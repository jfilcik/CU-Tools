"""Unit tests for deterministic contract-obligation evaluation."""

from __future__ import annotations

import sys
from pathlib import Path

EVALUATION_DIR = Path(__file__).resolve().parents[1]
EVALUATOR_DIR = EVALUATION_DIR / "evaluators" / "contract_obligations"
sys.path.insert(0, str(EVALUATION_DIR))
sys.path.insert(0, str(EVALUATOR_DIR))

from contract_eval_common import match_obligations, normalize_text
from duplicate_obligation_evaluator import DuplicateObligationEvaluator
from obligation_completeness_evaluator import ObligationCompletenessEvaluator
from obligation_discovery_evaluator import ObligationDiscoveryEvaluator
from obligation_type_evaluator import ObligationTypeEvaluator
from party_role_evaluator import PartyRoleEvaluator
from quote_alignment_evaluator import QuoteAlignmentEvaluator
from quote_groundedness_evaluator import QuoteGroundednessEvaluator
from generate_accuracy_report import aggregate
from generate_broad_quality_report import _failure_kind

SOURCE = "Buyer shall pay Seller $100 within 30 days after receipt of an invoice."
PREDICTION = {
    "source_text": SOURCE,
    "obligations": [
        {
            "ObligationId": "O1",
            "ObligorPartyId": "P1",
            "ObligeePartyIds": ["P2"],
            "ObligationType": "Payment",
            "TriggerCondition": "receipt of an invoice",
            "Timing": "within 30 days",
            "AmountOrQuantity": "$100",
            "Evidence": [{"ExactQuote": SOURCE, "EvidencePurpose": "Duty"}],
        }
    ],
}
GROUND_TRUTH = {
    "source_text": SOURCE,
    "obligations": [
        {
            "obligation_id": "O1",
            "obligor_party_id": "P1",
            "obligee_party_ids": ["P2"],
            "obligation_type": "Payment",
            "exact_quotes": [SOURCE],
            "required_fields": [
                "trigger_condition",
                "timing",
                "amount_or_quantity",
            ],
        }
    ],
}


def _score(evaluator, name):
    return evaluator().evaluate(PREDICTION, GROUND_TRUTH)[name]["score"]


def test_normalization_and_matching_are_deterministic():
    assert normalize_text("  Buyer\u00a0SHALL  pay ") == "buyer shall pay"
    matches, unmatched_pred, unmatched_gold = match_obligations(
        PREDICTION, GROUND_TRUTH
    )
    assert len(matches) == 1
    assert not unmatched_pred
    assert not unmatched_gold


def test_all_primary_metrics_pass_perfect_record():
    assert _score(ObligationDiscoveryEvaluator, "obligation_discovery") == 1.0
    assert _score(ObligationTypeEvaluator, "obligation_type_accuracy") == 1.0
    assert _score(PartyRoleEvaluator, "party_role_accuracy") == 1.0
    assert _score(QuoteGroundednessEvaluator, "quote_groundedness") == 1.0
    assert _score(QuoteAlignmentEvaluator, "quote_alignment") == 1.0
    assert _score(ObligationCompletenessEvaluator, "obligation_completeness") == 1.0
    assert _score(DuplicateObligationEvaluator, "duplicate_obligation") == 1.0


def test_quote_grounding_rejects_paraphrase():
    prediction = {
        **PREDICTION,
        "obligations": [
            {
                **PREDICTION["obligations"][0],
                "Evidence": [{"ExactQuote": "Buyer must promptly pay Seller."}],
            }
        ],
    }
    score = QuoteGroundednessEvaluator().evaluate(
        prediction, GROUND_TRUTH
    )["quote_groundedness"]["score"]
    assert score == 0.0


def test_quote_grounding_rejects_changed_case():
    prediction = {
        **PREDICTION,
        "obligations": [
            {
                **PREDICTION["obligations"][0],
                "Evidence": [{"ExactQuote": SOURCE.lower()}],
            }
        ],
    }
    score = QuoteGroundednessEvaluator().evaluate(
        prediction, GROUND_TRUTH
    )["quote_groundedness"]["score"]
    assert score == 0.0


def test_duplicate_and_zero_result_cases():
    duplicate_prediction = {
        **PREDICTION,
        "obligations": PREDICTION["obligations"] * 2,
    }
    duplicate_score = DuplicateObligationEvaluator().evaluate(
        duplicate_prediction, GROUND_TRUTH
    )["duplicate_obligation"]["score"]
    assert duplicate_score == 0.5

    discovery_score = ObligationDiscoveryEvaluator().evaluate(
        {"obligations": []}, GROUND_TRUTH
    )["obligation_discovery"]["score"]
    assert discovery_score == 0.0


def test_non_applicable_atomic_metrics_fail_closed():
    clause_only = {
        "source_text": SOURCE,
        "clauses": [
            {
                "obligation_type": "Payment",
                "exact_quote": SOURCE,
            }
        ],
    }
    assert PartyRoleEvaluator().evaluate(
        PREDICTION, clause_only
    )["party_role_accuracy"]["score"] == 0.0
    assert ObligationCompletenessEvaluator().evaluate(
        PREDICTION, clause_only
    )["obligation_completeness"]["score"] == 0.0


def test_report_aggregation_fails_closed_on_missing_metrics():
    summary = aggregate(
        {
            "results": [
                {
                    "doc_id": "doc-1",
                    "evaluation_results": [
                        {"name": "obligation_discovery", "score": 1.0}
                    ],
                }
            ]
        }
    )
    assert summary["component_scores"]["obligation_discovery"] == 1.0
    assert summary["component_scores"]["party_role_accuracy"] == 0.0
    assert summary["missing_evaluator_scores"]["party_role_accuracy"] == 1
    assert not summary["passed"]


def test_broad_report_failure_taxonomy():
    assert _failure_kind("Operation timed out after 1800 seconds") == "timeout"
    assert _failure_kind("Connection aborted") == "connection_reset"
    assert _failure_kind("Request failed.") == "request_failed"
