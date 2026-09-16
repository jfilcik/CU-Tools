"""Unit tests for cu_cli.cli argument parsing and dispatch (mocked operations)."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from cu_cli import cli as cu_cli_cli


@pytest.fixture
def patched_get_client(mock_client):
    with patch("cu_cli.operations.get_client", return_value=mock_client) as p:
        yield p, mock_client


class TestValidateSetupCommand:
    def test_validate_setup(self, patched_get_client, capsys):
        _, mock_client = patched_get_client
        rc = cu_cli_cli.main(["validate-setup", "--verbose"])
        assert rc == 0
        mock_client.validate_setup.assert_called_once_with(verbose=True)
        out = json.loads(capsys.readouterr().out)
        assert "modelDeployments" in out


class TestAnalyzerCommands:
    def test_analyzer_list(self, patched_get_client, capsys):
        rc = cu_cli_cli.main(["analyzer", "list"])
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert out == [{"analyzerId": "test-analyzer"}]

    def test_analyzer_get(self, patched_get_client):
        _, mock_client = patched_get_client
        rc = cu_cli_cli.main(["analyzer", "get", "--analyzer-id", "abc"])
        assert rc == 0
        mock_client.get_analyzer_detail_by_id.assert_called_once_with("abc")

    def test_analyzer_create(self, patched_get_client, tmp_path):
        _, mock_client = patched_get_client
        schema_path = tmp_path / "schema.json"
        schema_path.write_text(json.dumps({"description": "test"}))
        rc = cu_cli_cli.main([
            "analyzer", "create", "--analyzer-id", "abc", "--schema", str(schema_path),
        ])
        assert rc == 0
        mock_client.begin_create_analyzer.assert_called_once()

    def test_analyzer_create_missing_schema_file(self, patched_get_client, capsys):
        rc = cu_cli_cli.main([
            "analyzer", "create", "--analyzer-id", "abc", "--schema", "does-not-exist.json",
        ])
        assert rc == 1
        assert "not found" in capsys.readouterr().err

    def test_analyzer_delete(self, patched_get_client):
        _, mock_client = patched_get_client
        rc = cu_cli_cli.main(["analyzer", "delete", "--analyzer-id", "abc"])
        assert rc == 0
        mock_client.delete_analyzer.assert_called_once_with("abc")


class TestAnalyzeCommands:
    def test_analyze_file(self, patched_get_client, tmp_path):
        _, mock_client = patched_get_client
        file_path = tmp_path / "doc.pdf"
        file_path.write_bytes(b"%PDF-1.4 fake")
        rc = cu_cli_cli.main([
            "analyze", "file", "--analyzer-id", "abc", "--input", str(file_path),
        ])
        assert rc == 0
        mock_client.begin_analyze_binary.assert_called_once()

    def test_analyze_url(self, patched_get_client):
        _, mock_client = patched_get_client
        rc = cu_cli_cli.main([
            "analyze", "url", "--analyzer-id", "abc", "--url", "https://example.com/doc.pdf",
        ])
        assert rc == 0
        mock_client.begin_analyze_url.assert_called_once()

    def test_analyze_file_writes_output(self, patched_get_client, tmp_path):
        file_path = tmp_path / "doc.pdf"
        file_path.write_bytes(b"%PDF-1.4 fake")
        output_path = tmp_path / "result.json"
        rc = cu_cli_cli.main([
            "analyze", "file", "--analyzer-id", "abc", "--input", str(file_path),
            "--output", str(output_path),
        ])
        assert rc == 0
        assert output_path.exists()
        assert json.loads(output_path.read_text())["status"] == "Succeeded"


class TestClassifierCommands:
    def test_classifier_create(self, patched_get_client, tmp_path):
        _, mock_client = patched_get_client
        schema_path = tmp_path / "schema.json"
        schema_path.write_text(json.dumps({"description": "test"}))
        rc = cu_cli_cli.main([
            "classifier", "create", "--classifier-id", "c1", "--schema", str(schema_path),
        ])
        assert rc == 0
        mock_client.begin_create_classifier.assert_called_once()

    def test_classify(self, patched_get_client):
        _, mock_client = patched_get_client
        rc = cu_cli_cli.main(["classify", "--classifier-id", "c1", "--input", "doc.pdf"])
        assert rc == 0
        mock_client.begin_classify.assert_called_once_with("c1", "doc.pdf")


class TestDefaultsCommands:
    def test_defaults_get(self, patched_get_client):
        rc = cu_cli_cli.main(["defaults", "get"])
        assert rc == 0

    def test_defaults_set(self, patched_get_client):
        _, mock_client = patched_get_client
        mock_client.update_defaults.return_value = {"modelDeployments": {"gpt-4.1": "d1"}}
        rc = cu_cli_cli.main(["defaults", "set", "--model", "gpt-4.1=d1"])
        assert rc == 0
        mock_client.update_defaults.assert_called_once_with({"gpt-4.1": "d1"})

    def test_defaults_set_invalid_model_arg(self, patched_get_client, capsys):
        rc = cu_cli_cli.main(["defaults", "set", "--model", "invalid-no-equals"])
        assert rc == 1
        assert "Error" in capsys.readouterr().err


class TestErrorHandling:
    def test_missing_credentials_returns_error_code(self, monkeypatch, capsys):
        monkeypatch.delenv("AZURE_AI_ENDPOINT", raising=False)
        monkeypatch.delenv("AZURE_AI_API_KEY", raising=False)
        with patch("cu_cli.operations.load_dotenv"):
            rc = cu_cli_cli.main(["analyzer", "list"])
        assert rc == 1
        assert "AZURE_AI_ENDPOINT" in capsys.readouterr().err
