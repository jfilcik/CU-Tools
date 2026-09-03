"""Penalize repeated obligations with identical party, type, and evidence."""

from evallens.core.evaluator_registry import EvaluatorProvider, EvaluatorRegistry
from evallens.evaluators.base_evaluator import BaseEvaluator

from contract_eval_common import (
    evidence_quotes,
    get_value,
    metric,
    normalize_text,
    prediction_obligations,
)


@EvaluatorRegistry.register(
    name="duplicate_obligation",
    description="One minus the semantically duplicate obligation rate",
    module_name="contract_obligations",
    mode="offline",
    provider=EvaluatorProvider.CUSTOM_CODE,
)
class DuplicateObligationEvaluator(BaseEvaluator):
    def evaluate(self, prediction: dict, ground_truth: dict = None) -> dict:
        obligations = prediction_obligations(prediction)
        seen = set()
        duplicates = 0
        for obligation in obligations:
            key = (
                normalize_text(
                    get_value(obligation, "ObligorPartyId", "obligor_party_id")
                ),
                normalize_text(
                    get_value(obligation, "ObligationType", "obligation_type")
                ),
                tuple(sorted(normalize_text(quote) for quote in evidence_quotes(obligation))),
            )
            if key in seen:
                duplicates += 1
            else:
                seen.add(key)
        score = 1.0 - (duplicates / len(obligations) if obligations else 0.0)
        return {
            self.get_name(): metric(
                score,
                f"{duplicates} duplicate records among {len(obligations)} obligations",
            )
        }
