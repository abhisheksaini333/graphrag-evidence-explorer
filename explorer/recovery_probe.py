"""Run an actual killed-process indexing recovery probe against the local model."""
import argparse, json, os, signal, subprocess, sys, time
from pathlib import Path
from .domain import DocumentInput
from .evidence import EvidenceStore
from .graph_adapter import PROFILE
from .jobs import JobQueue
from .store import Store


def probe(directory, model_url):
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    database = directory / "corpus.sqlite"
    store = Store(database)
    # Blank separators deliberately put two simple assertions in separate chunks.
    store.put_document(
        DocumentInput(
            "recovery",
            "Recovery fixture",
            "Mira owns Atlas." + "\n" * 580 + "Omar owns Boreal.",
        )
    )
    jobs = JobQueue(store)
    job = jobs.enqueue("recovery", PROFILE, budget=(16, 24000))
    command = [
        sys.executable,
        "-m",
        "explorer.worker",
        "--database",
        str(database),
        "--model-url",
        model_url,
        "--lease-seconds",
        "90",
        "--once",
    ]
    first = None
    with (directory / "first-worker.log").open("w") as log:
        first = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + 150
        try:
            while time.monotonic() < deadline:
                if EvidenceStore(jobs).completed_chunks(job["id"]):
                    break
                if first.poll() is not None:
                    raise RuntimeError(
                        "Worker exited before publishing the first passage"
                    )
                time.sleep(0.025)
            else:
                raise TimeoutError("Worker did not checkpoint within the probe limit")
            os.kill(first.pid, signal.SIGSTOP)
            first_chunk = next(iter(EvidenceStore(jobs).completed_chunks(job["id"])))
            with store.connect() as db:
                before = [
                    dict(row)
                    for row in db.execute(
                        "SELECT call_key,status FROM model_calls WHERE job_id=? AND call_key IN (?,?) ORDER BY call_key",
                        (job["id"], "extract:" + first_chunk, "embed:" + first_chunk),
                    )
                ]
            os.kill(first.pid, signal.SIGKILL)
            first.wait(timeout=10)
        finally:
            if first.poll() is None:
                first.kill()
                first.wait(timeout=10)
    deadline = time.monotonic() + 100
    while jobs.get(job["id"])["lease_until"] > time.time():
        if time.monotonic() > deadline:
            raise TimeoutError("Interrupted lease did not expire")
        time.sleep(0.1)
    with (directory / "second-worker.log").open("w") as log:
        second = subprocess.run(
            command, stdout=log, stderr=subprocess.STDOUT, timeout=150
        )
    with store.connect() as db:
        after = [
            dict(row)
            for row in db.execute(
                "SELECT call_key,status FROM model_calls WHERE job_id=? AND call_key IN (?,?) ORDER BY call_key",
                (job["id"], "extract:" + first_chunk, "embed:" + first_chunk),
            )
        ]
    state = jobs.get(job["id"])
    snapshot = EvidenceStore(jobs).snapshot(PROFILE)
    assert first.returncode == -signal.SIGKILL
    assert second.returncode == 0 and state["status"] == "complete", state
    assert (
        before == after
        and len(before) == 2
        and all(c["status"] == "complete" for c in before)
    )
    report = {
        "method": "SIGSTOP/SIGKILL the actual indexing child after SQLite publication, wait for real lease expiry, run a fresh child",
        "first_exit": first.returncode,
        "second_exit": second.returncode,
        "status": state["status"],
        "attempts": state["attempt"],
        "first_passage_calls_before": before,
        "first_passage_calls_after": after,
        "passages": len(snapshot["vectors"]),
        "claims": len(snapshot["claims"]),
        "completed_calls_repeated": False,
    }
    (directory / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model-url", default="http://127.0.0.1:8090")
    args = parser.parse_args()
    print(json.dumps(probe(args.output, args.model_url), indent=2))
