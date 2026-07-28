"""Create deterministic CUAD development and held-out benchmark artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parents[1]
CATEGORY_PATTERN = re.compile(r'related to "([^"]+)"')


def _category(question: str) -> str:
    match = CATEGORY_PATTERN.search(question)
    return match.group(1) if match else question.strip()


def _doc_id(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:48]
    suffix = hashlib.sha256(title.encode("utf-8")).hexdigest()[:8]
    return f"{slug}-{suffix}"


def _answers(record: dict[str, Any], mapping: dict[str, str]) -> list[dict[str, Any]]:
    paragraph = record["paragraphs"][0]
    answers = []
    for qa in paragraph["qas"]:
        category = _category(qa["question"])
        if category not in mapping:
            continue
        for answer in qa.get("answers", []):
            text = answer.get("text", "")
            start = answer.get("answer_start")
            if not text or not isinstance(start, int):
                continue
            answers.append(
                {
                    "category": category,
                    "obligation_type": mapping[category],
                    "exact_quote": text,
                    "start": start,
                    "end": start + len(text),
                }
            )
    return answers


def select_records(
    records: list[dict[str, Any]],
    mapping: dict[str, str],
    total: int,
    seed: str,
) -> list[tuple[dict[str, Any], list[dict[str, Any]]]]:
    candidates = [
        (record, _answers(record, mapping))
        for record in records
        if _answers(record, mapping)
    ]
    selected = []
    category_counts: Counter[str] = Counter()

    while candidates and len(selected) < total:
        def rank(item):
            record, answers = item
            categories = {answer["category"] for answer in answers}
            coverage_score = sum(1.0 / (category_counts[name] + 1) for name in categories)
            tie_breaker = hashlib.sha256(
                f"{seed}:{record['title']}".encode("utf-8")
            ).hexdigest()
            return (-coverage_score, tie_breaker)

        candidates.sort(key=rank)
        chosen = candidates.pop(0)
        selected.append(chosen)
        category_counts.update({answer["category"] for answer in chosen[1]})

    if len(selected) != total:
        raise ValueError(f"Requested {total} records but found {len(selected)} eligible records")
    return selected


def prepare(
    dataset_path: Path,
    mapping_path: Path,
    manifest_path: Path,
    project_dir: Path,
    clean: bool = False,
) -> dict[str, Any]:
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    selection = manifest["selection"]
    dev_count = int(selection["development_count"])
    held_count = int(selection["held_out_count"])
    total = dev_count + held_count

    chosen = select_records(dataset["data"], mapping, total, selection["seed"])
    samples_dir = project_dir / "samples" / "downloaded"
    gold_dir = project_dir / "ground_truth"
    selection_path = project_dir / "dataset" / "selection_manifest.json"
    clause_gold_path = gold_dir / "cuad_clause_gold.jsonl"

    if clean:
        shutil.rmtree(samples_dir, ignore_errors=True)
        clause_gold_path.unlink(missing_ok=True)
        selection_path.unlink(missing_ok=True)
    samples_dir.mkdir(parents=True, exist_ok=True)
    gold_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    selected_docs = []
    for index, (record, answers) in enumerate(chosen):
        split = "development" if index < dev_count else "held_out"
        doc_id = _doc_id(record["title"])
        context = record["paragraphs"][0]["context"]
        sample_path = samples_dir / f"{doc_id}.txt"
        sample_path.write_text(context, encoding="utf-8")
        rows.append(
            {
                "doc_id": doc_id,
                "split": split,
                "source_text": context,
                "clauses": answers,
            }
        )
        selected_docs.append(
            {
                "doc_id": doc_id,
                "original_document_id": record["title"],
                "split": split,
                "contract_type": "",
                "selected_categories": sorted({answer["category"] for answer in answers}),
                "source": manifest["repository"],
                "revision": manifest["revision"],
                "attribution": manifest["dataset"],
            }
        )

    with clause_gold_path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")

    held_out = [row for row in selected_docs if row["split"] == "held_out"]
    atomic_count = int(selection["atomic_annotation_count"])
    atomic_ids = [
        row["doc_id"]
        for row in sorted(
            held_out,
            key=lambda row: hashlib.sha256(
                f"{selection['seed']}:atomic:{row['doc_id']}".encode("utf-8")
            ).hexdigest(),
        )[:atomic_count]
    ]
    output_manifest = {
        "dataset": manifest["dataset"],
        "revision": manifest["revision"],
        "selection_strategy": selection["strategy"],
        "seed": selection["seed"],
        "documents": selected_docs,
        "atomic_annotation_doc_ids": atomic_ids,
    }
    selection_path.write_text(
        json.dumps(output_manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=PROJECT_DIR / "dataset" / "raw" / "CUADv1.json",
    )
    parser.add_argument(
        "--mapping",
        type=Path,
        default=PROJECT_DIR / "dataset" / "obligation_type_mapping.json",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=PROJECT_DIR / "dataset" / "cuad_manifest.json",
    )
    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args()
    output = prepare(
        args.dataset.resolve(),
        args.mapping.resolve(),
        args.manifest.resolve(),
        PROJECT_DIR,
        clean=args.clean,
    )
    print(
        f"Prepared {len(output['documents'])} contracts; "
        f"{len(output['atomic_annotation_doc_ids'])} require atomic annotation."
    )


if __name__ == "__main__":
    main()
