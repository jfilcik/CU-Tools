"""Deterministic matching and normalization shared by contract evaluators."""

from __future__ import annotations

import json
import math
import re
import sys
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools" / "cu-results-export"))
from cu_result_io import load_results, result_status


def read_analysis_result(path: Path) -> dict[str, Any]:
    """Use the shared offline loader for shape validation and native normalization."""
    return load_results(path)[0]


def load_run_metadata(result_dir: Path, report_path: Path | None = None) -> dict[str, Any]:
    """Read official CLI status reports or previously saved CU-Tools metadata."""
    path = report_path or result_dir / "analyze-report.json"
    if report_path is None and not path.exists():
        path = result_dir / "metadata.json"
    metadata = json.loads(path.read_text(encoding="utf-8"))
    schema = metadata.get("schema")
    if schema is None:
        if path.name != "metadata.json" or "results" not in metadata:
            raise ValueError("Expected a CU CLI analyze report or saved metadata.json.")
        return metadata
    if schema != "cu-cli/analyze-report/v1" or metadata.get("result_view") != "full":
        raise ValueError("Expected cu-cli/analyze-report/v1 from cu analyze --json.")

    root = result_dir.resolve()
    results = []
    seen = set()
    for item in metadata["results"]:
        document = item["input"]
        doc_id = Path(document).stem
        if doc_id in seen:
            raise ValueError(f"Duplicate document stem in CLI report: {doc_id}")
        seen.add(doc_id)
        row = {
            "document": document,
            "status": "success" if item["status"] == "succeeded" else "failed",
            "error": (
                item.get("error") or item.get("reason") or item["status"]
                if item["status"] != "succeeded"
                else ""
            ),
        }
        output = item.get("output")
        if output:
            candidate = Path(output)
            candidates = [candidate.resolve(), (root / candidate).resolve()]
            for candidate in candidates:
                if candidate.is_relative_to(root):
                    row["result_path"] = str(candidate)
                    break
            else:
                raise ValueError(f"CLI output is outside the supplied result directory: {doc_id}")
        elif row["status"] == "success":
            row["status"] = "failed"
            row["error"] = "CLI report has no saved JSON output"
        results.append(row)
    return {"analyzer_id": metadata.get("analyzer", ""), "results": results}


def recorded_number(value: Any) -> int | float | None:
    """Keep unavailable measurements distinct from an explicitly recorded zero."""
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
        return value
    return None


def format_measure(
    value: int | float | None,
    *,
    divisor: float = 1,
    format_spec: str = ".1f",
    suffix: str = "",
) -> str:
    if value is None:
        return "not recorded"
    return format(value / divisor, format_spec) + suffix


def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    return " ".join(text.split()).casefold()


def normalize_quote_text(value: Any) -> str:
    """Normalize OCR whitespace and Unicode while preserving case."""
    text = unicodedata.normalize("NFKC", str(value or ""))
    return " ".join(text.split())


def get_value(record: dict[str, Any], *names: str, default: Any = "") -> Any:
    for name in names:
        if name in record:
            return record[name]
    return default


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
        if str(quote).strip():
            quotes.append(str(quote))
    direct = get_value(obligation, "exact_quotes", "ExactQuotes", default=[])
    if isinstance(direct, str):
        direct = [direct]
    quotes.extend(str(quote) for quote in direct if str(quote).strip())
    return quotes


def gold_obligations(ground_truth: dict[str, Any]) -> list[dict[str, Any]]:
    obligations = ground_truth.get("obligations")
    if isinstance(obligations, list):
        return obligations
    clauses = ground_truth.get("clauses", [])
    return [
        {
            "obligation_type": clause.get("obligation_type", ""),
            "exact_quotes": [clause.get("exact_quote", "")],
            "category": clause.get("category", ""),
        }
        for clause in clauses
        if isinstance(clause, dict)
    ]


def prediction_obligations(prediction: dict[str, Any]) -> list[dict[str, Any]]:
    obligations = get_value(prediction, "obligations", "Obligations", default=[])
    return obligations if isinstance(obligations, list) else []


def quote_similarity(left: str, right: str) -> float:
    left_n = normalize_text(left)
    right_n = normalize_text(right)
    if not left_n or not right_n:
        return 0.0
    if left_n in right_n or right_n in left_n:
        return min(len(left_n), len(right_n)) / max(len(left_n), len(right_n))
    left_tokens = set(re.findall(r"\w+", left_n))
    right_tokens = set(re.findall(r"\w+", right_n))
    token_score = (
        2 * len(left_tokens & right_tokens) / (len(left_tokens) + len(right_tokens))
        if left_tokens and right_tokens
        else 0.0
    )
    return max(SequenceMatcher(None, left_n, right_n).ratio(), token_score)


def obligation_similarity(prediction: dict[str, Any], gold: dict[str, Any]) -> float:
    pred_quotes = evidence_quotes(prediction)
    gold_quotes = evidence_quotes(gold)
    if not pred_quotes or not gold_quotes:
        return 0.0
    return max(quote_similarity(pred, target) for pred in pred_quotes for target in gold_quotes)


def match_obligations(
    prediction: dict[str, Any],
    ground_truth: dict[str, Any],
    threshold: float = 0.55,
) -> tuple[list[tuple[int, int, float]], list[int], list[int]]:
    predicted = prediction_obligations(prediction)
    gold = gold_obligations(ground_truth)
    pairs = sorted(
        (
            (obligation_similarity(pred, target), pred_index, gold_index)
            for pred_index, pred in enumerate(predicted)
            for gold_index, target in enumerate(gold)
        ),
        reverse=True,
    )
    matches = []
    used_pred = set()
    used_gold = set()
    for score, pred_index, gold_index in pairs:
        if score < threshold or pred_index in used_pred or gold_index in used_gold:
            continue
        matches.append((pred_index, gold_index, score))
        used_pred.add(pred_index)
        used_gold.add(gold_index)
    return (
        matches,
        [index for index in range(len(predicted)) if index not in used_pred],
        [index for index in range(len(gold)) if index not in used_gold],
    )


def metric(score: float, reason: str) -> dict[str, Any]:
    return {"score": round(max(0.0, min(1.0, score)), 4), "reason": reason}


def f1_score(true_positive: int, predicted: int, expected: int) -> tuple[float, float, float]:
    precision = true_positive / predicted if predicted else (1.0 if expected == 0 else 0.0)
    recall = true_positive / expected if expected else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1
