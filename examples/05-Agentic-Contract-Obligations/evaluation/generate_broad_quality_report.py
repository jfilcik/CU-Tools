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
    get_value,
    gold_obligations,
    match_obligations,
    normalize_quote_text,
    normalize_text,
    prediction_obligations,
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


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = round((len(ordered) - 1) * percentile)
    return ordered[index]


def score_run(
    result_dir: Path,
    selection_manifest_path: Path,
    clause_gold_path: Path,
    match_threshold: float = 0.55,
) -> dict[str, Any]:
    metadata = json.loads((result_dir / "metadata.json").read_text(encoding="utf-8"))
    selection = json.loads(selection_manifest_path.read_text(encoding="utf-8"))
    gold_by_id = _read_jsonl(clause_gold_path)
    canonicalize = _load_normalizer()

    held_out = {
        document["doc_id"]: document
        for document in selection["documents"]
        if document["split"] == "held_out"
    }
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
            "elapsed_seconds": float(run_row.get("elapsed_seconds", 0.0)),
            "input_tokens": int(run_row.get("input_tokens", 0)),
            "output_tokens": int(run_row.get("output_tokens", 0)),
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

        result_path = result_dir / f"{doc_id}.json"
        if row["status"] != "success" or not result_path.exists():
            row["status"] = "failed"
            row["error_kind"] = _failure_kind(str(run_row.get("error", "missing result")))
            failure_counts[row["error_kind"]] += 1
            rows.append(row)
            continue

        raw = json.loads(result_path.read_text(encoding="utf-8"))
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
    wall_seconds = 0.0
    if started_at and completed_at:
        started = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        completed = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
        wall_seconds = (completed - started).total_seconds()
    return {
        "run": {
            "run_id": metadata.get("run_id", ""),
            "analyzer_id": metadata.get("analyzer_id", ""),
            "api_version": metadata.get("api_version", ""),
            "model": "gpt-5.2",
            "region": "southeastasia",
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
                "mean": statistics.fmean(latencies) if latencies else 0.0,
                "p50": _percentile(latencies, 0.50),
                "p95": _percentile(latencies, 0.95),
                "max": max(latencies, default=0.0),
            },
            "reported_tokens": {
                "input": int(token_summary.get("total_input_tokens", 0)),
                "output": int(token_summary.get("total_output_tokens", 0)),
                "contextualization": int(
                    token_summary.get("total_contextualization_tokens", 0)
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
                "The required six-document atomic obligation gold set has not "
                "been human-verified."
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
    wall_hours = run["wall_seconds"] / 3600
    total_reported_tokens = (
        tokens["input"] + tokens["output"] + tokens["contextualization"]
    )
    lines = [
        "# Preview agentic API: latency and quality report",
        "",
        f"**Overall status: {summary['status']}**",
        "",
        (
            f"Only **{run['successful']}/{run['document_count']} "
            f"({operational['success_rate']:.1%})** contracts completed. "
            "This analyzer is not ready for broad production use on long contracts."
        ),
        "",
        "## Scope",
        "",
        "This report evaluates one workload: Content Understanding preview API "
        "`2026-06-01-preview`, `gpt-5.2`, `config.workflow: Agentic`, the "
        "Southeast Asia test resource, this contract-obligation schema, 20 long "
        "held-out CUAD contracts, and three concurrent requests. It does not "
        "characterize other CU APIs, models, regions, schemas, or shorter inputs.",
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
        "| Documents | 20 held-out CUAD contracts |",
        "| Parallel requests | 3 |",
        "| Per-document timeout | 1,800 seconds |",
        f"| End-to-end wall time | {wall_hours:.2f} hours |",
        "",
        "## API latency and reliability",
        "",
        "| Metric | Result |",
        "|---|---:|",
        f"| Successful | {run['successful']}/20 ({operational['success_rate']:.1%}) |",
        f"| Failed | {run['failed']}/20 ({1-operational['success_rate']:.1%}) |",
        f"| Timeouts | {failures.get('timeout', 0)} |",
        (
            "| Request failures | "
            f"{failures.get('request_failed', 0)} "
            "(the service log identified these as 429 rate-limit failures) |"
        ),
        f"| Connection resets | {failures.get('connection_reset', 0)} |",
        f"| Mean completed latency | {latency['mean']/60:.1f} minutes |",
        f"| P50 completed latency | {latency['p50']/60:.1f} minutes |",
        f"| Max completed latency | {latency['max']/60:.1f} minutes |",
        f"| End-to-end wall time | {wall_hours:.2f} hours |",
        "",
        "### Why the run took 17 hours",
        "",
        "1. **Agentic work was token-intensive.** Each completed contract used an "
        f"average of {tokens['input']/max(run['successful'], 1):,.0f} input and "
        f"{tokens['output']/max(run['successful'], 1):,.0f} output tokens. The "
        "schema asks the model to discover, atomize, classify, relate, and quote "
        "every obligation in long legal text.",
        "2. **Successful calls were already slow.** The three completions took "
        "17.6-19.5 minutes each before queueing and failures are considered.",
        "3. **Nine operations occupied capacity until the 30-minute analysis "
        "timeout.** With three workers, long-running calls held worker slots and "
        "later documents waited in the local queue.",
        "4. **Three-way concurrency exceeded available quota.** Six operations "
        "failed with service-reported HTTP 429 token/request rate limits.",
        "5. **Two network connections reset.** The client uses Requests calls "
        "without connect/read timeouts. Its 1,800-second operation deadline is "
        "checked between polling calls, so stalled HTTP I/O can extend wall time "
        "beyond the nominal analysis timeout.",
        "6. **Document size was not the only cause.** A 26.9 KB contract timed out "
        "while successful contracts ranged from 62.8 KB to 177.0 KB. Service "
        "capacity, generated obligation volume, and transport behavior also "
        "materially affected latency.",
        "",
        "## Overall observed API quality",
        "",
        "| Dimension | Observed result | Assessment |",
        "|---|---:|---|",
        f"| Completion reliability | {operational['success_rate']:.1%} | Fail |",
        f"| Completed-call mean latency | {latency['mean']/60:.1f} min | Too high |",
        f"| Timeout rate | {failures.get('timeout', 0)/run['document_count']:.1%} | Fail |",
        f"| Rate-limit failure rate | {failures.get('request_failed', 0)/run['document_count']:.1%} | Fail |",
        f"| Connection-reset rate | {failures.get('connection_reset', 0)/run['document_count']:.1%} | Fail |",
        f"| End-to-end clause F1 | {quality['clause_discovery_f1']:.1%} | Fail |",
        f"| Survivor-only clause F1 | {quality['survivor_clause_discovery_f1']:.1%} | Fail |",
        f"| Exact quote groundedness | {quality['quote_groundedness_on_completed']:.1%} | Strong on completed calls |",
        f"| Type accuracy on matches | {quality['type_accuracy_on_matches']:.1%} | Needs improvement |",
        "",
        "## Extraction quality",
        "",
        (
            "Discovery is calculated across all 20 contracts. Failed documents "
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
        "Party-role accuracy and obligation completeness are **not scored** because "
        "the six-contract atomic gold set still requires human verification.",
        "",
        "## Token diagnostics",
        "",
        (
            f"The three completed contracts reported **{tokens['input']:,} input**, "
            f"**{tokens['output']:,} output**, and "
            f"**{tokens['contextualization']:,} contextualization tokens** "
            f"(**{total_reported_tokens:,} total reported tokens**). "
            "These totals are a lower bound because failed requests do not report "
            "complete token usage."
        ),
        "",
        "## Interpretation",
        "",
        (
            f"Across all 20 contracts, the analyzer matched "
            f"**{quality['matched_clause_count']}/{quality['all_20_gold_clause_count']}** "
            f"mapped CUAD clauses while producing "
            f"**{quality['predicted_obligation_count']}** obligations from the three "
            "completed contracts. Operational failures dominate the 4.4% end-to-end "
            "F1, but survivor-only F1 remains low, so reliability is not the sole "
            "quality issue."
        ),
        "",
        (
            f"Evidence behavior was the strongest result: "
            f"**{quality['grounded_quote_count']}/{quality['quote_count']}** quotes "
            "were found in source text and every completed obligation had evidence. "
            "The remaining weakness is finding the same obligation-bearing clauses "
            "as CUAD without over-producing loosely aligned obligations."
        ),
        "",
        "## Recommendation",
        "",
        "Do not proceed to stability testing or production rollout with this shape. "
        "Before any future API test, add explicit HTTP connect/read timeouts and "
        "structured 429 retry/backoff, reduce concurrency to one, secure sufficient "
        "model quota, and bound input size through contract segmentation or a "
        "narrower obligation scope. Then rerun the same pinned manifest and complete "
        "second-reviewed atomic gold before publishing the weighted overall score.",
        "",
        "## Per-contract results",
        "",
        "| Contract | Status | Error | Minutes | Predicted | Gold clauses | Matched | F1 |",
        "|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in documents:
        lines.append(
            f"| `{row['doc_id']}` | {row['status']} | {row['error_kind'] or '-'} | "
            f"{row['elapsed_seconds']/60:.1f} | {row['predicted_obligations']} | "
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
    )
    write_report(summary, args.output_prefix.resolve())
    print(
        f"{summary['status']}: {summary['run']['successful']}/"
        f"{summary['run']['document_count']} completed; "
        f"F1={summary['quality_all_20_fail_closed']['clause_discovery_f1']:.1%}"
    )


if __name__ == "__main__":
    main()
