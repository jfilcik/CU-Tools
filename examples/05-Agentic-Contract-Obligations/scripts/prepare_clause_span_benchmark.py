"""Prepare a deterministic, category-covering CUAD clause-span benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parents[1]
SEED = "cuad-clause-spans-agentic-v1"


def read_jsonl(path: Path) -> dict[str, dict[str, Any]]:
    return {
        row["doc_id"]: row
        for row in (
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    }


def select_documents(
    documents: list[dict[str, Any]],
    gold_by_id: dict[str, dict[str, Any]],
    count: int,
    seed: str = SEED,
) -> list[dict[str, Any]]:
    """Greedily select held-out documents to maximize category coverage."""
    candidates = [
        document
        for document in documents
        if document.get("split") == "held_out" and document["doc_id"] in gold_by_id
    ]
    selected: list[dict[str, Any]] = []
    category_counts: Counter[str] = Counter()
    while candidates and len(selected) < count:
        def rank(document: dict[str, Any]) -> tuple[float, str]:
            categories = {
                clause["category"]
                for clause in gold_by_id[document["doc_id"]].get("clauses", [])
            }
            coverage = sum(1.0 / (category_counts[name] + 1) for name in categories)
            tie_breaker = hashlib.sha256(
                f"{seed}:{document['doc_id']}".encode("utf-8")
            ).hexdigest()
            return (-coverage, tie_breaker)

        candidates.sort(key=rank)
        chosen = candidates.pop(0)
        selected.append(chosen)
        category_counts.update(
            {
                clause["category"]
                for clause in gold_by_id[chosen["doc_id"]].get("clauses", [])
            }
        )
    if len(selected) != count:
        raise ValueError(f"Requested {count} documents but selected {len(selected)}")
    return selected


def prepare(
    selection_path: Path,
    gold_path: Path,
    mapping_path: Path,
    source_dir: Path,
    output_dir: Path,
    manifest_path: Path,
    count: int,
) -> dict[str, Any]:
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    gold_by_id = read_jsonl(gold_path)
    selected = select_documents(selection["documents"], gold_by_id, count)

    selected_categories = {
        clause["category"]
        for document in selected
        for clause in gold_by_id[document["doc_id"]].get("clauses", [])
    }
    missing = sorted(set(mapping) - selected_categories)
    if missing:
        raise ValueError(f"Selected benchmark does not cover categories: {missing}")

    shutil.rmtree(output_dir, ignore_errors=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for document in selected:
        doc_id = document["doc_id"]
        source = source_dir / f"{doc_id}.txt"
        if not source.exists():
            raise ValueError(f"Missing prepared CUAD input: {source}")
        shutil.copy2(source, output_dir / source.name)
        clauses = gold_by_id[doc_id].get("clauses", [])
        records.append(
            {
                "doc_id": doc_id,
                "original_document_id": document["original_document_id"],
                "gold_span_count": len(clauses),
                "categories": sorted({clause["category"] for clause in clauses}),
            }
        )

    manifest = {
        "dataset": selection["dataset"],
        "revision": selection["revision"],
        "seed": SEED,
        "selection_strategy": "category-coverage greedy selection",
        "document_count": len(records),
        "gold_span_count": sum(record["gold_span_count"] for record in records),
        "covered_categories": sorted(selected_categories),
        "documents": records,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=15)
    parser.add_argument(
        "--selection",
        type=Path,
        default=PROJECT_DIR / "dataset" / "selection_manifest.json",
    )
    parser.add_argument(
        "--gold",
        type=Path,
        default=PROJECT_DIR / "ground_truth" / "cuad_clause_gold.jsonl",
    )
    parser.add_argument(
        "--mapping",
        type=Path,
        default=PROJECT_DIR / "dataset" / "clause_span_field_mapping.json",
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=PROJECT_DIR / "test_results" / "heldout-inputs",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_DIR / "test_results" / "clause-span-15-input",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=PROJECT_DIR / "test_results" / "clause-span-15-selection.json",
    )
    args = parser.parse_args()
    manifest = prepare(
        args.selection.resolve(),
        args.gold.resolve(),
        args.mapping.resolve(),
        args.source_dir.resolve(),
        args.output_dir.resolve(),
        args.manifest.resolve(),
        args.count,
    )
    print(
        f"Prepared {manifest['document_count']} documents, "
        f"{manifest['gold_span_count']} gold spans, and "
        f"{len(manifest['covered_categories'])} categories."
    )


if __name__ == "__main__":
    main()
