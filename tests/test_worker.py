import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from explorer.domain import DocumentInput
from explorer.store import Store
from explorer.jobs import JobQueue
from explorer.budget import ModelBudget
from explorer.evidence import EvidenceStore
from explorer.graph_adapter import PROFILE
from explorer.worker import Worker
from explorer.models import model_manifest


class ProcessCrash(BaseException):
    pass


class FixtureModel:
    def __init__(self):
        self.generations = 0
        self.embeddings = 0
        self.on_generate = None

    def health(self):
        manifest = model_manifest()
        return {
            "model_revision": manifest["generation"]["revision"],
            "embedding_revision": manifest["embedding"]["revision"],
            "embedding_dimensions": 384,
        }

    def generate(self, prompt, max_new_tokens=192):
        self.generations += 1
        if self.on_generate:
            self.on_generate()
        return {
            "text": json.dumps(
                [{"subject": "Mira", "relation": "owns", "object": "Atlas"}]
            ),
            "input_tokens": 20,
            "output_tokens": 15,
        }

    def embed(self, texts):
        self.embeddings += 1
        return {"vectors": [[1.0] + [0.0] * 383 for _ in texts], "input_tokens": 10}


@unittest.skipUnless(
    importlib.util.find_spec("graphrag"), "Requires frozen GraphRAG runtime"
)
class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.now = 1000.0
        self.store = Store(Path(self.temp.name) / "db", clock=lambda: self.now)
        self.jobs = JobQueue(self.store)
        self.model = FixtureModel()
        self.worker = Worker(self.store, self.model, lease_seconds=10)

    def tearDown(self):
        self.temp.cleanup()

    def add(self, text="Mira owns Atlas."):
        self.store.put_document(DocumentInput("atlas", "Atlas", text))
        return self.jobs.enqueue("atlas", PROFILE)

    def test_worker_builds_actual_framework_graph_and_checkpointed_vectors(self):
        job = self.add()
        result = self.worker.run_once()
        self.assertEqual(result["status"], "complete")
        self.assertEqual(len(EvidenceStore(self.jobs).snapshot(PROFILE)["claims"]), 1)
        self.assertEqual(ModelBudget(self.jobs).usage(job["id"])["calls"], 2)

    def test_crash_recovery_skips_completed_passage_model_calls(self):
        job = self.add("Mira owns Atlas. " * 50)

        def crash(*args):
            raise ProcessCrash()

        self.worker.after_publish = crash
        with self.assertRaises(ProcessCrash):
            self.worker.run_once()
        self.assertEqual(self.model.generations, 1)
        self.now += 11
        self.worker.after_publish = None
        result = self.worker.run_once()
        self.assertEqual(result["status"], "complete")
        chunks = len(self.store.chunks("atlas"))
        self.assertEqual(self.model.generations, chunks)
        self.assertEqual(self.model.embeddings, chunks)
        self.assertEqual(ModelBudget(self.jobs).usage(job["id"])["calls"], 2 * chunks)

    def test_operator_cancellation_during_inference_cannot_publish(self):
        job = self.add()
        self.model.on_generate = lambda: self.jobs.cancel(job["id"])
        result = self.worker.run_once()
        self.assertEqual(result["status"], "ownership_lost")
        self.assertEqual(self.jobs.get(job["id"])["status"], "cancelled")
        self.assertEqual(EvidenceStore(self.jobs).completed_chunks(job["id"]), set())

    def test_budget_exhaustion_leaves_a_recoverable_explicit_failure(self):
        job = self.add()
        ModelBudget(self.jobs).configure(job["id"], max_calls=1, max_tokens=10000)
        result = self.worker.run_once()
        self.assertEqual(result["status"], "failed")
        self.assertEqual(self.jobs.get(job["id"])["error"], "budget_exhausted")
        self.assertEqual(self.model.generations, 1)
        self.assertEqual(self.model.embeddings, 0)
