"""
Test configuration for CU Cost Estimator tests.

These are unit tests (no external dependencies) so they're marked with @pytest.mark.unit
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
test_dir = Path(__file__).parent
cu_cost_estimator_dir = test_dir.parent
sys.path.insert(0, str(cu_cost_estimator_dir))

