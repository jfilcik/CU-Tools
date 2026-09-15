"""Unit tests for cu_cli.operations (mocked client, no network calls)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from cu_cli import operations as ops


class TestGetClient:
    def test_get_client_uses_env_vars(self, mock_env_vars):
        client = ops.get_client()
        assert client is not None

    def test_get_client_missing_endpoint_raises(self, monkeypatch):
        monkeypatch.delenv("AZURE_AI_ENDPOINT", raising=False)
        monkeypatch.delenv("AZURE_AI_API_KEY", raising=False)
        monkeypatch.setenv("AZURE_AI_API_KEY", "key")
        with pytest.raises(ops.CUCliError, match="AZURE_AI_ENDPOINT"):
            ops.get_client()

    def test_get_client_missing_api_key_raises(self, monkeypatch):
        monkeypatch.delenv("AZURE_AI_ENDPOINT", raising=False)
        monkeypatch.delenv("AZURE_AI_API_KEY", raising=False)
        monkeypatch.setenv("AZURE_AI_ENDPOINT", "https://example.com")
        with pytest.raises(ops.CUCliError, match="AZURE_AI_API_KEY"):
            ops.get_client()

    def test_get_client_explicit_args_override_env(self, mock_env_vars):
        client = ops.get_client(endpoint="https://explicit.example.com", api_key="explicit-key")
        assert client is not None


class TestResolveApiVersion:
    def test_default(self, monkeypatch):
        monkeypatch.delenv("CU_API_VERSION", raising=False)
        assert ops.resolve_api_version() == ops.DEFAULT_API_VERSION

    def test_explicit(self):
        assert ops.resolve_api_version("2026-06-01-preview") == "2026-06-01-preview"

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("CU_API_VERSION", "2099-01-01")
        assert ops.resolve_api_version() == "2099-01-01"

    def test_blank_raises(self):
        with pytest.raises(ops.CUCliError):
            ops.resolve_api_version("   ")


class TestValidateSetup:
    def test_validate_setup_calls_client(self, mock_client):
        result = ops.validate_setup(mock_client, verbose=True)
        mock_client.validate_setup.assert_called_once_with(verbose=True)
        assert "modelDeployments" in result


class TestAnalyzerOperations:
    def test_list_analyzers(self, mock_client):
        result = ops.list_analyzers(mock_client)
        assert result == [{"analyzerId": "test-analyzer"}]

    def test_get_analyzer(self, mock_client):
        result = ops.get_analyzer(mock_client, "test-analyzer")
        mock_client.get_analyzer_detail_by_id.assert_called_once_with("test-analyzer")
        assert result["status"] == "Succeeded"

    def test_create_analyzer_and_wait_success(self, mock_client):
        result = ops.create_analyzer_and_wait(
            mock_client, "test-analyzer", {"description": "test"}, poll_interval=1
        )
        mock_client.begin_create_analyzer.assert_called_once()
        assert result["status"] == "Succeeded"

    def test_create_analyzer_and_wait_deletes_existing_first(self, mock_client):
        ops.create_analyzer_and_wait(
            mock_client, "test-analyzer", {"description": "test"}, poll_interval=1
        )
        mock_client.delete_analyzer.assert_called_once_with("test-analyzer")

    def test_create_analyzer_and_wait_no_replace_skips_delete(self, mock_client):
        ops.create_analyzer_and_wait(
            mock_client, "test-analyzer", {"description": "test"},
            poll_interval=1, replace_existing=False,
        )
        mock_client.delete_analyzer.assert_not_called()

    def test_create_analyzer_and_wait_failed_status_raises(self, mock_client):
        mock_client.get_analyzer_detail_by_id.return_value = {"status": "Failed", "error": "bad schema"}
        with pytest.raises(ops.CUCliError, match="failed"):
            ops.create_analyzer_and_wait(
                mock_client, "test-analyzer", {"description": "test"}, poll_interval=1
            )

    def test_create_analyzer_and_wait_timeout_raises(self, mock_client):
        mock_client.get_analyzer_detail_by_id.return_value = {"status": "Running"}
        with pytest.raises(ops.CUCliError, match="not ready"):
            ops.create_analyzer_and_wait(
                mock_client, "test-analyzer", {"description": "test"},
                max_wait=1, poll_interval=1,
            )

    def test_create_analyzer_and_wait_progress_callback(self, mock_client):
        seen = []
        ops.create_analyzer_and_wait(
            mock_client, "test-analyzer", {"description": "test"},
            poll_interval=1, on_progress=lambda status, elapsed: seen.append((status, elapsed)),
        )
        assert seen == [("Succeeded", 0)]

    def test_create_analyzer_and_wait_tolerates_transient_polling_errors(self, mock_client):
        mock_client.get_analyzer_detail_by_id.side_effect = [
            RuntimeError("transient network blip"),
            {"status": "Succeeded"},
        ]
        result = ops.create_analyzer_and_wait(
            mock_client, "test-analyzer", {"description": "test"}, poll_interval=1
        )
        assert result["status"] == "Succeeded"
        assert mock_client.get_analyzer_detail_by_id.call_count == 2

    def test_create_analyzer_and_wait_rejects_non_positive_poll_interval(self, mock_client):
        with pytest.raises(ops.CUCliError, match="poll_interval"):
            ops.create_analyzer_and_wait(
                mock_client, "test-analyzer", {"description": "test"}, poll_interval=0
            )

    def test_delete_analyzer(self, mock_client):
        ops.delete_analyzer(mock_client, "test-analyzer")
        mock_client.delete_analyzer.assert_called_once_with("test-analyzer")

    def test_delete_analyzer_safe_swallows_errors(self, mock_client):
        mock_client.delete_analyzer.side_effect = RuntimeError("boom")
        errors = []
        result = ops.delete_analyzer_safe(mock_client, "test-analyzer", on_error=errors.append)
        assert result is False
        assert len(errors) == 1

    def test_delete_analyzer_safe_success(self, mock_client):
        result = ops.delete_analyzer_safe(mock_client, "test-analyzer")
        assert result is True

    def test_cleanup_analyzer_set_reverse_order(self, mock_client):
        deleted = []
        mock_client.delete_analyzer.side_effect = lambda aid: deleted.append(aid)
        ops.cleanup_analyzer_set(mock_client, ["a", "b", "c"])
        assert deleted == ["c", "b", "a"]


class TestAnalyzeOperations:
    def test_analyze_file_and_wait(self, mock_client, tmp_path):
        file_path = tmp_path / "doc.pdf"
        file_path.write_bytes(b"%PDF-1.4 fake")
        result = ops.analyze_file_and_wait(mock_client, "test-analyzer", file_path)
        mock_client.begin_analyze_binary.assert_called_once()
        mock_client.poll_result.assert_called_once()
        assert result["status"] == "Succeeded"

    def test_analyze_url_and_wait(self, mock_client):
        result = ops.analyze_url_and_wait(mock_client, "test-analyzer", "https://example.com/doc.pdf")
        mock_client.begin_analyze_url.assert_called_once_with(
            "test-analyzer", "https://example.com/doc.pdf", diagnostics=False
        )
        assert result["status"] == "Succeeded"

    def test_analyze_file_and_wait_diagnostics_flag(self, mock_client, tmp_path):
        file_path = tmp_path / "doc.pdf"
        file_path.write_bytes(b"%PDF-1.4 fake")
        ops.analyze_file_and_wait(mock_client, "test-analyzer", file_path, diagnostics=True)
        _, kwargs = mock_client.begin_analyze_binary.call_args
        assert kwargs["diagnostics"] is True


class TestClassifierOperations:
    def test_create_classifier_and_wait(self, mock_client):
        result = ops.create_classifier_and_wait(mock_client, "test-classifier", {"description": "test"}, poll_interval=1)
        mock_client.begin_create_classifier.assert_called_once()
        assert result["status"] == "Succeeded"

    def test_classify_and_wait(self, mock_client):
        result = ops.classify_and_wait(mock_client, "test-classifier", "doc.pdf")
        mock_client.begin_classify.assert_called_once_with("test-classifier", "doc.pdf")
        assert result["status"] == "Succeeded"


class TestDefaultsOperations:
    def test_get_defaults(self, mock_client):
        result = ops.get_defaults(mock_client)
        assert result["modelDeployments"]["gpt-4.1"] == "my-gpt41-deployment"

    def test_update_defaults(self, mock_client):
        mock_client.update_defaults.return_value = {"modelDeployments": {"gpt-4.1": "new-deployment"}}
        result = ops.update_defaults(mock_client, {"gpt-4.1": "new-deployment"})
        mock_client.update_defaults.assert_called_once_with({"gpt-4.1": "new-deployment"})
        assert result["modelDeployments"]["gpt-4.1"] == "new-deployment"
