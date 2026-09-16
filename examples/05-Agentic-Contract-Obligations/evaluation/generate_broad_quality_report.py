"""Score a broad CUAD run and generate fail-closed quality artifacts."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import statistics
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from contract_eval_common import (
    evidence_quotes,
    f1_score,
    format_measure,
    get_value,
    gold_obligations,
    load_run_metadata,
    match_obligations,
    normalize_quote_text,
    normalize_text,
    prediction_obligations,
    read_analysis_result,
    recorded_number,
    result_status,
)

HERE = Path(__file__).resolve().parent
PROJECT_DIR = HERE.parent
NORMALIZER_PATH = (
    HERE
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
    records = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            record = json.loads(line)
            records[record["doc_id"]] = record
    return records


def _failure_kind(error: str) -> str:
    lowered = error.lower()
    if "timed out" in lowered:
        return "timeout"
    if "connection" in lowered:
        return "connection_reset"
    if "request failed" in lowered:
        return "request_failed"
    return "other"


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = round((len(ordered) - 1) * percentile)
    return ordered[index]


def score_run(
    result_dir: Path,
    selection_manifest_path: Path,
    clause_gold_path: Path,
    match_threshold: float = 0.55,
    report_path: Path | None = None,
) -> dict[str, Any]:
    metadata = load_run_metadata(result_dir, report_path)
    selection = json.loads(selection_manifest_path.read_text(encoding="utf-8"))
    gold_by_id = _read_jsonl(clause_gold_path)
    canonicalize = _load_normalizer()

    held_out = {
        document["doc_id"]: document
        for document in selection["documents"]
        if document["split"] == "held_out"
    }
    if not held_out:
        raise ValueError("The selection manifest contains no held-out documents to score.")
    run_rows = {
        Path(row["document"]).stem: row
        for row in metadata.get("results", [])
    }
    rows = []
    failure_counts: Counter[str] = Counter()
    total_matches = total_predictions = total_gold = 0
    type_correct = type_applicable = 0
    grounded_quotes = total_quotes = 0
    obligations_with_quotes = total_obligations = 0
    overlap_scores = []
    latencies = []

    for doc_id in sorted(held_out):
        gold = gold_by_id[doc_id]
        run_row = run_rows.get(doc_id, {"status": "failed", "error": "missing result"})
        row = {
            "doc_id": doc_id,
            "status": run_row.get("status", "failed"),
            "error_kind": "",
            "elapsed_seconds": recorded_number(run_row.get("elapsed_seconds")),
            "input_tokens": recorded_number(run_row.get("input_tokens")),
            "output_tokens": recorded_number(run_row.get("output_tokens")),
            "predicted_obligations": 0,
            "gold_clauses": len(gold_obligations(gold)),
            "matched_clauses": 0,
            "discovery_precision": 0.0,
            "discovery_recall": 0.0,
            "discovery_f1": 0.0,
            "type_accuracy": 0.0,
            "quote_groundedness": 0.0,
            "obligation_evidence_coverage": 0.0,
            "mean_quote_overlap": 0.0,
        }
        total_gold += row["gold_clauses"]

        result_path = Path(run_row.get("result_path", result_dir / f"{doc_id}.json"))
        if row["status"] != "success" or not result_path.exists():
            row["status"] = "failed"
            row["error_kind"] = _failure_kind(str(run_row.get("error", "missing result")))
            failure_counts[row["error_kind"]] += 1
            rows.append(row)
            continue

        raw = read_analysis_result(result_path)
        recorded_status = result_status(raw)
        if recorded_status is not None and recorded_status.casefold() != "succeeded":
            row["status"] = "failed"
            row["error_kind"] = "non_success_result"
            failure_counts[row["error_kind"]] += 1
            rows.append(row)
            continue
        prediction = canonicalize(raw, doc_id)
        prediction["source_text"] = gold.get("source_text", "")
        predicted = prediction_obligations(prediction)
        target = gold_obligations(gold)
        matches, _, _ = match_obligations(prediction, gold, match_threshold)
        precision, recall, f1 = f1_score(len(matches), len(predicted), len(target))
        row.update(
            {
                "predicted_obligations": len(predicted),
                "matched_clauses": len(matches),
                "discovery_precision": precision,
                "discovery_recall": recall,
                "discovery_f1": f1,
                "mean_quote_overlap": (
                    statistics.fmean(match[2] for match in matches)
                    if matches
                    else 0.0
                ),
            }
        )

        current_type_correct = 0
        for pred_index, gold_index, overlap in matches:
            gold_type = get_value(target[gold_index], "obligation_type", "ObligationType")
            if gold_type:
                type_applicable += 1
                current_type_correct += (
                    normalize_text(
                        get_value(
                            predicted[pred_index],
                            "ObligationType",
                            "obligation_type",
                        )
                    )
                    == normalize_text(gold_type)
                )
            overlap_scores.append(overlap)
        type_correct += current_type_correct
        row["type_accuracy"] = (
            current_type_correct / len(matches) if matches else 0.0
        )

        source = normalize_quote_text(gold.get("source_text", ""))
        current_quotes = [
            quote
            for obligation in predicted
            for quote in evidence_quotes(obligation)
        ]
        current_grounded = sum(
            normalize_quote_text(quote) in source for quote in current_quotes
        )
        current_with_quotes = sum(bool(evidence_quotes(item)) for item in predicted)
        row["quote_groundedness"] = (
            current_grounded / len(current_quotes) if current_quotes else 0.0
        )
        row["obligation_evidence_coverage"] = (
            current_with_quotes / len(predicted) if predicted else 0.0
        )

        total_matches += len(matches)
        total_predictions += len(predicted)
        grounded_quotes += current_grounded
        total_quotes += len(current_quotes)
        obligations_with_quotes += current_with_quotes
        total_obligations += len(predicted)
        if row["elapsed_seconds"] is not None:
            latencies.append(row["elapsed_seconds"])
        rows.append(row)

    precision, recall, f1 = f1_score(
        total_matches,
        total_predictions,
        total_gold,
    )
    survivor_gold = sum(
        row["gold_clauses"] for row in rows if row["status"] == "success"
    )
    survivor_precision, survivor_recall, survivor_f1 = f1_score(
        total_matches,
        total_predictions,
        survivor_gold,
    )
    success_count = sum(row["status"] == "success" for row in rows)
    token_summary = metadata.get("token_summary", {})
    started_at = metadata.get("started_at", "")
    completed_at = metadata.get("completed_at", "")
    wall_seconds = None
    if started_at and completed_at:
        started = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        completed = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
        wall_seconds = (completed - started).total_seconds()
    return {
        "run": {
            "run_id": metadata.get("run_id", ""),
            "analyzer_id": metadata.get("analyzer_id", ""),
            "api_version": metadata.get("api_version", ""),
            "model": metadata.get("model", "not recorded"),
            "region": metadata.get("region", "not recorded"),
            "started_at": started_at,
            "completed_at": completed_at,
            "wall_seconds": wall_seconds,
            "document_count": len(rows),
            "successful": success_count,
            "failed": len(rows) - success_count,
        },
        "status": "FAIL" if success_count < len(rows) else "PASS",
        "operational": {
            "success_rate": success_count / len(rows) if rows else 0.0,
            "failure_counts": dict(failure_counts),
            "latency_seconds": {
                "mean": statistics.fmean(latencies) if latencies else None,
                "p50": _percentile(latencies, 0.50),
                "p95": _percentile(latencies, 0.95),
                "max": max(latencies, default=None),
            },
            "reported_tokens": {
                "input": recorded_number(token_summary.get("total_input_tokens")),
                "output": recorded_number(token_summary.get("total_output_tokens")),
                "contextualization": recorded_number(
                    token_summary.get("total_contextualization_tokens")
                ),
            },
        },
        "quality_all_20_fail_closed": {
            "clause_discovery_precision": precision,
            "clause_discovery_recall": recall,
            "clause_discovery_f1": f1,
            "survivor_clause_discovery_precision": survivor_precision,
            "survivor_clause_discovery_recall": survivor_recall,
            "survivor_clause_discovery_f1": survivor_f1,
            "matched_clause_count": total_matches,
            "predicted_obligation_count": total_predictions,
            "all_20_gold_clause_count": total_gold,
            "survivor_gold_clause_count": survivor_gold,
            "type_accuracy_on_matches": (
                type_correct / type_applicable if type_applicable else 0.0
            ),
            "type_correct_count": type_correct,
            "type_applicable_count": type_applicable,
            "quote_groundedness_on_completed": (
                grounded_quotes / total_quotes if total_quotes else 0.0
            ),
            "grounded_quote_count": grounded_quotes,
            "quote_count": total_quotes,
            "obligation_evidence_coverage_on_completed": (
                obligations_with_quotes / total_obligations
                if total_obligations
                else 0.0
            ),
            "obligations_with_evidence_count": obligations_with_quotes,
            "completed_obligation_count": total_obligations,
            "mean_quote_overlap_on_matches": (
                statistics.fmean(overlap_scores) if overlap_scores else 0.0
            ),
        },
        "scope_limits": {
            "atomic_party_role_scored": False,
            "atomic_completeness_scored": False,
            "reason": (
                "This report scores mapped CUAD clauses, not atomic party roles "
                "or completeness. It does not consume atomic annotations or "
                "produce a weighted atomic-obligation score."
            ),
        },
        "documents": rows,
    }


def write_report(summary: dict[str, Any], output_prefix: Path) -> None:
    output_prefix.parent.mkdir(parents=True, exist_ok=True)
    output_prefix.with_suffix(".json").write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )
    documents = summary["documents"]
    with output_prefix.with_suffix(".csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=list(documents[0]))
        writer.writeheader()
        writer.writerows(documents)

    run = summary["run"]
    operational = summary["operational"]
    quality = summary["quality_all_20_fail_closed"]
    failures = operational["failure_counts"]
    latency = operational["latency_seconds"]
    tokens = operational["reported_tokens"]
    wall_time = format_measure(run["wall_seconds"], divisor=3600, format_spec=".2f", suffix=" hours")
    total_reported_tokens = (
        sum(tokens.values()) if all(value is not None for value in tokens.values()) else None
    )
    lines = [
        "# Preview agentic API: latency and quality report",
        "",
        f"**Completion status: {summary['status']}**",
        "",
        (
            f"**{run['successful']}/{run['document_count']} "
            f"({operational['success_rate']:.1%})** contracts completed. "
            "Completion status is not a quality or production-readiness verdict."
        ),
        "",
        "## Scope",
        "",
        f"This report evaluates {run['document_count']} held-out CUAD contracts "
        "from the supplied selection manifest against locally saved CU results. "
        "API version, model, and region are reported only when present in run "
        "metadata; no test account or region is assumed. Results do not "
        "characterize other CU APIs, models, regions, schemas, or inputs.",
        "",
        "## Run configuration",
        "",
        "| Setting | Value |",
        "|---|---|",
        f"| Run ID | `{run['run_id']}` |",
        f"| Analyzer | `{run['analyzer_id']}` |",
        f"| Region | `{run['region']}` |",
        f"| API version | `{run['api_version']}` |",
        f"| Model | `{run['model']}` |",
        f"| Documents | {run['document_count']} held-out CUAD contracts |",
        f"| End-to-end wall time | {wall_time} |",
        "",
        "## API latency and reliability",
        "",
        "| Metric | Result |",
        "|---|---:|",
        f"| Successful | {run['successful']}/{run['document_count']} ({operational['success_rate']:.1%}) |",
        f"| Failed | {run['failed']}/{run['document_count']} ({1-operational['success_rate']:.1%}) |",
        f"| Timeouts | {failures.get('timeout', 0)} |",
        f"| Request failures | {failures.get('request_failed', 0)} |",
        f"| Connection resets | {failures.get('connection_reset', 0)} |",
        f"| Mean completed latency | {format_measure(latency['mean'], divisor=60, suffix=' minutes')} |",
        f"| P50 completed latency | {format_measure(latency['p50'], divisor=60, suffix=' minutes')} |",
        f"| Max completed latency | {format_measure(latency['max'], divisor=60, suffix=' minutes')} |",
        f"| End-to-end wall time | {wall_time} |",
        "",
        "### Operational interpretation",
        "",
        "Failure categories come only from saved client error text. A generic "
        "request failure does not establish HTTP 429 or any internal service "
        "cause. Latency summaries include completed documents only; wall time "
        "uses the run's recorded start and completion timestamps. The native CLI "
        "status report does not record timing or usage: absent values remain "
        "null in JSON, blank in CSV, and not recorded here. Console --time and "
        "--usage output is not parsed as report metadata.",
        "",
        "## Overall observed API quality",
        "",
        "| Dimension | Observed result |",
        "|---|---:|",
        f"| Completion reliability | {operational['success_rate']:.1%} |",
        f"| Completed-call mean latency | {format_measure(latency['mean'], divisor=60, suffix=' min')} |",
        f"| Timeout rate | {failures.get('timeout', 0)/run['document_count']:.1%} |",
        f"| Request-failure rate | {failures.get('request_failed', 0)/run['document_count']:.1%} |",
        f"| Connection-reset rate | {failures.get('connection_reset', 0)/run['document_count']:.1%} |",
        f"| End-to-end clause F1 | {quality['clause_discovery_f1']:.1%} |",
        f"| Survivor-only clause F1 | {quality['survivor_clause_discovery_f1']:.1%} |",
        f"| Exact quote groundedness | {quality['quote_groundedness_on_completed']:.1%} |",
        f"| Type accuracy on matches | {quality['type_accuracy_on_matches']:.1%} |",
        "",
        "## Extraction quality",
        "",
        (
            f"Discovery is calculated across all {run['document_count']} contracts. "
            "Failed documents "
            "contribute their CUAD clauses to the denominator and zero predictions, "
            "so the result fails closed rather than measuring only survivors."
        ),
        "",
        "| Metric | Result |",
        "|---|---:|",
        f"| Clause discovery precision | {quality['clause_discovery_precision']:.1%} |",
        f"| Clause discovery recall | {quality['clause_discovery_recall']:.1%} |",
        f"| Clause discovery F1 | {quality['clause_discovery_f1']:.1%} |",
        (
            "| Survivor-only clause discovery F1 | "
            f"{quality['survivor_clause_discovery_f1']:.1%} |"
        ),
        f"| Type accuracy on matched clauses | {quality['type_accuracy_on_matches']:.1%} |",
        f"| Exact quote groundedness (completed only) | {quality['quote_groundedness_on_completed']:.1%} |",
        f"| Obligations with evidence (completed only) | {quality['obligation_evidence_coverage_on_completed']:.1%} |",
        f"| Mean evidence-to-gold overlap | {quality['mean_quote_overlap_on_matches']:.1%} |",
        "",
        "Party-role accuracy and obligation completeness are **not scored**. "
        + summary["scope_limits"]["reason"],
        "",
        "## Reported token usage",
        "",
        (
            f"Recorded input tokens: **{format_measure(tokens['input'], format_spec=',.0f')}**; "
            f"output tokens: **{format_measure(tokens['output'], format_spec=',.0f')}**; "
            f"contextualization tokens: **{format_measure(tokens['contextualization'], format_spec=',.0f')}**; "
            f"total: **{format_measure(total_reported_tokens, format_spec=',.0f')}**. "
            "These are standard returned usage totals, not internal telemetry "
            "or billing totals. Failed requests may omit usage."
        ),
        "",
        "## Interpretation",
        "",
        (
            f"Across all {run['document_count']} contracts, the analyzer matched "
            f"**{quality['matched_clause_count']}/{quality['all_20_gold_clause_count']}** "
            f"mapped CUAD clauses while producing "
            f"**{quality['predicted_obligation_count']}** obligations from "
            f"{run['successful']} completed contracts. Compare fail-closed and "
            "survivor-only scores to distinguish operational gaps from the "
            "quality of completed extractions."
        ),
        "",
        (
            f"**{quality['grounded_quote_count']}/{quality['quote_count']}** quotes "
            "were found in source text. Groundedness alone does not establish "
            "clause discovery, correct party roles, or complete atomic obligations."
        ),
        "",
        "## Recommendation",
        "",
        "Review failed or missing results and the per-contract quality metrics "
        "before additional paid runs. Resolve resource availability, quota, or "
        "client errors using evidence from your own authorized resource. "
        "Obtain cost approval before scale or stability testing. Do not publish "
        "a weighted atomic-obligation score from these clause-only metrics.",
        "",
        "## Per-contract results",
        "",
        "| Contract | Status | Error | Minutes | Predicted | Gold clauses | Matched | F1 |",
        "|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in documents:
        lines.append(
            f"| `{row['doc_id']}` | {row['status']} | {row['error_kind'] or '-'} | "
            f"{format_measure(row['elapsed_seconds'], divisor=60)} | {row['predicted_obligations']} | "
            f"{row['gold_clauses']} | {row['matched_clauses']} | "
            f"{row['discovery_f1']:.1%} |"
        )
    lines.extend(
        [
            "",
            "Machine-readable details are in the adjacent JSON and CSV artifacts.",
            "",
        ]
    )
    output_prefix.with_suffix(".md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-report",
        type=Path,
        help="Official cu analyze --report-file JSON; defaults to results/analyze-report.json.",
    )
    parser.add_argument(
        "--results",
        type=Path,
        default=PROJECT_DIR / "test_results" / "heldout-20",
    )
    parser.add_argument(
        "--selection-manifest",
        type=Path,
        default=PROJECT_DIR / "dataset" / "selection_manifest.json",
    )
    parser.add_argument(
        "--clause-gold",
        type=Path,
        default=PROJECT_DIR / "ground_truth" / "cuad_clause_gold.jsonl",
    )
    parser.add_argument(
        "--output-prefix",
        type=Path,
        default=PROJECT_DIR / "reports" / "heldout_20_quality",
    )
    args = parser.parse_args()
    summary = score_run(
        args.results.resolve(),
        args.selection_manifest.resolve(),
        args.clause_gold.resolve(),
        report_path=args.run_report.resolve() if args.run_report else None,
    )
    write_report(summary, args.output_prefix.resolve())
    print(
        f"{summary['status']}: {summary['run']['successful']}/"
        f"{summary['run']['document_count']} completed; "
        f"F1={summary['quality_all_20_fail_closed']['clause_discovery_f1']:.1%}"
    )


if __name__ == "__main__":
    main()
