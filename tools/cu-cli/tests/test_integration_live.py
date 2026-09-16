"""
Live integration smoke test for cu-cli against the real Content
Understanding service.

Skipped automatically unless AZURE_AI_ENDPOINT and AZURE_AI_API_KEY are set
(see conftest.py's `has_azure_credentials()` / `pytest_collection_modifyitems`).

This creates a throwaway analyzer (prebuilt-document base, no custom
fields, minimal cost), analyzes a small sample document, and deletes the
analyzer in a `finally` block so it never leaks even if analysis fails.
"""

import sys
import time
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from cu_cli import operations as ops

REPO_ROOT = Path(__file__).parent.parent.parent.parent
DATA_FOLDER = REPO_ROOT / "data"

SAMPLE_CANDIDATES = [
    REPO_ROOT / "examples" / "02-Invoice-Extraction" / "samples" / "invoice.pdf",
    DATA_FOLDER / "invoice.pdf",
    DATA_FOLDER / "receipt.png",
    DATA_FOLDER / "pieChart.jpg",
]


def _find_sample_file():
    for path in SAMPLE_CANDIDATES:
        if path.exists():
            return path
    return None


@pytest.mark.integration
class TestLiveSmoke:
    def test_validate_setup_against_live_service(self, requires_credentials):
        client = ops.get_client()
        defaults = ops.validate_setup(client, verbose=True)
        assert isinstance(defaults, dict)

    def test_create_analyze_delete_round_trip(self, requires_credentials):
        sample_file = _find_sample_file()
        if sample_file is None:
            pytest.skip("No sample document available in data/ for a live analyze call")

        client = ops.get_client()
        analyzer_id = f"cu_cli_smoke_{uuid.uuid4().hex[:8]}"
        schema = {
            "description": "cu-cli live smoke test analyzer (safe to delete)",
            "baseAnalyzerId": "prebuilt-document",
            "config": {"returnDetails": True},
        }

        try:
            detail = ops.create_analyzer_and_wait(client, analyzer_id, schema, max_wait=120)
            assert detail.get("status", "").lower() in ("succeeded", "ready")

            result = ops.analyze_file_and_wait(client, analyzer_id, sample_file, timeout=180)
            assert result.get("status", "").lower() == "succeeded"
            assert "result" in result
        finally:
            # Best-effort cleanup; give the service a moment before deleting.
            time.sleep(1)
            ops.delete_analyzer_safe(client, analyzer_id)

    def test_list_analyzers_against_live_service(self, requires_credentials):
        client = ops.get_client()
        analyzers = ops.list_analyzers(client)
        assert isinstance(analyzers, list)
