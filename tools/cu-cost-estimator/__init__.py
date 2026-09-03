"""
Azure AI Content Understanding Tools

This package contains tools for estimating and analyzing costs for
Azure AI Content Understanding services.
"""

try:
    from .cu_cost_estimator import (
        CostEstimator,
        CostBreakdown,
        ProcessingRequest,
        SchemaConfig,
        UsageData,
        EstimationMode,
        PRICING_CONFIG,
    )
except ImportError:
    # Allow imports to work when running tests directly
    pass

__all__ = [
    'CostEstimator',
    'CostBreakdown',
    'ProcessingRequest',
    'SchemaConfig',
    'UsageData',
    'EstimationMode',
    'PRICING_CONFIG',
]
