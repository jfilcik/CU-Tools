"""Score category-specific CU clause spans against official CUAD annotations."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parents[1]
VALUE_KEYS = (
    "valueString",
    "valueNumber",
    "valueInteger",
    "valueBoolean",
    "valueDate",
    "valueTime",
)


def unwrap_field(node: Any) -> Any:
    if not isinstance(node, dict):
        return node
    if "valueArray" in node:
        return [unwrap_field(item) for item in node["valueArray"]]
    if "valueObject" in node:
        return {name: unwrap_field(value) for name, value in node["valueObject"].items()}
    for key in VALUE_KEYS:
        if key in node:
            return node[key]
    return None


def normalize(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value or "").split()).casefold()


def similarity(left: str, right: str) -> float:
    left_n = normalize(left)
    right_n = normalize(right)
    if not left_n or not right_n:
        return 0.0
    if left_n in right_n or right_n in left_n:
        return min(len(left_n), len(right_n)) / max(len(left_n), len(right_n))
    return SequenceMatcher(None, left_n, right_n).ratio()


def match_spans(
    predicted: list[str],
    expected: list[str],
    threshold: float,
) -> list[tuple[int, int, float]]:
    candidates = sorted(
        (
            (similarity(prediction, target), pred_index, gold_index)
            for pred_index, prediction in enumerate(predicted)
            for gold_index, target in enumerate(expected)
        ),
        reverse=True,
    )
    matches = []
    used_predictions: set[int] = set()
    used_gold: set[int] = set()
    for score, pred_index, gold_index in candidates:
        if (
            score < threshold
            or pred_index in used_predictions
            or gold_index in used_gold
        ):
            continue
        matches.append((pred_index, gold_index, score))
        used_predictions.add(pred_index)
        used_gold.add(gold_index)
    return matches


def rates(matches: int, predicted: int, expected: int) -> tuple[float, float, float]:
    precision = matches / predicted if predicted else (1.0 if expected == 0 else 0.0)
    recall = matches / expected if expected else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def read_jsonl(path: Path) -> dict[str, dict[str, Any]]:
    return {
        row["doc_id"]: row
        for row in (
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    }


def predicted_by_category(
    result_path: Path,
    field_mapping: dict[str, str],
) -> dict[str, list[str]]:
    raw = json.loads(result_path.read_text(encoding="utf-8"))
    contents = raw.get("result", {}).get("contents", [])
    fields = contents[0].get("fields", {}) if contents else {}
    clause_spans = unwrap_field(fields.get("ClauseSpans", {})) or {}
    return {
        category: [
            str(value)
            for value in clause_spans.get(field_name, []) or []
            if str(value).strip()
        ]
        for category, field_name in field_mapping.items()
    }


def score_run(
    result_dir: Path,
    benchmark_manifest_path: Path,
    gold_path: Path,
    mapping_path: Path,
    threshold: float,
) -> dict[str, Any]:
    metadata = json.loads((result_dir / "metadata.json").read_text(encoding="utf-8"))
    benchmark = json.loads(benchmark_manifest_path.read_text(encoding="utf-8"))
    gold_by_id = read_jsonl(gold_path)
    field_mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    run_rows = {
        Path(row.get("document", "")).stem: row
        for row in metadata.get("results", [])
    }
    category_totals: dict[str, Counter[str]] = {
        category: Counter() for category in field_mapping
    }
    document_rows = []
    latencies = []
    grounded = total_predictions = total_gold = total_matches = 0

    for document in benchmark["documents"]:
        doc_id = document["doc_id"]
        gold_record = gold_by_id[doc_id]
        source = normalize(gold_record["source_text"])
        expected_by_category: dict[str, list[str]] = defaultdict(list)
        for clause in gold_record.get("clauses", []):
            expected_by_category[clause["category"]].append(clause["exact_quote"])

        run_row = run_rows.get(doc_id, {"status": "failed", "error": "missing result"})
        status = run_row.get("status", "failed")
        result_path = result_dir / f"{doc_id}.json"
        predictions = (
            predicted_by_category(result_path, field_mapping)
            if status == "success" and result_path.exists()
            else {category: [] for category in field_mapping}
        )
        doc_matches = doc_predictions = doc_gold = doc_grounded = 0
        for category in field_mapping:
            predicted = predictions[category]
            expected = expected_by_category[category]
            matches = match_spans(predicted, expected, threshold)
            counts = category_totals[category]
            counts["predicted"] += len(predicted)
            counts["gold"] += len(expected)
            counts["matched"] += len(matches)
            counts["grounded"] += sum(normalize(span) in source for span in predicted)
            doc_predictions += len(predicted)
            doc_gold += len(expected)
            doc_matches += len(matches)
            doc_grounded += sum(normalize(span) in source for span in predicted)

        precision, recall, f1 = rates(doc_matches, doc_predictions, doc_gold)
        document_rows.append(
            {
                "doc_id": doc_id,
                "status": status,
                "elapsed_seconds": float(run_row.get("elapsed_seconds", 0)),
                "predicted": doc_predictions,
                "gold": doc_gold,
                "matched": doc_matches,
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "groundedness": (
                    doc_grounded / doc_predictions if doc_predictions else 0.0
                ),
                "error": run_row.get("error", ""),
            }
        )
        if status == "success":
            latencies.append(float(run_row.get("elapsed_seconds", 0)))
        total_predictions += doc_predictions
        total_gold += doc_gold
        total_matches += doc_matches
        grounded += doc_grounded

    precision, recall, f1 = rates(total_matches, total_predictions, total_gold)
    category_rows = []
    for category, counts in category_totals.items():
        cat_precision, cat_recall, cat_f1 = rates(
            counts["matched"], counts["predicted"], counts["gold"]
        )
        category_rows.append(
            {
                "category": category,
                **counts,
                "precision": cat_precision,
                "recall": cat_recall,
                "f1": cat_f1,
                "groundedness": (
                    counts["grounded"] / counts["predicted"]
                    if counts["predicted"]
                    else 0.0
                ),
            }
        )

    started_at = metadata.get("started_at", "")
    completed_at = metadata.get("completed_at", "")
    attempts = metadata.get("attempts", [])
    active_wall_seconds = 0.0
    for attempt in attempts:
        attempt_started = attempt.get("started_at", "")
        attempt_completed = attempt.get("completed_at", "")
        if attempt_started and attempt_completed:
            active_wall_seconds += (
                datetime.fromisoformat(attempt_completed.replace("Z", "+00:00"))
                - datetime.fromisoformat(attempt_started.replace("Z", "+00:00"))
            ).total_seconds()
    if not attempts and started_at and completed_at:
        active_wall_seconds = (
            datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
            - datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        ).total_seconds()
    successes = sum(row["status"] == "success" for row in document_rows)
    token_summary = metadata.get("token_summary", {})
    return {
        "run": {
            "run_id": metadata.get("run_id", ""),
            "analyzer_id": metadata.get("analyzer_id", ""),
            "api_version": metadata.get("api_version", ""),
            "started_at": started_at,
            "completed_at": completed_at,
            "active_wall_seconds": active_wall_seconds,
            "documents": len(document_rows),
            "successful": successes,
            "failed": len(document_rows) - successes,
            "attempt_count": sum(
                int(attempt.get("successful", 0)) + int(attempt.get("failed", 0))
                for attempt in attempts
            ) or len(document_rows),
        },
        "quality": {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "matched": total_matches,
            "predicted": total_predictions,
            "gold": total_gold,
            "groundedness": grounded / total_predictions if total_predictions else 0.0,
        },
        "operational": {
            "latency_mean_seconds": statistics.fmean(latencies) if latencies else 0.0,
            "latency_max_seconds": max(latencies, default=0.0),
            "tokens": token_summary,
        },
        "categories": sorted(category_rows, key=lambda row: row["category"]),
        "documents": document_rows,
    }


def percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def write_report(report: dict[str, Any], markdown_path: Path) -> None:
    run = report["run"]
    quality = report["quality"]
    operational = report["operational"]
    lines = [
        "# Agentic CUAD clause-span benchmark",
        "",
        "This benchmark evaluates category-specific exact-span extraction against "
        "official CUAD annotations. Failed documents contribute all gold spans and "
        "zero predictions.",
        "",
        "## Summary",
        "",
        "| Metric | Result |",
        "|---|---:|",
        f"| Completed | {run['successful']}/{run['documents']} |",
        f"| Active execution time | {run['active_wall_seconds'] / 3600:.2f} hours |",
        f"| Analysis attempts including retries | {run['attempt_count']} |",
        f"| Mean completed latency | {operational['latency_mean_seconds'] / 60:.1f} min |",
        f"| Gold spans | {quality['gold']} |",
        f"| Predicted spans | {quality['predicted']} |",
        f"| Matched spans | {quality['matched']} |",
        f"| Precision | {percent(quality['precision'])} |",
        f"| Recall | {percent(quality['recall'])} |",
        f"| F1 | {percent(quality['f1'])} |",
        f"| Source groundedness | {percent(quality['groundedness'])} |",
        f"| Input tokens | {int(operational['tokens'].get('total_input_tokens', 0)):,} |",
        f"| Output tokens | {int(operational['tokens'].get('total_output_tokens', 0)):,} |",
        "",
        "## Per-category quality",
        "",
        "| Category | Predicted | Gold | Matched | Precision | Recall | F1 | Grounded |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report["categories"]:
        lines.append(
            f"| {row['category']} | {row['predicted']} | {row['gold']} | "
            f"{row['matched']} | {percent(row['precision'])} | "
            f"{percent(row['recall'])} | {percent(row['f1'])} | "
            f"{percent(row['groundedness'])} |"
        )
    lines.extend(
        [
            "",
            "## Per-document quality",
            "",
            "| Document | Status | Predicted | Gold | Matched | Precision | Recall | F1 |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in report["documents"]:
        lines.append(
            f"| {row['doc_id']} | {row['status']} | {row['predicted']} | "
            f"{row['gold']} | {row['matched']} | {percent(row['precision'])} | "
            f"{percent(row['recall'])} | {percent(row['f1'])} |"
        )
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    markdown_path.with_suffix(".json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    with markdown_path.with_suffix(".csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=report["documents"][0].keys())
        writer.writeheader()
        writer.writerows(report["documents"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument(
        "--benchmark-manifest",
        type=Path,
        default=PROJECT_DIR / "test_results" / "clause-span-15-selection.json",
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
        "--output",
        type=Path,
        default=PROJECT_DIR / "reports" / "clause_span_15_quality.md",
    )
    parser.add_argument("--match-threshold", type=float, default=0.55)
    args = parser.parse_args()
    report = score_run(
        args.results.resolve(),
        args.benchmark_manifest.resolve(),
        args.gold.resolve(),
        args.mapping.resolve(),
        args.match_threshold,
    )
    write_report(report, args.output.resolve())
    print(args.output.resolve())


if __name__ == "__main__":
    main()
