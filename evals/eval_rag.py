"""Run a small deterministic RAG retrieval evaluation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.rag_retriever import retrieve_context  # noqa: E402


DATASET_PATH = PROJECT_ROOT / "evals" / "rag_eval_dataset.json"
OUTPUT_PATH = PROJECT_ROOT / "reports" / "rag_eval_results.json"


def citation_sources_exist(retrieved: list[dict]) -> bool:
    sources = {item.get("source") for item in retrieved}
    return all(source and source in sources for source in sources)


def evaluate(top_k: int = 3) -> dict:
    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    details = []

    for item in dataset:
        retrieved = retrieve_context(item["question"], top_k=top_k)
        sources = [doc.get("source") for doc in retrieved]
        expected_source = item.get("expected_source")

        topk_contains_expected = expected_source in sources if expected_source else None
        rejected = len(retrieved) == 0
        citation_checked = len(retrieved) > 0
        citation_passed = citation_sources_exist(retrieved) if citation_checked else False

        details.append(
            {
                "id": item["id"],
                "type": item["type"],
                "question": item["question"],
                "expected_source": expected_source,
                "retrieved_sources": sources,
                "topk_contains_expected": topk_contains_expected,
                "rejected": rejected,
                "citation_checked": citation_checked,
                "citation_passed": citation_passed,
            }
        )

    answerable = [item for item in details if item["type"] == "answerable"]
    unanswerable = [item for item in details if item["type"] == "unanswerable"]
    citation_checked = [item for item in details if item["citation_checked"]]

    summary = {
        "total_questions": len(details),
        "answerable_questions": len(answerable),
        "topk_expected_source_hits": sum(1 for item in answerable if item["topk_contains_expected"]),
        "unanswerable_questions": len(unanswerable),
        "correct_rejections": sum(1 for item in unanswerable if item["rejected"]),
        "citation_validator_checks": len(citation_checked),
        "citation_validator_passed": sum(1 for item in citation_checked if item["citation_passed"]),
        "details": details,
    }
    return summary


def main() -> int:
    summary = evaluate()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "details"}, ensure_ascii=False, indent=2))
    print(f"Saved: {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
