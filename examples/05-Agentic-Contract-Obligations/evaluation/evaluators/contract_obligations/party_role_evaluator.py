"""Obligor and obligee accuracy on evidence-matched atomic obligations."""

from evallens.core.evaluator_registry import EvaluatorProvider, EvaluatorRegistry
from evallens.evaluators.base_evaluator import BaseEvaluator

from contract_eval_common import (
    get_value,
    gold_obligations,
    match_obligations,
    metric,
    normalize_text,
    prediction_obligations,
)


@EvaluatorRegistry.register(
    name="party_role_accuracy",
    description="Obligor and obligee role accuracy for matched atomic obligations",
    module_name="contract_obligations",
    mode="offline",
    provider=EvaluatorProvider.CUSTOM_CODE,
)
class PartyRoleEvaluator(BaseEvaluator):
    def evaluate(self, prediction: dict, ground_truth: dict = None) -> dict:
        ground_truth = ground_truth or {}
        predicted = prediction_obligations(prediction)
        gold = gold_obligations(ground_truth)
        matches, _, _ = match_obligations(
            prediction,
            ground_truth,
            float(self.config.get("match_threshold", 0.55)),
        )
        obligor_correct = obligee_correct = applicable = 0
        for pred_index, gold_index, _ in matches:
            target = gold[gold_index]
            target_obligor = get_value(target, "obligor_party_id", "ObligorPartyId")
            if not target_obligor:
                continue
            applicable += 1
            pred = predicted[pred_index]
            obligor_correct += (
                normalize_text(get_value(pred, "ObligorPartyId", "obligor_party_id"))
                == normalize_text(target_obligor)
            )
            pred_obligees = {
                normalize_text(value)
                for value in get_value(
                    pred, "ObligeePartyIds", "obligee_party_ids", default=[]
                )
            }
            target_obligees = {
                normalize_text(value)
                for value in get_value(
                    target, "ObligeePartyIds", "obligee_party_ids", default=[]
                )
            }
            obligee_correct += pred_obligees == target_obligees
        score = (
            (obligor_correct + obligee_correct) / (2 * applicable)
            if applicable
            else 0.0
        )
        return {
            self.get_name(): metric(
                score,
                f"obligor={obligor_correct}/{applicable}; "
                f"obligee={obligee_correct}/{applicable}",
            )
        }
