"""Evaluate paired CU obligation runs against the reviewed atomic golden set."""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import unicodedata
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable

PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_GOLD = PROJECT_DIR / "ground_truth" / "golden_obligations.jsonl"
DEFAULT_SAMPLES = PROJECT_DIR / "samples" / "downloaded"
DEFAULT_OUTPUT = PROJECT_DIR / "evaluation" / "output"
MATCH_THRESHOLD = 0.55

VALUE_KEYS = (
    "valueString",
    "valueNumber",
    "valueInteger",
    "valueBoolean",
    "valueDate",
    "valueTime",
    "valueCurrency",
    "valueAddress",
    "valueCountryRegion",
)


def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    return " ".join(text.split()).casefold()


def text_tokens(value: Any) -> list[str]:
    return re.findall(r"\w+", normalize_text(value))


def get_value(record: dict[str, Any], *names: str, default: Any = "") -> Any:
    for name in names:
        if name in record:
            return record[name]
    return default


def unwrap_field(node: Any) -> Any:
    if not isinstance(node, dict):
        return node
    if "valueArray" in node:
        return [unwrap_field(item) for item in node["valueArray"]]
    if "valueObject" in node:
        return {
            name: unwrap_field(value)
            for name, value in node["valueObject"].items()
        }
    for key in VALUE_KEYS:
        if key in node:
            return node[key]
    if "value" in node:
        return node["value"]
    return {
        name: unwrap_field(value)
        for name, value in node.items()
        if name
        not in {"type", "confidence", "source", "spans", "boundingRegions"}
    }


def canonicalize_result(raw: dict[str, Any]) -> dict[str, Any]:
    result = raw.get("result", raw)
    contents = result.get("contents", []) if isinstance(result, dict) else []
    content = contents[0] if contents else result
    fields = content.get("fields", {}) if isinstance(content, dict) else {}
    values = {name: unwrap_field(value) for name, value in fields.items()}
    parties = values.get("Parties", [])
    obligations = values.get("Obligations", [])
    return {
        "parties": parties if isinstance(parties, list) else [],
        "obligations": obligations if isinstance(obligations, list) else [],
    }


def load_gold(path: Path) -> list[dict[str, Any]]:
    records = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len({record["doc_id"] for record in records}) != len(records):
        raise ValueError(f"Duplicate doc_id in golden set: {path}")
    return records


def result_doc_id(document_name: str) -> str:
    return Path(document_name).stem


def load_run(results_dir: Path) -> dict[str, dict[str, Any]]:
    metadata_path = results_dir / "metadata.json"
    if not metadata_path.is_file():
        raise FileNotFoundError(f"Run metadata not found: {metadata_path}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    run = {}
    for item in metadata.get("results", []):
        doc_id = result_doc_id(item.get("document", ""))
        record = {
            "doc_id": doc_id,
            "status": item.get("status", "failed"),
            "error": item.get("error", ""),
            "elapsed_seconds": item.get("elapsed_seconds"),
            "input_tokens": item.get("input_tokens", 0),
            "output_tokens": item.get("output_tokens", 0),
            "contextualization_tokens": item.get("contextualization_tokens", 0),
            "document_pages": item.get("document_pages", 0),
            "prediction": {"parties": [], "obligations": []},
        }
        result_file = item.get("result_file")
        if record["status"] == "success" and result_file:
            raw_path = results_dir / result_file
            if raw_path.is_file():
                raw = json.loads(raw_path.read_text(encoding="utf-8"))
                record["prediction"] = canonicalize_result(raw)
            else:
                record["status"] = "failed"
                record["error"] = f"Missing result file: {raw_path.name}"
        run[doc_id] = record
    return {
        "metadata": metadata,
        "documents": run,
    }


def evidence_quotes(obligation: dict[str, Any]) -> list[str]:
    evidence = get_value(obligation, "Evidence", "evidence", default=[])
    if isinstance(evidence, dict):
        evidence = [evidence]
    quotes = []
    for item in evidence or []:
        if isinstance(item, str):
            quote = item
        elif isinstance(item, dict):
            quote = get_value(item, "ExactQuote", "exact_quote")
        else:
            quote = ""
        if normalize_text(quote):
            quotes.append(str(quote))
    direct = get_value(obligation, "exact_quotes", "ExactQuotes", default=[])
    if isinstance(direct, str):
        direct = [direct]
    quotes.extend(str(quote) for quote in direct if normalize_text(quote))
    return quotes


def quote_similarity(left: str, right: str) -> float:
    left_n = normalize_text(left)
    right_n = normalize_text(right)
    if not left_n or not right_n:
        return 0.0
    if left_n in right_n or right_n in left_n:
        return 1.0
    left_tokens = text_tokens(left)
    right_tokens = text_tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    left_counts = Counter(left_tokens)
    right_counts = Counter(right_tokens)
    overlap = sum((left_counts & right_counts).values())
    precision = overlap / len(left_tokens)
    recall = overlap / len(right_tokens)
    token_f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )
    return max(token_f1, SequenceMatcher(None, left_n, right_n).ratio())


def obligation_similarity(prediction: dict[str, Any], gold: dict[str, Any]) -> float:
    predicted_quotes = evidence_quotes(prediction)
    gold_quotes = evidence_quotes(gold)
    if not predicted_quotes or not gold_quotes:
        return 0.0
    return max(
        quote_similarity(predicted_quote, gold_quote)
        for predicted_quote in predicted_quotes
        for gold_quote in gold_quotes
    )


def match_obligations(
    predicted: list[dict[str, Any]],
    gold: list[dict[str, Any]],
    party_mapping: dict[str, str] | None = None,
    threshold: float = MATCH_THRESHOLD,
) -> tuple[list[tuple[int, int, float]], list[int], list[int]]:
    party_mapping = party_mapping or {}

    def tie_breaker(prediction: dict[str, Any], target: dict[str, Any]) -> float:
        score = 0.0
        predicted_obligor = mapped_party_id(
            get_value(prediction, "ObligorPartyId", "obligor_party_id"),
            party_mapping,
        )
        if predicted_obligor and predicted_obligor == target["obligor_party_id"]:
            score += 0.02
        if normalize_text(
            get_value(prediction, "ObligationType", "obligation_type")
        ) == normalize_text(target["obligation_type"]):
            score += 0.01
        return score

    candidates = sorted(
        (
            (
                obligation_similarity(prediction, target),
                tie_breaker(prediction, target),
                pred_index,
                gold_index,
            )
            for pred_index, prediction in enumerate(predicted)
            for gold_index, target in enumerate(gold)
        ),
        reverse=True,
    )
    matches = []
    used_predictions: set[int] = set()
    used_gold: set[int] = set()
    for score, _tie, pred_index, gold_index in candidates:
        if (
            score < threshold
            or pred_index in used_predictions
            or gold_index in used_gold
        ):
            continue
        matches.append((pred_index, gold_index, score))
        used_predictions.add(pred_index)
        used_gold.add(gold_index)
    return (
        sorted(matches),
        [index for index in range(len(predicted)) if index not in used_predictions],
        [index for index in range(len(gold)) if index not in used_gold],
    )


def scalar_similarity(left: Any, right: Any) -> float:
    left_n = normalize_text(left)
    right_n = normalize_text(right)
    if not left_n and not right_n:
        return 1.0
    if not left_n or not right_n:
        return 0.0
    if left_n in right_n or right_n in left_n:
        return min(len(left_n), len(right_n)) / max(len(left_n), len(right_n))
    return SequenceMatcher(None, left_n, right_n).ratio()


def party_names(party: dict[str, Any]) -> list[str]:
    aliases = get_value(party, "Aliases", "aliases", default=[])
    if isinstance(aliases, str):
        aliases = [aliases]
    legal_name = get_value(party, "LegalName", "legal_name")
    return [str(value) for value in [legal_name, *aliases] if normalize_text(value)]


def map_parties(
    predicted: list[dict[str, Any]],
    gold: list[dict[str, Any]],
) -> dict[str, str]:
    candidates = []
    for predicted_party in predicted:
        predicted_id = str(
            get_value(predicted_party, "PartyId", "party_id", default="")
        )
        for gold_party in gold:
            gold_id = str(get_value(gold_party, "party_id", "PartyId", default=""))
            score = max(
                (
                    scalar_similarity(predicted_name, gold_name)
                    for predicted_name in party_names(predicted_party)
                    for gold_name in party_names(gold_party)
                ),
                default=0.0,
            )
            candidates.append((score, predicted_id, gold_id))
    mapping = {}
    used_gold = set()
    for score, predicted_id, gold_id in sorted(candidates, reverse=True):
        if (
            score < 0.6
            or not predicted_id
            or predicted_id in mapping
            or gold_id in used_gold
        ):
            continue
        mapping[predicted_id] = gold_id
        used_gold.add(gold_id)
    return mapping


def mapped_party_id(value: Any, mapping: dict[str, str]) -> str:
    return mapping.get(str(value or ""), "")


def mapped_party_ids(value: Any, mapping: dict[str, str]) -> set[str]:
    values = value if isinstance(value, list) else ([] if value in (None, "") else [value])
    return {mapped for item in values if (mapped := mapped_party_id(item, mapping))}


def grounded_quote(quote: str, source_text: str) -> bool:
    return bool(normalize_text(quote)) and normalize_text(quote) in normalize_text(
        source_text
    )


def duplicate_count(obligations: list[dict[str, Any]]) -> int:
    signatures = []
    for obligation in obligations:
        summary = normalize_text(
            get_value(obligation, "BusinessSummary", "business_summary", "action")
        )
        quote = normalize_text(evidence_quotes(obligation)[0]) if evidence_quotes(obligation) else ""
        obligor = normalize_text(
            get_value(obligation, "ObligorPartyId", "obligor_party_id")
        )
        signatures.append((obligor, summary, quote))
    counts = Counter(signature for signature in signatures if any(signature))
    return sum(count - 1 for count in counts.values() if count > 1)


def safe_rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(fraction * len(ordered)) - 1))
    return ordered[index]


def evaluate_document(
    gold: dict[str, Any],
    run_record: dict[str, Any] | None,
    source_text: str,
) -> dict[str, Any]:
    predicted = (
        run_record["prediction"]["obligations"]
        if run_record and run_record["status"] == "success"
        else []
    )
    gold_obligations = gold["obligations"]
    predicted_parties = (
        run_record["prediction"]["parties"]
        if run_record and run_record["status"] == "success"
        else []
    )
    party_mapping = map_parties(predicted_parties, gold["parties"])
    matches, false_positive_indices, false_negative_indices = match_obligations(
        predicted,
        gold_obligations,
        party_mapping,
    )

    matched_details = []
    type_correct = nature_correct = obligor_correct = obligee_correct = 0
    post_termination_correct = 0
    post_termination_present_count = 0
    required_correct = required_total = 0
    summary_scores = []
    alignment_scores = []
    predicted_id_to_gold_id = {
        str(
            get_value(
                predicted[pred_index],
                "ObligationId",
                "obligation_id",
                default="",
            )
        ): gold_obligations[gold_index]["obligation_id"]
        for pred_index, gold_index, _alignment in matches
        if get_value(
            predicted[pred_index],
            "ObligationId",
            "obligation_id",
            default="",
        )
    }
    for pred_index, gold_index, alignment in matches:
        pred = predicted[pred_index]
        target = gold_obligations[gold_index]
        pred_type = get_value(pred, "ObligationType", "obligation_type")
        pred_nature = get_value(pred, "Nature", "nature")
        type_match = normalize_text(pred_type) == normalize_text(
            target["obligation_type"]
        )
        nature_match = normalize_text(pred_nature) == normalize_text(target["nature"])
        pred_obligor = mapped_party_id(
            get_value(pred, "ObligorPartyId", "obligor_party_id"),
            party_mapping,
        )
        obligor_match = pred_obligor == target["obligor_party_id"]
        pred_obligees = mapped_party_ids(
            get_value(pred, "ObligeePartyIds", "obligee_party_ids", default=[]),
            party_mapping,
        )
        obligee_match = pred_obligees == set(target["obligee_party_ids"])
        predicted_post_termination = get_value(
            pred,
            "IsPostTermination",
            "is_post_termination",
            default=None,
        )
        post_termination_present = isinstance(predicted_post_termination, bool)
        post_termination_match = (
            post_termination_present
            and predicted_post_termination == target["is_post_termination"]
        )
        type_correct += int(type_match)
        nature_correct += int(nature_match)
        obligor_correct += int(obligor_match)
        obligee_correct += int(obligee_match)
        post_termination_present_count += int(post_termination_present)
        post_termination_correct += int(post_termination_match)
        alignment_scores.append(alignment)

        summary = get_value(pred, "BusinessSummary", "business_summary")
        summary_score = max(
            scalar_similarity(summary, target["business_summary"]),
            scalar_similarity(summary, target["action"]),
        )
        summary_scores.append(summary_score)

        detail_scores = {}
        for field in target.get("required_fields", []):
            if field == "related_obligation_ids":
                predicted_related = get_value(
                    pred,
                    "RelatedObligationIds",
                    "related_obligation_ids",
                    default=[],
                )
                if not isinstance(predicted_related, list):
                    predicted_related = [predicted_related]
                mapped_related = {
                    predicted_id_to_gold_id.get(str(value), "")
                    for value in predicted_related
                    if predicted_id_to_gold_id.get(str(value), "")
                }
                score = float(mapped_related == set(target[field]))
            else:
                predicted_value = get_value(
                    pred,
                    "".join(part.title() for part in field.split("_")),
                    field,
                )
                score = scalar_similarity(predicted_value, target[field])
            detail_scores[field] = score
            required_total += 1
            required_correct += int(score >= 0.55)
        matched_details.append(
            {
                "prediction_index": pred_index,
                "gold_obligation_id": target["obligation_id"],
                "quote_alignment": round(alignment, 4),
                "type_correct": type_match,
                "nature_correct": nature_match,
                "obligor_correct": obligor_match,
                "obligee_correct": obligee_match,
                "post_termination_correct": post_termination_match,
                "post_termination_present": post_termination_present,
                "summary_similarity": round(summary_score, 4),
                "required_detail_scores": detail_scores,
            }
        )

    all_quotes = [
        quote for obligation in predicted for quote in evidence_quotes(obligation)
    ]
    grounded = sum(grounded_quote(quote, source_text) for quote in all_quotes)
    duplicates = duplicate_count(predicted)
    return {
        "doc_id": gold["doc_id"],
        "status": run_record["status"] if run_record else "failed",
        "error": run_record.get("error", "") if run_record else "No run record",
        "gold_count": len(gold_obligations),
        "predicted_count": len(predicted),
        "matched_count": len(matches),
        "false_positive_count": len(false_positive_indices),
        "false_negative_count": len(false_negative_indices),
        "precision": safe_rate(len(matches), len(predicted)),
        "recall": safe_rate(len(matches), len(gold_obligations)),
        "quote_groundedness": safe_rate(grounded, len(all_quotes)),
        "duplicate_count": duplicates,
        "type_correct": type_correct,
        "nature_correct": nature_correct,
        "obligor_correct": obligor_correct,
        "obligee_correct": obligee_correct,
        "post_termination_correct": post_termination_correct,
        "post_termination_present": post_termination_present_count,
        "required_detail_correct": required_correct,
        "required_detail_total": required_total,
        "summary_score_total": sum(summary_scores),
        "quote_alignment_total": sum(alignment_scores),
        "quote_count": len(all_quotes),
        "grounded_quote_count": grounded,
        "elapsed_seconds": run_record.get("elapsed_seconds") if run_record else None,
        "input_tokens": run_record.get("input_tokens", 0) if run_record else 0,
        "output_tokens": run_record.get("output_tokens", 0) if run_record else 0,
        "matched_details": matched_details,
        "false_positives": [
            {
                "index": index,
                "summary": get_value(
                    predicted[index], "BusinessSummary", "business_summary", "action"
                ),
                "quotes": evidence_quotes(predicted[index]),
            }
            for index in false_positive_indices
        ],
        "false_negatives": [
            {
                "obligation_id": gold_obligations[index]["obligation_id"],
                "business_summary": gold_obligations[index]["business_summary"],
                "exact_quotes": gold_obligations[index]["exact_quotes"],
            }
            for index in false_negative_indices
        ],
    }


def aggregate(mode: str, documents: list[dict[str, Any]], metadata: dict[str, Any]) -> dict[str, Any]:
    totals = Counter()
    for document in documents:
        for key in (
            "gold_count",
            "predicted_count",
            "matched_count",
            "false_positive_count",
            "false_negative_count",
            "duplicate_count",
            "type_correct",
            "nature_correct",
            "obligor_correct",
            "obligee_correct",
            "post_termination_correct",
            "post_termination_present",
            "required_detail_correct",
            "required_detail_total",
            "quote_count",
            "grounded_quote_count",
            "input_tokens",
            "output_tokens",
        ):
            totals[key] += document[key]
    precision = safe_rate(totals["matched_count"], totals["predicted_count"])
    recall = safe_rate(totals["matched_count"], totals["gold_count"])
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )
    completed = [doc for doc in documents if doc["status"] == "success"]
    latencies = [
        float(doc["elapsed_seconds"])
        for doc in completed
        if isinstance(doc["elapsed_seconds"], (int, float))
    ]
    matched_count = totals["matched_count"]
    return {
        "mode": mode,
        "run_id": metadata.get("run_id", ""),
        "api_version": metadata.get("api_version", ""),
        "analyzer_id": metadata.get("analyzer_id", ""),
        "document_count": len(documents),
        "completed_count": len(completed),
        "completion_rate": safe_rate(len(completed), len(documents)),
        "gold_obligations": totals["gold_count"],
        "predicted_obligations": totals["predicted_count"],
        "matched_obligations": matched_count,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "type_accuracy": safe_rate(totals["type_correct"], matched_count),
        "nature_accuracy": safe_rate(totals["nature_correct"], matched_count),
        "obligor_accuracy": safe_rate(totals["obligor_correct"], matched_count),
        "obligee_accuracy": safe_rate(totals["obligee_correct"], matched_count),
        "post_termination_accuracy": safe_rate(
            totals["post_termination_correct"], matched_count
        ),
        "post_termination_coverage": safe_rate(
            totals["post_termination_present"], matched_count
        ),
        "required_detail_accuracy": safe_rate(
            totals["required_detail_correct"], totals["required_detail_total"]
        ),
        "summary_similarity": safe_rate(
            sum(document["summary_score_total"] for document in documents),
            matched_count,
        ),
        "quote_alignment": safe_rate(
            sum(document["quote_alignment_total"] for document in documents),
            matched_count,
        ),
        "quote_groundedness": safe_rate(
            totals["grounded_quote_count"], totals["quote_count"]
        ),
        "duplicate_count": totals["duplicate_count"],
        "duplicate_rate": safe_rate(
            totals["duplicate_count"], totals["predicted_count"]
        ),
        "total_input_tokens": totals["input_tokens"],
        "total_output_tokens": totals["output_tokens"],
        "total_tokens": totals["input_tokens"] + totals["output_tokens"],
        "latency_seconds": {
            "mean": statistics.fmean(latencies) if latencies else 0.0,
            "p50": statistics.median(latencies) if latencies else 0.0,
            "p95": percentile(latencies, 0.95),
            "max": max(latencies, default=0.0),
            "total": sum(latencies),
        },
        "documents": documents,
    }


def evaluate_mode(
    mode: str,
    gold_records: list[dict[str, Any]],
    samples_dir: Path,
    results_dir: Path,
) -> dict[str, Any]:
    run = load_run(results_dir)
    documents = []
    for gold in gold_records:
        source_path = samples_dir / f"{gold['doc_id']}.txt"
        source_text = source_path.read_text(encoding="utf-8")
        documents.append(
            evaluate_document(
                gold,
                run["documents"].get(gold["doc_id"]),
                source_text,
            )
        )
    return aggregate(mode, documents, run["metadata"])


def fmt_percent(value: float) -> str:
    return f"{value:.1%}"


def fmt_number(value: float) -> str:
    return f"{value:,.1f}"


def comparison_conclusion(standard: dict[str, Any], agentic: dict[str, Any]) -> str:
    delta = agentic["f1"] - standard["f1"]
    if agentic["completion_rate"] < 0.8:
        return (
            "Agentic is not yet a reliable demo path for this benchmark because fewer "
            "than 80% of documents completed, regardless of survivor-only quality."
        )
    if agentic["f1"] < 0.7:
        return (
            "Agentic does not yet reach the 70% obligation-discovery F1 readiness bar "
            "for this curated use case."
        )
    if delta >= 0.1:
        return (
            "Agentic shows a material obligation-discovery advantage over Standard "
            f"on this golden set ({delta:+.1%} F1), subject to the latency and token tradeoff."
        )
    return (
        "Agentic does not show a material (10-point) obligation-discovery advantage "
        f"over Standard on this golden set ({delta:+.1%} F1)."
    )


def write_report(
    standard: dict[str, Any],
    agentic: dict[str, Any],
    output_path: Path,
) -> None:
    delta = agentic["f1"] - standard["f1"]
    selection = json.loads(
        (PROJECT_DIR / "dataset" / "selection_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    review = json.loads(
        (PROJECT_DIR / "ground_truth" / "review_summary.json").read_text(
            encoding="utf-8"
        )
    )
    qualitative_path = PROJECT_DIR / "evaluation" / "qualitative_review.json"
    qualitative = (
        json.loads(qualitative_path.read_text(encoding="utf-8"))
        if qualitative_path.is_file()
        else {}
    )
    latency_ratio = (
        agentic["latency_seconds"]["mean"] / standard["latency_seconds"]["mean"]
        if standard["latency_seconds"]["mean"]
        else 0.0
    )
    token_ratio = (
        agentic["total_tokens"] / standard["total_tokens"]
        if standard["total_tokens"]
        else 0.0
    )
    qualitative_lines = []
    if qualitative:
        verdict = qualitative["verdict"]
        qualitative_lines = [
            "## Independent qualitative review",
            "",
            f"**{verdict['headline']}**",
            "",
            f"- Demo: {verdict['demo_assessment']}",
            f"- Production: {verdict['production_assessment']}",
            "",
            *[
                f"- {finding}"
                for finding in qualitative.get("report_findings", [])
            ],
            "",
            "See [`evaluation/qualitative_review.md`](evaluation/qualitative_review.md) "
            "for the source-level review of every Agentic miss and unmatched prediction.",
            "",
        ]
    lines = [
        "# Standard vs. Agentic contract-obligation benchmark",
        "",
        "**Result:** " + comparison_conclusion(standard, agentic),
        "",
        "## Benchmark design",
        "",
        "- Test resource region: Southeast Asia.",
        f"- Standard run: `{standard['run_id']}` ({standard['api_version']}).",
        f"- Agentic run: `{agentic['run_id']}` ({agentic['api_version']}).",
        "- Golden set: 10 independently annotated short CUAD contracts.",
        f"- Gold obligations: {standard['gold_obligations']}.",
        "- Standard: GA API with `gpt-4.1` and no Agentic workflow selector.",
        "- Agentic: `2026-06-01-preview`, `gpt-5.2`, and `config.workflow: \"Agentic\"`.",
        "- The field schema, source documents, matching threshold, and fail-closed scoring are identical.",
        "- Failed documents retain all gold obligations and contribute zero predictions.",
        "",
        "### Golden-set composition",
        "",
        "| Contract type | Words | Gold obligations |",
        "|---|---:|---:|",
    ]
    review_counts = review["per_document_obligation_counts"]
    for document in selection["documents"]:
        lines.append(
            f"| {document['agreement_type']} | {document['expected_words']} | "
            f"{review_counts[document['doc_id']]} |"
        )
    removed_count = sum(
        batch["removed"] for batch in review["changes_from_drafts"].values()
    )
    added_count = sum(
        batch["added"] for batch in review["changes_from_drafts"].values()
    )
    corrected_count = sum(
        batch["materially_corrected"]
        for batch in review["changes_from_drafts"].values()
    )
    lines.extend(
        [
            "",
            f"The adjudicator finalized {review['total_obligations']} obligations, "
            f"removing {removed_count}, adding {added_count}, and materially correcting "
            f"{corrected_count} first-pass records. All hashes, offsets, IDs, references, "
            "enumerations, and duplicate checks passed.",
            "",
            "## Headline comparison",
            "",
            "| Metric | Standard | Agentic | Agentic delta |",
            "|---|---:|---:|---:|",
        ]
    )
    for label, key in (
        ("Completion rate", "completion_rate"),
        ("Precision", "precision"),
        ("Recall", "recall"),
        ("Obligation F1", "f1"),
        ("Quote groundedness", "quote_groundedness"),
        ("Obligor accuracy", "obligor_accuracy"),
        ("Obligee accuracy", "obligee_accuracy"),
        ("Post-termination accuracy", "post_termination_accuracy"),
        ("Post-termination field coverage", "post_termination_coverage"),
        ("Type accuracy", "type_accuracy"),
        ("Nature accuracy", "nature_accuracy"),
        ("Required-detail accuracy", "required_detail_accuracy"),
    ):
        lines.append(
            f"| {label} | {fmt_percent(standard[key])} | "
            f"{fmt_percent(agentic[key])} | {agentic[key] - standard[key]:+.1%} |"
        )
    lines.extend(
        [
            "",
            f"Agentic obligation-F1 delta: **{delta:+.1%}**.",
            "",
            "## Cost and latency",
            "",
            "| Metric | Standard | Agentic |",
            "|---|---:|---:|",
            f"| Completed documents | {standard['completed_count']}/10 | {agentic['completed_count']}/10 |",
            f"| Mean latency | {fmt_number(standard['latency_seconds']['mean'])} s | {fmt_number(agentic['latency_seconds']['mean'])} s |",
            f"| P95 latency | {fmt_number(standard['latency_seconds']['p95'])} s | {fmt_number(agentic['latency_seconds']['p95'])} s |",
            f"| Active execution time | {fmt_number(standard['latency_seconds']['total'] / 60)} min | {fmt_number(agentic['latency_seconds']['total'] / 60)} min |",
            f"| Input tokens | {standard['total_input_tokens']:,} | {agentic['total_input_tokens']:,} |",
            f"| Output tokens | {standard['total_output_tokens']:,} | {agentic['total_output_tokens']:,} |",
            f"| Duplicate obligations | {standard['duplicate_count']} | {agentic['duplicate_count']} |",
            f"| Agentic latency multiplier | - | {latency_ratio:.1f}x |",
            f"| Agentic token multiplier | - | {token_ratio:.1f}x |",
            "",
            "Dollar cost is intentionally not estimated because the repository's "
            "cost model does not define a verified `gpt-5.2` preview price.",
            "",
            "## Per-contract discovery",
            "",
            "| Contract | Gold | Standard matched/predicted | Agentic matched/predicted | Standard F1 | Agentic F1 |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    standard_docs = {doc["doc_id"]: doc for doc in standard["documents"]}
    agentic_docs = {doc["doc_id"]: doc for doc in agentic["documents"]}
    for doc_id, standard_doc in standard_docs.items():
        agentic_doc = agentic_docs[doc_id]
        standard_p = standard_doc["precision"]
        standard_r = standard_doc["recall"]
        standard_f1 = (
            2 * standard_p * standard_r / (standard_p + standard_r)
            if standard_p + standard_r
            else 0.0
        )
        agentic_p = agentic_doc["precision"]
        agentic_r = agentic_doc["recall"]
        agentic_f1 = (
            2 * agentic_p * agentic_r / (agentic_p + agentic_r)
            if agentic_p + agentic_r
            else 0.0
        )
        lines.append(
            f"| `{doc_id}` | {standard_doc['gold_count']} | "
            f"{standard_doc['matched_count']}/{standard_doc['predicted_count']} | "
            f"{agentic_doc['matched_count']}/{agentic_doc['predicted_count']} | "
            f"{fmt_percent(standard_f1)} | {fmt_percent(agentic_f1)} |"
        )
    lines.extend(
        [
            "",
            "## Readiness gates",
            "",
            "| Gate | Target | Agentic result | Status |",
            "|---|---:|---:|---|",
            f"| Completion | >=80% | {fmt_percent(agentic['completion_rate'])} | {'PASS' if agentic['completion_rate'] >= 0.8 else 'FAIL'} |",
            f"| Obligation discovery F1 | >=70% | {fmt_percent(agentic['f1'])} | {'PASS' if agentic['f1'] >= 0.7 else 'FAIL'} |",
            f"| Quote groundedness | >=90% | {fmt_percent(agentic['quote_groundedness'])} | {'PASS' if agentic['quote_groundedness'] >= 0.9 else 'FAIL'} |",
            f"| Material gain over Standard | >=10 points F1 | {delta:+.1%} | {'PASS' if delta >= 0.1 else 'FAIL'} |",
            "",
            "These are demo-readiness gates for this example, not service SLAs or "
            "universal legal-extraction thresholds.",
            "",
            "## Error profile",
            "",
            f"- Standard missed {sum(doc['false_negative_count'] for doc in standard['documents'])} "
            f"gold obligations and emitted {sum(doc['false_positive_count'] for doc in standard['documents'])} "
            "unmatched predictions.",
            f"- Agentic missed {sum(doc['false_negative_count'] for doc in agentic['documents'])} "
            f"gold obligations and emitted {sum(doc['false_positive_count'] for doc in agentic['documents'])} "
            "unmatched predictions.",
            f"- Standard required-detail accuracy was {fmt_percent(standard['required_detail_accuracy'])}; "
            f"Agentic required-detail accuracy was {fmt_percent(agentic['required_detail_accuracy'])}.",
            "",
            *qualitative_lines,
            "## Interpretation",
            "",
            "This benchmark measures broad atomic obligations, not CUAD's narrower "
            "31-category clause taxonomy. Evidence overlap drives one-to-one discovery "
            "matching; party, type, nature, details, duplicates, source groundedness, "
            "latency, and token usage are reported separately.",
            "",
            "The comparison is a product-mode comparison, not an isolated model ablation: "
            "Standard uses the supported GA model/API combination while Agentic uses the "
            "verified preview model/API combination.",
            "",
            "### Annotation limitations",
            "",
            *[f"- {ambiguity}" for ambiguity in review["known_ambiguities"]],
            "",
            "The golden set is model-assisted and independently adjudicated, but it still "
            "requires qualified legal-human review before use as an external or contractual "
            "benchmark.",
            "",
        ]
    )
    output_path.write_text("\n".join(lines), encoding="utf-8")


def write_json(data: dict[str, Any], path: Path) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--samples", type=Path, default=DEFAULT_SAMPLES)
    parser.add_argument("--standard-results", type=Path, required=True)
    parser.add_argument("--agentic-results", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--report",
        type=Path,
        default=PROJECT_DIR / "REPORT.md",
    )
    args = parser.parse_args()
    gold_records = load_gold(args.gold.resolve())
    output_dir = args.output.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    standard = evaluate_mode(
        "Standard",
        gold_records,
        args.samples.resolve(),
        args.standard_results.resolve(),
    )
    agentic = evaluate_mode(
        "Agentic",
        gold_records,
        args.samples.resolve(),
        args.agentic_results.resolve(),
    )
    write_json(standard, output_dir / "standard_metrics.json")
    write_json(agentic, output_dir / "agentic_metrics.json")
    write_report(standard, agentic, args.report.resolve())
    print(
        f"Standard F1={standard['f1']:.1%}; Agentic F1={agentic['f1']:.1%}; "
        f"report={args.report.resolve()}"
    )


if __name__ == "__main__":
    main()
