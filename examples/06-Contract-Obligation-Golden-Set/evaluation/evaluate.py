"""Evaluate paired CU obligation runs against the reviewed atomic golden set."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
import sys
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any
from uuid import uuid4

PROJECT_DIR = Path(__file__).resolve().parents[1]
RESULT_TOOLS = PROJECT_DIR.parents[1] / "tools" / "cu-results-export"
if str(RESULT_TOOLS) not in sys.path:
    sys.path.insert(0, str(RESULT_TOOLS))

from cu_result_io import (  # noqa: E402
    ResultFormatError,
    decoded_value,
    load_results,
    result_payload,
    result_status,
    result_usage,
)

DEFAULT_GOLD = PROJECT_DIR / "ground_truth" / "golden_obligations.jsonl"
DEFAULT_SAMPLES = PROJECT_DIR / "samples" / "downloaded"
DEFAULT_OUTPUT = PROJECT_DIR / "evaluation" / "output"
MATCH_THRESHOLD = 0.55
MEASUREMENTS = (
    "elapsed_seconds", "input_tokens", "output_tokens",
    "contextualization_tokens", "document_pages",
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
    return decoded_value(node)


def canonicalize_result(raw: dict[str, Any]) -> dict[str, Any]:
    result = result_payload(raw)
    if "contents" in result:
        contents = result["contents"]
        if len(contents) != 1 or "fields" in result:
            raise ResultFormatError("Expected one contract content entry per result")
        fields = contents[0].get("fields", {})
    else:
        fields = result.get("fields", {})
    if not {"Parties", "Obligations"} & fields.keys():
        raise ResultFormatError("Result has no Parties or Obligations fields")
    values = {name: unwrap_field(value) for name, value in fields.items()}
    for name in ("Parties", "Obligations"):
        value = values.get(name, [])
        if value is None:
            values[name] = []
        elif not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
            raise ResultFormatError(f"{name} must be an array of objects or null")
    return {
        "parties": values.get("Parties", []),
        "obligations": values.get("Obligations", []),
    }


def load_gold(path: Path) -> list[dict[str, Any]]:
    records = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    expected_sources(records)
    return records


def relative_identity(value: Any, root: Path | None = None) -> str:
    """Keep the full input-relative path and extension; never match by stem."""
    if not isinstance(value, str) or not value.strip():
        raise ResultFormatError("Input identity must be a nonempty path")
    text = value.replace("\\", "/")
    path = PurePosixPath(text)
    if ".." in path.parts or ":" in text and not PureWindowsPath(text).drive:
        raise ResultFormatError(f"Unsafe input identity: {value}")
    absolute = path.is_absolute() or bool(PureWindowsPath(text).drive)
    if absolute:
        if root is None:
            raise ResultFormatError(f"Expected a relative input identity: {value}")
        try:
            if PureWindowsPath(text).drive:
                path = PurePosixPath(
                    PureWindowsPath(text).relative_to(PureWindowsPath(root.resolve())).as_posix()
                )
            else:
                path = path.relative_to(PurePosixPath(root.resolve().as_posix()))
        except ValueError as exc:
            raise ResultFormatError(f"Input is outside {root}: {value}") from exc
    if not path.parts or path.is_absolute():
        raise ResultFormatError(f"Invalid input identity: {value}")
    return path.as_posix()


def expected_sources(gold_records: list[dict[str, Any]]) -> dict[str, str]:
    if not gold_records:
        raise ValueError("The golden set must not be empty")
    sources = {}
    seen_ids = set()
    for gold in gold_records:
        doc_id = relative_identity(gold["doc_id"])
        source = relative_identity(gold.get("source_file", f"{doc_id}.txt"))
        if doc_id.casefold() in seen_ids or source.casefold() in sources:
            raise ValueError(f"Duplicate golden-set document or source: {doc_id}")
        seen_ids.add(doc_id.casefold())
        sources[source.casefold()] = gold["doc_id"]
    return sources


def source_identity(value: Any, root: Path, expected: dict[str, str]) -> str:
    source = relative_identity(value, root)
    if source.casefold() not in expected:
        # CLI reports may record a repository-relative path, rather than an
        # absolute path or a path relative to --source.
        candidate = Path(str(value).replace("\\", "/")).resolve()
        source = relative_identity(str(candidate), root)
    if source.casefold() not in expected:
        raise ResultFormatError(f"Unrelated result input: {value}")
    return source


def output_identity(value: Any, root: Path) -> str:
    relative = relative_identity(value, root)
    try:
        candidate = Path(str(value).replace("\\", "/")).resolve().relative_to(root.resolve())
    except ValueError:
        return relative
    return relative_identity(candidate.as_posix())


def measurement(value: Any, name: str) -> int | float | None:
    if value is None:
        return None
    if (
        isinstance(value, bool) or not isinstance(value, (int, float))
        or not math.isfinite(value) or value < 0
        or name != "elapsed_seconds" and value != int(value)
    ):
        raise ResultFormatError(f"Invalid numeric measurement {name}: {value!r}")
    return value


def measurements(raw: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    metadata = raw.get("_metadata", {})
    values = {
        name: measurement(item.get(name, metadata.get(name)), name)
        for name in MEASUREMENTS
    }
    usage = result_usage(raw) or {}
    tokens = usage.get("tokens")
    if tokens is not None:
        if not isinstance(tokens, dict):
            raise ResultFormatError("usage.tokens must be an object")
        for direction in ("input", "output"):
            entries = [
                measurement(value, f"{direction}_tokens")
                for key, value in tokens.items() if key.endswith(f"-{direction}")
            ]
            if values[f"{direction}_tokens"] is None and entries and None not in entries:
                values[f"{direction}_tokens"] = sum(entries)
    for target, source in (
        ("contextualization_tokens", "contextualizationTokens"),
        ("document_pages", "documentPages"),
    ):
        if values[target] is None:
            values[target] = measurement(usage.get(source), target)
    return values


def load_run(
    results_dir: Path,
    gold_records: list[dict[str, Any]],
    samples_dir: Path,
    report_path: Path | None = None,
) -> dict[str, Any]:
    """Read native results plus an optional CLI report, or a saved legacy run."""
    expected = expected_sources(gold_records)
    loaded = load_results(results_dir)
    if not results_dir.is_dir():
        raise ResultFormatError("A benchmark run must be a result directory")
    legacy_path = results_dir / "metadata.json"
    native_path = report_path or results_dir / "report.json"
    if legacy_path.is_file() and (report_path is not None or native_path.is_file()):
        raise ResultFormatError("Do not mix a legacy run manifest with a CLI report")
    manifest_path = legacy_path if legacy_path.is_file() else native_path
    metadata: dict[str, Any] = {}
    if manifest_path.is_file():
        metadata = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        if not isinstance(metadata, dict) or not isinstance(metadata.get("results"), list):
            raise ResultFormatError(f"Invalid run manifest: {manifest_path}")
        if manifest_path != legacy_path and metadata.get("schema") != "cu-cli/analyze-report/v1":
            raise ResultFormatError(f"Unrecognized CLI report schema: {manifest_path}")
        if manifest_path != legacy_path:
            if metadata.get("result_view") != "full":
                raise ResultFormatError("CLI report must describe --json full results")
            counts = metadata.get("counts")
            if not isinstance(counts, dict) or any(not isinstance(row, dict) for row in metadata["results"]):
                raise ResultFormatError("Invalid CLI report counts or rows")
            expected_counts = {
                state: sum(row.get("status") == state for row in metadata["results"])
                for state in ("succeeded", "failed", "skipped")
            }
            expected_counts["total"] = len(metadata["results"])
            if any(type(counts.get(key)) is not int or counts[key] != value for key, value in expected_counts.items()):
                raise ResultFormatError("CLI report counts disagree with its input rows")
    elif report_path is not None:
        raise FileNotFoundError(f"CLI report not found: {report_path}")

    legacy = manifest_path == legacy_path
    rows = {}
    files = {}
    for item in metadata.get("results", []):
        if not isinstance(item, dict):
            raise ResultFormatError("Run manifest rows must be objects")
        source = source_identity(item.get("document" if legacy else "input"), samples_dir, expected)
        doc_id = expected[source.casefold()]
        if doc_id in rows:
            raise ResultFormatError(f"Duplicate manifest input: {source}")
        allowed = {"success", "failed"} if legacy else {"succeeded", "failed", "skipped"}
        if item.get("status") not in allowed:
            raise ResultFormatError(f"Unrecognized manifest status for {source}")
        output = item.get("result_file" if legacy else "output")
        if output:
            output = output_identity(output, results_dir)
            if output.casefold() in files:
                raise ResultFormatError(f"Duplicate manifest result file: {output}")
            files[output.casefold()] = doc_id
        rows[doc_id] = {**item, "source_file": source, "result_file": output}

    actual = {}
    for raw in loaded:
        local = raw["_metadata"]
        file_name = relative_identity(local["result_file"])
        if file_name.lower().endswith(".result.json"):
            source = source_identity(file_name[:-len(".result.json")], samples_dir, expected)
            for name in ("document", "source_file"):
                if name in local and source_identity(local[name], samples_dir, expected).casefold() != source.casefold():
                    raise ResultFormatError(f"Conflicting source identity in {file_name}")
            doc_id = expected[source.casefold()]
        elif "document" in local:
            source = source_identity(local["document"], samples_dir, expected)
            doc_id = expected[source.casefold()]
        elif file_name.casefold() in files:
            doc_id = files[file_name.casefold()]
            source = rows[doc_id]["source_file"]
        else:
            source = source_identity(local["source_file"], samples_dir, expected)
            doc_id = expected[source.casefold()]
        if doc_id in actual:
            raise ResultFormatError(f"Duplicate result input: {source}")
        if metadata:
            row = rows.get(doc_id)
            if row is None or row.get("result_file") and row["result_file"].casefold() != file_name.casefold():
                raise ResultFormatError(f"Result is not the manifest output for {source}")
        status = result_status(raw)
        if status is not None and status.lower() not in {
            "succeeded", "success", "failed", "canceled", "cancelled", "running", "notstarted",
        }:
            raise ResultFormatError(f"Unrecognized result status: {status}")
        failed = (
            status is not None and status.lower() not in {"succeeded", "success"}
            or bool(raw.get("error") or result_payload(raw).get("error"))
        )
        actual[doc_id] = {
            "raw": raw, "source_file": source, "result_file": file_name,
            "status": "failed" if failed else "success",
            "service_status": status,
            "prediction": {"parties": [], "obligations": []} if failed else canonicalize_result(raw),
        }

    run = {}
    for source, doc_id in expected.items():
        result = actual.get(doc_id, {})
        item = rows.get(doc_id, {})
        succeeded = result.get("status") == "success" and (
            not metadata or item.get("status") in {"success", "succeeded"}
        )
        run[doc_id] = {
            "doc_id": doc_id,
            "source_file": result.get("source_file", item.get("source_file", source)),
            "result_file": result.get("result_file", item.get("result_file")),
            "status": "success" if succeeded else "failed",
            "service_status": result.get("service_status"),
            "report_status": item.get("status"),
            "error": "" if succeeded else item.get("error") or item.get("reason")
            or "Missing, failed, or uncompleted expected result",
            **measurements(result.get("raw", {}), item),
            "prediction": result["prediction"] if succeeded else {"parties": [], "obligations": []},
        }

    metadata = dict(metadata)
    metadata["result_directory"] = str(results_dir)
    metadata["result_format"] = "legacy" if legacy else "native"
    for name, payload_key, report_key in (
        ("analyzer_id", "analyzerId", "analyzer"),
        ("api_version", "apiVersion", "api_version"),
    ):
        values = {
            result_payload(raw).get(payload_key) for raw in loaded
            if result_payload(raw).get(payload_key)
        }
        if metadata.get(name) or metadata.get(report_key):
            values.add(metadata.get(name) or metadata[report_key])
        if len(values) > 1:
            raise ResultFormatError(f"Mixed {name} values in one benchmark run")
        metadata[name] = next(iter(values), None)
    return {"metadata": metadata, "documents": run}


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
    aliases = get_value(party, "Aliases", "aliases", default=[]) or []
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


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
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
        "source_file": run_record.get("source_file") if run_record else None,
        "result_file": run_record.get("result_file") if run_record else None,
        "status": run_record["status"] if run_record else "failed",
        "service_status": run_record.get("service_status") if run_record else None,
        "report_status": run_record.get("report_status") if run_record else None,
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
        "input_tokens": run_record.get("input_tokens") if run_record else None,
        "output_tokens": run_record.get("output_tokens") if run_record else None,
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
    all_latencies = [doc["elapsed_seconds"] for doc in documents if doc["elapsed_seconds"] is not None]
    full_latency = bool(completed) and len(latencies) == len(completed)
    measured = {
        key: [doc[key] for doc in documents if doc[key] is not None]
        for key in ("input_tokens", "output_tokens")
    }
    token_totals = {
        key: sum(values) if values and len(values) == len(documents) else None
        for key, values in measured.items()
    }
    total_input, total_output = token_totals["input_tokens"], token_totals["output_tokens"]
    matched_count = totals["matched_count"]
    return {
        "mode": mode,
        "run_id": metadata.get("run_id", ""),
        "api_version": metadata.get("api_version", ""),
        "analyzer_id": metadata.get("analyzer_id", ""),
        "result_directory": metadata.get("result_directory"),
        "result_format": metadata.get("result_format"),
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
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_tokens": total_input + total_output if total_input is not None and total_output is not None else None,
        "observed_input_tokens": sum(measured["input_tokens"]) if measured["input_tokens"] else None,
        "observed_output_tokens": sum(measured["output_tokens"]) if measured["output_tokens"] else None,
        "measurement_coverage": {
            "input_tokens": len(measured["input_tokens"]),
            "output_tokens": len(measured["output_tokens"]),
            "elapsed_seconds": len(all_latencies),
            "completed_elapsed_seconds": len(latencies),
            "expected_documents": len(documents),
        },
        "latency_seconds": {
            "mean": statistics.fmean(latencies) if full_latency else None,
            "p50": statistics.median(latencies) if full_latency else None,
            "p95": percentile(latencies, 0.95) if full_latency else None,
            "max": max(latencies) if full_latency else None,
            "total": sum(all_latencies) if all_latencies and len(all_latencies) == len(documents) else None,
        },
        "documents": documents,
    }


def evaluate_mode(
    mode: str,
    gold_records: list[dict[str, Any]],
    samples_dir: Path,
    results_dir: Path,
    report_path: Path | None = None,
) -> dict[str, Any]:
    run = load_run(results_dir, gold_records, samples_dir, report_path)
    documents = []
    for gold in gold_records:
        source_path = samples_dir / relative_identity(gold.get("source_file", f"{gold['doc_id']}.txt"))
        source_text = source_path.read_text(encoding="utf-8")
        if gold.get("source_sha256") and hashlib.sha256(source_text.encode("utf-8")).hexdigest() != gold["source_sha256"]:
            raise ValueError(f"Source checksum mismatch: {source_path}")
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


def fmt_number(value: float | None) -> str:
    return "unknown" if value is None else f"{value:,.1f}"


def fmt_tokens(value: int | None) -> str:
    return "unknown" if value is None else f"{value:,}"


def measured_ratio(numerator: float | None, denominator: float | None) -> float | None:
    return numerator / denominator if numerator is not None and denominator else None


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
    latency_ratio = measured_ratio(
        agentic["latency_seconds"]["mean"], standard["latency_seconds"]["mean"]
    )
    token_ratio = measured_ratio(
        agentic["total_tokens"], standard["total_tokens"]
    )
    lines = [
        "# Standard vs. Agentic contract-obligation benchmark",
        "",
        "**Result:** " + comparison_conclusion(standard, agentic),
        "",
        "## Benchmark design",
        "",
        f"- Standard run ID: `{standard['run_id'] or 'not recorded'}`; API: `{standard['api_version'] or 'not recorded'}`.",
        f"- Agentic run ID: `{agentic['run_id'] or 'not recorded'}`; API: `{agentic['api_version'] or 'not recorded'}`.",
        f"- Standard inputs: `{standard.get('result_directory')}` ({standard.get('result_format')}).",
        f"- Agentic inputs: `{agentic.get('result_directory')}` ({agentic.get('result_format')}).",
        f"- Golden set: {standard['document_count']} independently annotated short CUAD contracts.",
        f"- Gold obligations: {standard['gold_obligations']}.",
        "- Standard: GA API with `gpt-4.1` and no Agentic workflow selector.",
        "- Agentic: `2026-06-01-preview`, `gpt-5.2`, and `config.workflow: \"Agentic\"`.",
        "- The field schema, source documents, matching threshold, and fail-closed scoring are identical.",
        "- Missing, failed, and skipped documents retain all gold obligations and contribute zero predictions.",
        "- Native payloads may omit operation status; service_status remains null rather than inventing a service status.",
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
            f"| Completed documents | {standard['completed_count']}/{standard['document_count']} | {agentic['completed_count']}/{agentic['document_count']} |",
            f"| Mean latency | {fmt_number(standard['latency_seconds']['mean'])} s | {fmt_number(agentic['latency_seconds']['mean'])} s |",
            f"| P95 latency | {fmt_number(standard['latency_seconds']['p95'])} s | {fmt_number(agentic['latency_seconds']['p95'])} s |",
            f"| Active execution time | {fmt_number(measured_ratio(standard['latency_seconds']['total'], 60))} min | {fmt_number(measured_ratio(agentic['latency_seconds']['total'], 60))} min |",
            f"| Input tokens | {fmt_tokens(standard['total_input_tokens'])} | {fmt_tokens(agentic['total_input_tokens'])} |",
            f"| Output tokens | {fmt_tokens(standard['total_output_tokens'])} | {fmt_tokens(agentic['total_output_tokens'])} |",
            f"| Duplicate obligations | {standard['duplicate_count']} | {agentic['duplicate_count']} |",
            f"| Agentic latency multiplier | - | {fmt_number(latency_ratio)} |",
            f"| Agentic token multiplier | - | {fmt_number(token_ratio)} |",
            "",
            "Unknown measurements stay null, not zero. Token and active-time totals require "
            "measurements for every expected document, including failures. Latency statistics "
            "require timing for every completed document. JSON includes measurement coverage "
            "and explicitly partial observed token sums; console --usage/--time is not parsed.",
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
            "The checked-in REPORT.md and qualitative review describe the historical run only; "
            "their verdicts are not applied to this evaluation.",
            "",
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
    with output_path.open("x", encoding="utf-8") as handle:
        handle.write("\n".join(lines))


def write_json(data: dict[str, Any], path: Path) -> None:
    with path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(data, indent=2, allow_nan=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--samples", type=Path, default=DEFAULT_SAMPLES)
    parser.add_argument("--standard-results", type=Path, required=True)
    parser.add_argument("--agentic-results", type=Path, required=True)
    parser.add_argument("--standard-report", type=Path, help="Native CLI report; defaults to report.json in the result directory")
    parser.add_argument("--agentic-report", type=Path, help="Native CLI report; defaults to report.json in the result directory")
    parser.add_argument("--output", type=Path, help="New metrics directory; defaults to a unique directory under evaluation/output")
    parser.add_argument(
        "--report",
        type=Path,
        help="New report path; defaults to REPORT.md in the new metrics directory",
    )
    args = parser.parse_args()
    gold_records = load_gold(args.gold.resolve())
    output_dir = args.output or DEFAULT_OUTPUT / (
        datetime.now(timezone.utc).strftime("evaluation_%Y%m%dT%H%M%SZ_") + uuid4().hex[:8]
    )
    output_dir = output_dir.resolve()
    report_path = (args.report or output_dir / "REPORT.md").resolve()
    for path in (output_dir / "standard_metrics.json", output_dir / "agentic_metrics.json", report_path):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite saved evidence: {path}")
    standard = evaluate_mode(
        "Standard",
        gold_records,
        args.samples.resolve(),
        args.standard_results.resolve(),
        args.standard_report,
    )
    agentic = evaluate_mode(
        "Agentic",
        gold_records,
        args.samples.resolve(),
        args.agentic_results.resolve(),
        args.agentic_report,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(standard, output_dir / "standard_metrics.json")
    write_json(agentic, output_dir / "agentic_metrics.json")
    write_report(standard, agentic, report_path)
    print(
        f"Standard F1={standard['f1']:.1%}; Agentic F1={agentic['f1']:.1%}; "
        f"report={report_path}"
    )


if __name__ == "__main__":
    main()
