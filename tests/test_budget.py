import tempfile
from pathlib import Path
import unittest
from explorer.domain import DocumentInput
from explorer.store import Store, Conflict
from explorer.jobs import JobQueue
from explorer.budget import ModelBudget, BudgetExceeded


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.now = 1000.0
        self.store = Store(Path(self.temp.name) / "db", clock=lambda: self.now)
        self.store.put_document(DocumentInput("atlas", "Atlas", "Mira owns Atlas."))
        self.jobs = JobQueue(self.store)
        self.job = self.jobs.enqueue("atlas", "v1")
        self.claim = self.jobs.claim("one", lease_seconds=10)
        self.budget = ModelBudget(self.jobs)
        self.budget.configure(self.job["id"], max_calls=2, max_tokens=200)

    def tearDown(self):
        self.temp.cleanup()

    def test_reservations_are_durable_and_enforce_both_limits(self):
        self.budget.reserve(self.job["id"], self.claim["lease_token"], "chunk-a", 120)
        with self.assertRaises(BudgetExceeded):
            self.budget.reserve(
                self.job["id"], self.claim["lease_token"], "chunk-b", 100
            )
        self.budget.reserve(self.job["id"], self.claim["lease_token"], "chunk-b", 80)
        with self.assertRaises(BudgetExceeded):
            self.budget.reserve(self.job["id"], self.claim["lease_token"], "chunk-c", 1)
        self.assertEqual(
            ModelBudget(self.jobs).usage(self.job["id"])["reserved_tokens"], 200
        )

    def test_completed_inference_is_reused_after_worker_reclaim(self):
        token = self.claim["lease_token"]
        r = self.budget.reserve(self.job["id"], token, "chunk-a", 100)
        self.budget.complete(
            r["id"], token, {"raw": "Mira owns Atlas"}, actual_tokens=40
        )
        self.now += 11
        replacement = self.jobs.claim("two", lease_seconds=10)
        cached = self.budget.reserve(
            self.job["id"], replacement["lease_token"], "chunk-a", 100
        )
        self.assertEqual(cached["cached"], {"raw": "Mira owns Atlas"})
        self.assertEqual(self.budget.usage(self.job["id"])["calls"], 1)

    def test_interrupted_inference_is_charged_again_but_old_completion_is_fenced(self):
        old = self.budget.reserve(
            self.job["id"], self.claim["lease_token"], "chunk-a", 100
        )
        self.now += 11
        new = self.jobs.claim("two", lease_seconds=10)
        second = self.budget.reserve(self.job["id"], new["lease_token"], "chunk-a", 100)
        with self.assertRaises(Conflict):
            self.budget.complete(
                old["id"], self.claim["lease_token"], {}, actual_tokens=10
            )
        self.budget.complete(
            second["id"], new["lease_token"], {"ok": True}, actual_tokens=20
        )
        self.assertEqual(self.budget.usage(self.job["id"])["calls"], 2)

    def test_budget_cannot_be_reconfigured_after_usage(self):
        self.budget.reserve(self.job["id"], self.claim["lease_token"], "a", 100)
        with self.assertRaises(Conflict):
            self.budget.configure(self.job["id"], max_calls=5, max_tokens=1000)
