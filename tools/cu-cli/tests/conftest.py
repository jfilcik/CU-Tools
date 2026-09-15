"""Shared fixtures for cu-cli tests."""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "cu-client"))

REPO_ROOT = Path(__file__).parent.parent.parent.parent
DATA_FOLDER = REPO_ROOT / "data"


@pytest.fixture
def mock_client():
    """A MagicMock standing in for AzureContentUnderstandingClient."""
    client = MagicMock()
    client.get_analyzer_detail_by_id.return_value = {"status": "Succeeded", "analyzerId": "test-analyzer"}
    client.get_all_analyzers.return_value = {"value": [{"analyzerId": "test-analyzer"}]}
    client.get_defaults.return_value = {"modelDeployments": {"gpt-4.1": "my-gpt41-deployment"}}
    client.validate_setup.return_value = {"modelDeployments": {"gpt-4.1": "my-gpt41-deployment"}}

    analyze_response = MagicMock()
    analyze_response.headers = {"operation-location": "https://example/op/1"}
    client.begin_analyze_binary.return_value = analyze_response
    client.begin_analyze_url.return_value = analyze_response
    client.begin_classify.return_value = analyze_response

    client.poll_result.return_value = {
        "status": "Succeeded",
        "result": {"contents": [{"fields": {}}]},
    }
    return client


@pytest.fixture
def mock_env_vars(monkeypatch):
    monkeypatch.setenv("AZURE_AI_ENDPOINT", "https://test.cognitiveservices.azure.com")
    monkeypatch.setenv("AZURE_AI_API_KEY", "test-api-key-12345")
    monkeypatch.setenv("CU_API_VERSION", "2025-11-01")


def has_azure_credentials() -> bool:
    return bool(os.environ.get("AZURE_AI_ENDPOINT") and os.environ.get("AZURE_AI_API_KEY"))


@pytest.fixture
def requires_credentials():
    if not has_azure_credentials():
        pytest.skip("Azure credentials not available")


def pytest_collection_modifyitems(config, items):
    """Automatically skip integration tests when credentials are unavailable."""
    if has_azure_credentials():
        return
    skip_credentials = pytest.mark.skip(reason="Azure credentials not available")
    for item in items:
        if "requires_credentials" in item.keywords or "integration" in item.keywords:
            item.add_marker(skip_credentials)
        if "test_integration" in str(item.fspath):
            item.add_marker(skip_credentials)
