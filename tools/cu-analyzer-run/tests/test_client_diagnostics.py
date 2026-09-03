"""Tests for diagnostic request headers in the shared CU client."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from content_understanding_client import AzureContentUnderstandingClient


def create_client() -> AzureContentUnderstandingClient:
    return AzureContentUnderstandingClient(
        endpoint="https://example.services.ai.azure.com",
        api_version="2025-11-01",
        subscription_key="test-key",
    )


@patch("content_understanding_client.requests.post")
def test_begin_analyze_binary_adds_diagnostics_header(mock_post, tmp_path: Path):
    sample = tmp_path / "sample.pdf"
    sample.write_bytes(b"%PDF-1.4")
    mock_post.return_value = MagicMock(ok=True)

    create_client().begin_analyze_binary(
        "prebuilt-invoice",
        str(sample),
        diagnostics=True,
    )

    assert mock_post.call_args.kwargs["headers"]["x-ms-diagnostics"] == "true"


@patch("content_understanding_client.requests.post")
def test_begin_analyze_url_omits_diagnostics_header_by_default(mock_post):
    mock_post.return_value = MagicMock(ok=True)

    create_client().begin_analyze_url(
        "prebuilt-invoice",
        "https://example.com/invoice.pdf",
    )

    assert "x-ms-diagnostics" not in mock_post.call_args.kwargs["headers"]


@patch("content_understanding_client.time.sleep")
@patch("content_understanding_client.requests.get")
def test_poll_result_adds_diagnostics_header(mock_get, _mock_sleep):
    initial_response = MagicMock()
    initial_response.headers = {
        "operation-location": (
            "https://example.services.ai.azure.com/"
            "contentunderstanding/analyzerResults/result-1"
            "?api-version=2025-11-01"
        )
    }
    completed_response = MagicMock(ok=True)
    completed_response.json.return_value = {"status": "succeeded"}
    mock_get.return_value = completed_response

    create_client().poll_result(initial_response, diagnostics=True)

    assert mock_get.call_args.kwargs["headers"]["x-ms-diagnostics"] == "true"
