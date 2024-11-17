"""Restartable indexing worker with durable per-passage model checkpoints."""
import argparse
import asyncio
import json
import logging
import time
import uuid
from .budget import ModelBudget, BudgetExceeded
from .domain import Invalid
from .evidence import EvidenceStore
from .graph_adapter import PROFILE, extract_graph
from .jobs import JobQueue
from .model_client import ModelClient, ModelUnavailable
from .models import model_manifest
from .store import Store, Conflict


class Worker:
    def __init__(self, store, model, lease_seconds=120):
        self.store, self.model = store, model
        self.jobs = JobQueue(store)
        self.budget = ModelBudget(self.jobs)
        self.evidence = EvidenceStore(self.jobs)
        self.name = "index-" + uuid.uuid4().hex[:12]
        self.lease_seconds = lease_seconds
        self.after_publish = None

    def _ready(self):
        health = self.model.health()
        manifest = model_manifest()
        if (
            health.get("model_revision") != manifest["generation"]["revision"]
            or health.get("embedding_revision") != manifest["embedding"]["revision"]
            or health.get("embedding_dimensions") != 384
        ):
            raise ModelUnavailable(
                "Model process does not match the frozen indexing profile"
            )

    def _call(self, job, key, reserved_tokens, operation):
        self.jobs.heartbeat(job["id"], job["lease_token"], self.lease_seconds)
        reservation = self.budget.reserve(
            job["id"], job["lease_token"], key, reserved_tokens
        )
        if reservation["cached"] is not None:
            return reservation["cached"]
        result = operation()
        actual = result["input_tokens"] + result.get("output_tokens", 0)
        self.budget.complete(
            reservation["id"], job["lease_token"], result, actual_tokens=actual
        )
        return result

    def run_once(self):
        self._ready()
        job = self.jobs.claim(self.name, self.lease_seconds)
        if job is None:
            return {"status": "idle"}
        try:
            if job["profile"] != PROFILE:
                raise Invalid("Unsupported indexing profile")
            if "max_calls" not in self.budget.usage(job["id"]):
                self.budget.configure(job["id"])
            complete = self.evidence.completed_chunks(job["id"])
            chunks = self.store.chunks(job["document_id"])
            for chunk in chunks:
                if chunk["id"] in complete:
                    continue

                def invoke(prompt):
                    return self._call(
                        job,
                        "extract:" + chunk["id"],
                        len(prompt.encode("utf-8")) + 320,
                        lambda: self.model.generate(prompt, 192),
                    )

                result = asyncio.run(extract_graph(chunk["text"], invoke))
                embedding = self._call(
                    job,
                    "embed:" + chunk["id"],
                    len(chunk["text"].encode("utf-8")) + 32,
                    lambda: self.model.embed([chunk["text"]]),
                )
                self.evidence.publish(
                    job["id"],
                    job["lease_token"],
                    chunk["id"],
                    result,
                    embedding["vectors"][0],
                )
                if self.after_publish:
                    self.after_publish(job, chunk)
            self.jobs.finish(job["id"], job["lease_token"], "complete")
            return {
                "status": "complete",
                "job_id": job["id"],
                "passages": len(chunks),
                "usage": self.budget.usage(job["id"]),
            }
        except Conflict:
            return {"status": "ownership_lost", "job_id": job["id"]}
        except Exception as error:
            code = (
                "budget_exhausted"
                if isinstance(error, BudgetExceeded)
                else "model_unavailable"
                if isinstance(error, ModelUnavailable)
                else "invalid_extraction"
                if isinstance(error, Invalid)
                else "index_failed"
            )
            logging.warning("Indexing stopped: %s", code)
            try:
                self.jobs.finish(job["id"], job["lease_token"], "failed", code)
            except Conflict:
                return {"status": "ownership_lost", "job_id": job["id"]}
            return {"status": "failed", "job_id": job["id"], "error": code}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", default=".data/corpus.sqlite")
    parser.add_argument("--model-url", default="http://127.0.0.1:8090")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--lease-seconds", type=int, default=120)
    args = parser.parse_args()
    # Load the large framework before a short-lived job lease is acquired.
    from graphrag.index.graph.extractors.graph.graph_extractor import GraphExtractor

    worker = Worker(
        Store(args.database), ModelClient(args.model_url), args.lease_seconds
    )
    while True:
        try:
            result = worker.run_once()
        except ModelUnavailable:
            result = {"status": "model_unavailable"}
        print(json.dumps(result), flush=True)
        if args.once:
            return 0 if result["status"] in ("idle", "complete") else 1
        time.sleep(1 if result["status"] in ("idle", "model_unavailable") else 0.1)


if __name__ == "__main__":
    raise SystemExit(main())
