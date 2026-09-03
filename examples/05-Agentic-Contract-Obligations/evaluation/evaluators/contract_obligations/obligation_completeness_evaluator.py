"""Score required atomic-obligation fields on matched records."""

from evallens.core.evaluator_registry import EvaluatorProvider, EvaluatorRegistry
from evallens.evaluators.base_evaluator import BaseEvaluator

from contract_eval_common import (
    get_value,
    gold_obligations,
    match_obligations,
    metric,
    prediction_obligations,
)

FIELD_NAMES = {
    "trigger_condition": ("TriggerCondition", "trigger_condition"),
    "timing": ("Timing", "timing"),
    "amount_or_quantity": ("AmountOrQuantity", "amount_or_quantity"),
    "exceptions": ("Exceptions", "exceptions"),
    "related_obligation_ids": ("RelatedObligationIds", "related_obligation_ids"),
}


@EvaluatorRegistry.register(
    name="obligation_completeness",
    description="Presence of gold-applicable trigger, timing, amount, exception, and relation fields",
    module_name="contract_obligations",
    mode="offline",
    provider=EvaluatorProvider.CUSTOM_CODE,
)
class ObligationCompletenessEvaluator(BaseEvaluator):
    def evaluate(self, prediction: dict, ground_truth: dict = None) -> dict:
        ground_truth = ground_truth or {}
        predicted = prediction_obligations(prediction)
        gold = gold_obligations(ground_truth)
        matches, _, _ = match_obligations(
            prediction,
            ground_truth,
            float(self.config.get("match_threshold", 0.55)),
        )
        present = required = 0
        for pred_index, gold_index, _ in matches:
            pred = predicted[pred_index]
            for field_name in gold[gold_index].get("required_fields", []):
                names = FIELD_NAMES.get(field_name)
                if not names:
                    continue
                required += 1
                value = get_value(pred, *names, default="")
                present += bool(value)
        score = present / required if required else 0.0
        return {
            self.get_name(): metric(
                score,
                f"{present}/{required} applicable detail fields populated",
            )
        }
