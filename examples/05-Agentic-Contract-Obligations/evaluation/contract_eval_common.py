"""Deterministic matching and normalization shared by contract evaluators."""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any


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
