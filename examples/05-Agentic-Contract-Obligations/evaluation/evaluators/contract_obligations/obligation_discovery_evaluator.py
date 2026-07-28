"""Deterministic obligation discovery precision, recall, and F1."""

from evallens.core.evaluator_registry import EvaluatorProvider, EvaluatorRegistry
from evallens.evaluators.base_evaluator import BaseEvaluator

from contract_eval_common import (
    f1_score,
    gold_obligations,
    match_obligations,
    metric,
    prediction_obligations,
)


@EvaluatorRegistry.register(
    name="obligation_discovery",
    description="Evidence-span matched obligation discovery F1",
    module_name="contract_obligations",
    mode="offline",
    provider=EvaluatorProvider.CUSTOM_CODE,
)
class ObligationDiscoveryEvaluator(BaseEvaluator):
    def evaluate(self, prediction: dict, ground_truth: dict = None) -> dict:
        ground_truth = ground_truth or {}
        threshold = float(self.config.get("match_threshold", 0.55))
        matches, _, _ = match_obligations(prediction, ground_truth, threshold)
        predicted_count = len(prediction_obligations(prediction))
        gold_count = len(gold_obligations(ground_truth))
        precision, recall, f1 = f1_score(len(matches), predicted_count, gold_count)
        return {
            self.get_name(): metric(
                f1,
                f"precision={precision:.4f}; recall={recall:.4f}; "
                f"matched={len(matches)}/{gold_count}; predicted={predicted_count}",
            )
        }
