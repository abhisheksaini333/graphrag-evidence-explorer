"""Import the owned demonstration corpus without overwriting edited documents."""
import argparse, json
from pathlib import Path
from .domain import DocumentInput
from .store import Store
from .jobs import JobQueue
from .graph_adapter import PROFILE


def seed(store, path):
    documents = json.loads(Path(path).read_text())
    existing = {d["id"] for d in store.list_documents()}
    jobs = JobQueue(store)
    results = []
    for value in documents:
        document = DocumentInput.parse(value)
        if document.id not in existing:
            store.put_document(document, expected_revision=0)
        results.append(jobs.enqueue(document.id, PROFILE))
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", default=".data/corpus.sqlite")
    parser.add_argument("--corpus", default="examples/corpus.json")
    args = parser.parse_args()
    print(json.dumps(seed(Store(args.database), args.corpus), indent=2))
