"""Obligation type accuracy on evidence-matched obligations."""

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
    name="obligation_type_accuracy",
    description="Obligation taxonomy accuracy on matched obligations",
    module_name="contract_obligations",
    mode="offline",
    provider=EvaluatorProvider.CUSTOM_CODE,
)
class ObligationTypeEvaluator(BaseEvaluator):
    def evaluate(self, prediction: dict, ground_truth: dict = None) -> dict:
        ground_truth = ground_truth or {}
        predicted = prediction_obligations(prediction)
        gold = gold_obligations(ground_truth)
        matches, _, _ = match_obligations(
            prediction,
            ground_truth,
            float(self.config.get("match_threshold", 0.55)),
        )
        applicable = [
            (predicted[pred_index], gold[gold_index])
            for pred_index, gold_index, _ in matches
            if get_value(gold[gold_index], "obligation_type", "ObligationType")
        ]
        correct = sum(
            normalize_text(get_value(pred, "ObligationType", "obligation_type"))
            == normalize_text(get_value(target, "ObligationType", "obligation_type"))
            for pred, target in applicable
        )
        score = correct / len(applicable) if applicable else 1.0
        return {
            self.get_name(): metric(
                score,
                f"{correct}/{len(applicable)} matched obligations have the correct type",
            )
        }
