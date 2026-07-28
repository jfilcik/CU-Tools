"""Measure whether emitted evidence aligns to the matching gold clause."""

from evallens.core.evaluator_registry import EvaluatorProvider, EvaluatorRegistry
from evallens.evaluators.base_evaluator import BaseEvaluator

from contract_eval_common import match_obligations, metric


@EvaluatorRegistry.register(
    name="quote_alignment",
    description="Evidence overlap with the correct gold clause",
    module_name="contract_obligations",
    mode="offline",
    provider=EvaluatorProvider.CUSTOM_CODE,
)
class QuoteAlignmentEvaluator(BaseEvaluator):
    def evaluate(self, prediction: dict, ground_truth: dict = None) -> dict:
        threshold = float(self.config.get("match_threshold", 0.55))
        matches, _, unmatched_gold = match_obligations(
            prediction,
            ground_truth or {},
            threshold,
        )
        expected = len(matches) + len(unmatched_gold)
        score = len(matches) / expected if expected else 1.0
        mean_overlap = (
            sum(match[2] for match in matches) / len(matches) if matches else 0.0
        )
        return {
            self.get_name(): metric(
                score,
                f"aligned={len(matches)}/{expected}; mean_quote_overlap={mean_overlap:.4f}",
            )
        }
