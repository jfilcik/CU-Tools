"""Build canonical EvalLens prediction and ground-truth JSONL files."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parents[1]
NORMALIZER_PATH = (
    PROJECT_DIR
    / "evaluation"
    / "preprocessors"
    / "contract_obligations"
    / "normalize_cu_results.py"
)


def _load_normalizer():
    spec = importlib.util.spec_from_file_location("contract_normalizer", NORMALIZER_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load normalizer: {NORMALIZER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.canonicalize_result


def _read_jsonl(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    records = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        record = json.loads(line)
        doc_id = record.get("doc_id")
        if not doc_id:
            raise ValueError(f"{path}:{line_number} is missing doc_id")
        records[doc_id] = record
    return records


def validate_atomic_coverage(
    selection_manifest_path: Path,
    atomic_gold: dict[str, dict[str, Any]],
) -> None:
    if not selection_manifest_path.exists():
        raise FileNotFoundError(
            f"Selection manifest not found: {selection_manifest_path}. "
            "Run prepare_cuad_eval.py first."
        )
    selection = json.loads(selection_manifest_path.read_text(encoding="utf-8"))
    required_ids = set(selection.get("atomic_annotation_doc_ids", []))
    missing = sorted(required_ids - set(atomic_gold))
    unverified = sorted(
        doc_id
        for doc_id in required_ids & set(atomic_gold)
        if atomic_gold[doc_id].get("review_status") != "verified"
    )
    if missing or unverified:
        raise ValueError(
            "Atomic ground truth is incomplete; "
            f"missing={missing}, not_verified={unverified}. "
            "Complete second-review annotation before scoring."
        )


def build(
    results_dir: Path,
    clause_gold_path: Path,
    atomic_gold_path: Path,
    selection_manifest_path: Path,
    output_dir: Path,
) -> tuple[int, int]:
    canonicalize = _load_normalizer()
    clause_gold = _read_jsonl(clause_gold_path)
    atomic_gold = _read_jsonl(atomic_gold_path)
    validate_atomic_coverage(selection_manifest_path, atomic_gold)
    output_dir.mkdir(parents=True, exist_ok=True)
    pred_path = output_dir / "pred.jsonl"
    gt_path = output_dir / "gt.jsonl"

    predictions = []
    ground_truth = []
    for result_path in sorted(results_dir.rglob("*.json")):
        if result_path.name == "metadata.json":
            continue
        raw = json.loads(result_path.read_text(encoding="utf-8"))
        document = raw.get("_metadata", {}).get("document", result_path.stem)
        doc_id = Path(document).stem
        prediction = canonicalize(raw, doc_id)
        gold = dict(clause_gold.get(doc_id, {}))
        gold.update(atomic_gold.get(doc_id, {}))
        if not gold:
            continue
        prediction["source_text"] = gold.get("source_text", "")
        predictions.append(prediction)
        ground_truth.append(gold)

    with pred_path.open("w", encoding="utf-8", newline="\n") as stream:
        for record in predictions:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    with gt_path.open("w", encoding="utf-8", newline="\n") as stream:
        for record in ground_truth:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    return len(predictions), len(ground_truth)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument(
        "--clause-gold",
        type=Path,
        default=PROJECT_DIR / "ground_truth" / "cuad_clause_gold.jsonl",
    )
    parser.add_argument(
        "--atomic-gold",
        type=Path,
        default=PROJECT_DIR / "ground_truth" / "atomic_obligations_gold.jsonl",
    )
    parser.add_argument(
        "--selection-manifest",
        type=Path,
        default=PROJECT_DIR / "dataset" / "selection_manifest.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_DIR / "evaluation" / "data",
    )
    args = parser.parse_args()
    pred_count, gt_count = build(
        args.results.resolve(),
        args.clause_gold.resolve(),
        args.atomic_gold.resolve(),
        args.selection_manifest.resolve(),
        args.output.resolve(),
    )
    print(f"Wrote {pred_count} predictions and {gt_count} ground-truth records.")


if __name__ == "__main__":
    main()
