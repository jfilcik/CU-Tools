"""Generate weighted contract-obligation accuracy reports from EvalLens output."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
DEFAULT_REPORT_DIR = HERE.parent / "reports"
WEIGHTS = {
    "obligation_discovery": 0.30,
    "obligation_type_accuracy": 0.15,
    "party_role_accuracy": 0.20,
    "quote_groundedness": 0.10,
    "quote_alignment": 0.15,
    "obligation_completeness": 0.05,
    "duplicate_obligation": 0.05,
}


def aggregate(result: dict[str, Any]) -> dict[str, Any]:
    scores: dict[str, list[float]] = defaultdict(list)
    missing_scores: Counter[str] = Counter()
    per_document = []
    for row in result.get("results", []):
        row_scores = {name: 0.0 for name in WEIGHTS}
        seen = set()
        for item in row.get("evaluation_results", []):
            name = item.get("name")
            score = item.get("score")
            if name in WEIGHTS and isinstance(score, (int, float)):
                row_scores[name] = float(score)
                seen.add(name)
        for name in WEIGHTS:
            scores[name].append(row_scores[name])
            if name not in seen:
                missing_scores[name] += 1
        per_document.append({"doc_id": row.get("doc_id", ""), **row_scores})

    component_scores = {
        name: statistics.fmean(scores[name]) if scores[name] else 0.0
        for name in WEIGHTS
    }
    overall = sum(component_scores[name] * weight for name, weight in WEIGHTS.items())
    return {
        "run_id": result.get("run_id", ""),
        "module_name": result.get("module_name", ""),
        "timestamp": result.get("timestamp", ""),
        "document_count": len(per_document),
        "overall_score": round(overall, 4),
        "passed": overall >= 0.80,
        "component_scores": {
            name: round(score, 4) for name, score in component_scores.items()
        },
        "weights": WEIGHTS,
        "missing_evaluator_scores": dict(missing_scores),
        "per_document": per_document,
    }


def write_reports(summary: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "overall_accuracy.json").write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )
    with (output_dir / "per_contract_scores.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        fieldnames = ["doc_id", *WEIGHTS]
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for row in summary["per_document"]:
            writer.writerow({name: row.get(name, "") for name in fieldnames})

    status = "PASS" if summary["passed"] else "FAIL"
    lines = [
        "# Contract obligation extraction accuracy",
        "",
        f"**Weighted overall score: {summary['overall_score']:.1%} ({status})**",
        "",
        f"- Run ID: `{summary['run_id']}`",
        f"- Documents: {summary['document_count']}",
        f"- EvalLens timestamp: `{summary['timestamp']}`",
        "",
        "## Components",
        "",
        "| Component | Score | Weight |",
        "|---|---:|---:|",
    ]
    for name, weight in WEIGHTS.items():
        lines.append(
            f"| {name.replace('_', ' ').title()} | "
            f"{summary['component_scores'][name]:.1%} | {weight:.0%} |"
        )
    lines.extend(
        [
            "",
            "## Missing evaluator scores",
            "",
            (
                "Missing scores are treated as zero (fail closed): "
                + (
                    ", ".join(
                        f"{name}={count}"
                        for name, count in sorted(
                            summary["missing_evaluator_scores"].items()
                        )
                    )
                    if summary["missing_evaluator_scores"]
                    else "none"
                )
            ),
            "",
            "## Interpretation",
            "",
            "The overall score is deterministic and excludes optional LLM judging. "
            "Review EvalLens row-level reasons for unsupported obligations, quote failures, "
            "type or party mismatches, missing detail fields, and duplicates.",
            "",
            "A missing live run or incomplete six-contract atomic annotation set is an "
            "execution gap, not a passing quality result.",
            "",
        ]
    )
    (output_dir / "overall_accuracy.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT_DIR)
    args = parser.parse_args()
    summary = aggregate(json.loads(args.input.read_text(encoding="utf-8")))
    write_reports(summary, args.output.resolve())
    print(
        f"Weighted score: {summary['overall_score']:.1%}; "
        f"report: {args.output.resolve() / 'overall_accuracy.md'}"
    )


if __name__ == "__main__":
    main()
