"""Verify every emitted evidence quote occurs in source text."""

from evallens.core.evaluator_registry import EvaluatorProvider, EvaluatorRegistry
from evallens.evaluators.base_evaluator import BaseEvaluator

from contract_eval_common import (
    evidence_quotes,
    metric,
    normalize_quote_text,
    prediction_obligations,
)


@EvaluatorRegistry.register(
    name="quote_groundedness",
    description="Share of obligations whose exact evidence quotes occur in source text",
    module_name="contract_obligations",
    mode="offline",
    provider=EvaluatorProvider.CUSTOM_CODE,
)
class QuoteGroundednessEvaluator(BaseEvaluator):
    def evaluate(self, prediction: dict, ground_truth: dict = None) -> dict:
        source = normalize_quote_text(
            prediction.get("source_text")
            or (ground_truth or {}).get("source_text", "")
        )
        obligations = prediction_obligations(prediction)
        grounded = 0
        failures = []
        for index, obligation in enumerate(obligations):
            quotes = evidence_quotes(obligation)
            valid = bool(quotes) and all(
                normalize_quote_text(quote) in source for quote in quotes
            )
            grounded += valid
            if not valid:
                failures.append(index)
        score = grounded / len(obligations) if obligations else 1.0
        return {
            self.get_name(): metric(
                score,
                f"{grounded}/{len(obligations)} obligations fully quote-grounded; "
                f"failures={failures[:10]}",
            )
        }
