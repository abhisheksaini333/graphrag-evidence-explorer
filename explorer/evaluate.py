"""Same-corpus comparisons; lexical coverage is a diagnostic, not semantic accuracy."""
import argparse, hashlib, json, statistics
from pathlib import Path
from .model_client import ModelClient
from .search import Search
from .store import Store


def score_case(case, run):
    result = run.get("result") or {}
    answer = result.get("answer") or ""
    documents = {p["document_id"] for p in result.get("passages", [])}
    required = set(case["required_docs"])
    terms = case["answer_terms"]
    return {
        "case_id": case["id"],
        "kind": case["kind"],
        "mode": run["mode"],
        "status": run["status"],
        "run_id": run["id"],
        "retrieval_document_recall": len(required & documents) / len(required)
        if required
        else None,
        "all_required_documents_retrieved": required <= documents if required else None,
        "answer_term_coverage": sum(t.casefold() in answer.casefold() for t in terms)
        / len(terms)
        if terms
        else None,
        "expected_abstention_observed": bool(result.get("abstained"))
        if case["kind"] == "abstention"
        else None,
        "seconds": result.get("seconds"),
        "model_calls": len(run["calls"]),
        "actual_tokens": sum(
            (c.get("response") or {}).get("input_tokens", 0)
            + (c.get("response") or {}).get("output_tokens", 0)
            for c in run["calls"]
        ),
        "answer": result.get("answer"),
        "error": run.get("error"),
        "retrieved_documents": sorted(documents),
    }


def evaluate(store, model, cases):
    search = Search(store, model)
    rows = []
    for case in cases:
        for mode in ("vector", "local", "global"):
            row = score_case(case, search.query(case["question"], mode))
            rows.append(row)
            print(json.dumps(row), flush=True)
    summaries = {}
    for mode in ("vector", "local", "global"):
        selected = [r for r in rows if r["mode"] == mode]

        def mean(key):
            values = [r[key] for r in selected if r[key] is not None]
            return statistics.mean(values) if values else None

        summaries[mode] = {
            "queries": len(selected),
            "completed": sum(r["status"] == "complete" for r in selected),
            "mean_required_document_recall": mean("retrieval_document_recall"),
            "mean_answer_term_coverage": mean("answer_term_coverage"),
            "correct_abstentions": sum(
                r["expected_abstention_observed"] is True for r in selected
            ),
            "mean_seconds": mean("seconds"),
            "model_calls": sum(r["model_calls"] for r in selected),
            "actual_tokens": sum(r["actual_tokens"] for r in selected),
        }
    return {
        "schema": 1,
        "limitations": [
            "Small owned synthetic corpus, not external production traffic.",
            "Lexical answer-term coverage does not establish correctness or entailment.",
            "Citation validation proves source IDs exist, not that answers follow from them.",
            "Global mode has an extra map step; actual token and call cost is reported.",
        ],
        "generation": store.generation(),
        "summary": summaries,
        "cases": rows,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", default=".data/corpus.sqlite")
    parser.add_argument("--model-url", default="http://127.0.0.1:8090")
    parser.add_argument("--questions", default="examples/questions.json")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    raw = Path(args.questions).read_bytes()
    report = evaluate(
        Store(args.database), ModelClient(args.model_url), json.loads(raw)
    )
    report["questions_sha256"] = hashlib.sha256(raw).hexdigest()
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n")
