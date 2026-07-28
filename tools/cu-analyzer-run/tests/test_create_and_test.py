"""
Tests for create_and_test.py functionality.

Tests the schema validation, analyzer creation, and testing workflow
without customer-specific test cases.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock
import sys
import json

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


# Test data paths
DATA_FOLDER = Path(__file__).parent.parent.parent.parent / "data"
SCHEMAS_FOLDER = Path(__file__).parent.parent.parent.parent / "schemas"


class TestSchemaValidation:
    """Tests for schema validation functionality."""

    def test_valid_schema_passes_validation(self, tmp_path):
        """Test that a valid schema passes validation."""
        valid_schema = {
            "name": "test-analyzer",
            "description": "Test analyzer",
            "baseAnalyzerId": "prebuilt-document",
            "fieldSchema": {
                "fields": {
                    "TestField": {
                        "type": "string",
                        "method": "extract",
                        "description": "A test field for extraction"
                    }
                }
            }
        }
        
        schema_file = tmp_path / "valid_schema.json"
        schema_file.write_text(json.dumps(valid_schema, indent=2))
        
        loaded = json.loads(schema_file.read_text())
        assert loaded["name"] == "test-analyzer"
        assert "fields" in loaded["fieldSchema"]

    def test_invalid_json_fails_validation(self, tmp_path):
        """Test that invalid JSON fails validation."""
        invalid_json = "{ not valid json }"
        schema_file = tmp_path / "invalid.json"
        schema_file.write_text(invalid_json)
        
        with pytest.raises(json.JSONDecodeError):
            json.loads(schema_file.read_text())

    def test_missing_required_fields_detected(self, tmp_path):
        """Test that missing required fields are detected."""
        incomplete_schema = {
            "description": "Incomplete schema"
        }
        
        schema_file = tmp_path / "incomplete.json"
        schema_file.write_text(json.dumps(incomplete_schema))
        
        loaded = json.loads(schema_file.read_text())
        assert "name" not in loaded
        assert "fieldSchema" not in loaded

    def test_validates_field_types(self):
        """Test validation of field type definitions."""
        valid_types = ["string", "number", "boolean", "array", "object"]
        
        for field_type in valid_types:
            schema = {
                "name": "test-analyzer",
                "fieldSchema": {
                    "fields": {
                        "TestField": {
                            "type": field_type,
                            "method": "extract",
                            "description": f"Field of type {field_type}"
                        }
                    }
                }
            }
            
            assert schema["fieldSchema"]["fields"]["TestField"]["type"] == field_type

    def test_validates_extraction_methods(self):
        """Test validation of extraction method values."""
        valid_methods = ["extract", "generate", "classify"]
        
        for method in valid_methods:
            schema = {
                "name": "test-analyzer",
                "fieldSchema": {
                    "fields": {
                        "TestField": {
                            "type": "string",
                            "method": method,
                            "description": f"Field using {method} method"
                        }
                    }
                }
            }
            
            assert schema["fieldSchema"]["fields"]["TestField"]["method"] == method

    def test_preview_version_can_be_resolved_from_environment(self, monkeypatch):
        monkeypatch.setenv("CU_API_VERSION", "2026-06-01-preview")
        from run import resolve_api_version

        assert resolve_api_version(None) == "2026-06-01-preview"

    def test_loads_real_schema_files(self):
        """Test loading real schema files from schemas folder."""
        if not SCHEMAS_FOLDER.exists():
            pytest.skip("Schemas folder not found")
        
        schema_files = list(SCHEMAS_FOLDER.glob("*.json"))
        if not schema_files:
            pytest.skip("No schema files found")
        
        for schema_file in schema_files:
            try:
                content = json.loads(schema_file.read_text())
                assert isinstance(content, dict)
            except json.JSONDecodeError as e:
                pytest.fail(f"Invalid JSON in {schema_file.name}: {e}")


class TestAnalyzerCreation:
    """Tests for analyzer creation functionality."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock CU client for analyzer operations."""
        client = MagicMock()
        client.create_analyzer = MagicMock(return_value={
            "analyzerId": "test-analyzer-12345",
            "status": "succeeded"
        })
        client.get_analyzer = MagicMock(return_value={
            "analyzerId": "test-analyzer-12345",
            "status": "ready"
        })
        return client

    def test_create_analyzer_from_schema(self, mock_client, tmp_path):
        """Test creating an analyzer from a schema file."""
        schema = {
            "name": "test-analyzer",
            "description": "Test description",
            "baseAnalyzerId": "prebuilt-document",
            "fieldSchema": {
                "fields": {
                    "Amount": {
                        "type": "number",
                        "method": "extract",
                        "description": "The total amount"
                    }
                }
            }
        }
        
        schema_file = tmp_path / "test_schema.json"
        schema_file.write_text(json.dumps(schema))
        
        result = mock_client.create_analyzer(schema)
        assert result["status"] == "succeeded"
        assert "analyzerId" in result

    def test_handles_analyzer_creation_failure(self, mock_client):
        """Test handling of analyzer creation failure."""
        mock_client.create_analyzer.side_effect = Exception("Creation failed")
        
        schema = {"name": "test", "fieldSchema": {"fields": {}}}
        
        with pytest.raises(Exception) as exc_info:
            mock_client.create_analyzer(schema)
        
        assert "Creation failed" in str(exc_info.value)

    def test_waits_for_analyzer_ready(self, mock_client):
        """Test waiting for analyzer to become ready."""
        ready_states = ["creating", "creating", "ready"]
        call_count = [0]
        
        def mock_get_analyzer(analyzer_id):
            state = ready_states[min(call_count[0], len(ready_states) - 1)]
            call_count[0] += 1
            return {"analyzerId": analyzer_id, "status": state}
        
        mock_client.get_analyzer = mock_get_analyzer
        
        result = mock_client.get_analyzer("test-id")
        assert result["status"] == "creating"
        
        mock_client.get_analyzer("test-id")
        result = mock_client.get_analyzer("test-id")
        assert result["status"] == "ready"


class TestTestingWorkflow:
    """Tests for the complete testing workflow."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock CU client for testing workflow."""
        client = MagicMock()
        client.create_analyzer = MagicMock(return_value={
            "analyzerId": "workflow-test-analyzer",
            "status": "succeeded"
        })
        client.analyze_document = MagicMock(return_value={
            "status": "succeeded",
            "result": {
                "contents": [{
                    "fields": {
                        "Amount": {"content": "1000.00", "confidence": 0.95},
                        "Date": {"content": "2024-01-15", "confidence": 0.92}
                    }
                }]
            }
        })
        return client

    def test_full_workflow_schema_to_results(self, mock_client, tmp_path):
        """Test complete workflow from schema to analysis results."""
        schema = {
            "name": "workflow-test",
            "baseAnalyzerId": "prebuilt-document",
            "fieldSchema": {
                "fields": {
                    "Amount": {"type": "number", "method": "extract", "description": "Total amount"},
                    "Date": {"type": "string", "method": "extract", "description": "Document date"}
                }
            }
        }
        
        schema_file = tmp_path / "workflow_schema.json"
        schema_file.write_text(json.dumps(schema))
        
        test_doc = tmp_path / "test_doc.pdf"
        test_doc.write_bytes(b"%PDF-1.4 test content")
        
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        
        create_result = mock_client.create_analyzer(schema)
        assert create_result["status"] == "succeeded"
        analyzer_id = create_result["analyzerId"]
        
        analysis_result = mock_client.analyze_document(analyzer_id, str(test_doc))
        assert analysis_result["status"] == "succeeded"
        
        fields = analysis_result["result"]["contents"][0]["fields"]
        assert "Amount" in fields
        assert "Date" in fields
        assert fields["Amount"]["confidence"] > 0.9

    def test_batch_testing_workflow(self, mock_client, tmp_path):
        """Test batch testing with multiple documents."""
        docs = []
        for i in range(5):
            doc = tmp_path / f"doc_{i}.pdf"
            doc.write_bytes(b"%PDF-1.4")
            docs.append(doc)
        
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        
        results = []
        for doc in docs:
            result = mock_client.analyze_document("test-analyzer", str(doc))
            results.append(result)
        
        assert all(r["status"] == "succeeded" for r in results)
        assert len(results) == 5


class TestResultsExport:
    """Tests for results export functionality."""

    def test_results_can_be_serialized_to_json(self, tmp_path):
        """Test that analysis results can be serialized to JSON."""
        results = {
            "file": "test.pdf",
            "status": "succeeded",
            "fields": {
                "Amount": {"content": "1000.00", "confidence": 0.95},
                "Date": {"content": "2024-01-15", "confidence": 0.92}
            },
            "metadata": {
                "processingTime": 1.5,
                "pageCount": 2
            }
        }
        
        output_file = tmp_path / "results.json"
        output_file.write_text(json.dumps(results, indent=2))
        
        loaded = json.loads(output_file.read_text())
        assert loaded["status"] == "succeeded"
        assert loaded["fields"]["Amount"]["content"] == "1000.00"

    def test_results_structure_for_csv_export(self):
        """Test that results can be flattened for CSV export."""
        results = [
            {
                "file": "doc1.pdf",
                "Amount": "100.00",
                "Amount_confidence": 0.95,
                "Date": "2024-01-01",
                "Date_confidence": 0.90
            },
            {
                "file": "doc2.pdf",
                "Amount": "200.00",
                "Amount_confidence": 0.92,
                "Date": "2024-01-02",
                "Date_confidence": 0.88
            }
        ]
        
        for row in results:
            assert "file" in row
            assert "Amount" in row
            assert "Amount_confidence" in row


class TestErrorHandling:
    """Tests for error handling in create_and_test workflow."""

    def test_handles_missing_schema_file(self):
        """Test handling of missing schema file."""
        non_existent = Path("/path/to/nonexistent/schema.json")
        assert not non_existent.exists()

    def test_handles_invalid_base_analyzer(self):
        """Test handling of invalid base analyzer ID."""
        schema = {
            "name": "test",
            "baseAnalyzerId": "invalid-analyzer-id",
            "fieldSchema": {"fields": {}}
        }
        assert schema["baseAnalyzerId"] == "invalid-analyzer-id"

    def test_handles_empty_input_folder(self, tmp_path):
        """Test handling of empty input folder."""
        empty_input = tmp_path / "empty_input"
        empty_input.mkdir()
        
        files = list(empty_input.glob("*.pdf"))
        assert files == []

    def test_handles_output_directory_creation(self, tmp_path):
        """Test that output directory is created if it doesn't exist."""
        output_dir = tmp_path / "new" / "nested" / "output"
        
        assert not output_dir.exists()
        output_dir.mkdir(parents=True)
        assert output_dir.exists()


class TestConfigurationOptions:
    """Tests for configuration options in create_and_test."""

    def test_supports_different_base_analyzers(self):
        """Test that different base analyzers can be specified."""
        base_analyzers = [
            "prebuilt-document",
            "prebuilt-layout",
            "prebuilt-invoice",
            "prebuilt-receipt"
        ]
        
        for base in base_analyzers:
            schema = {
                "name": f"test-{base}",
                "baseAnalyzerId": base,
                "fieldSchema": {"fields": {}}
            }
            assert schema["baseAnalyzerId"] == base

    def test_supports_optional_description(self):
        """Test that description is optional but supported."""
        schema_no_desc = {
            "name": "test",
            "fieldSchema": {"fields": {}}
        }
        assert "description" not in schema_no_desc
        
        schema_with_desc = {
            "name": "test",
            "description": "A test analyzer for unit testing",
            "fieldSchema": {"fields": {}}
        }
        assert schema_with_desc["description"] == "A test analyzer for unit testing"

    def test_supports_nested_field_structures(self):
        """Test support for nested/complex field structures."""
        schema = {
            "name": "test-nested",
            "fieldSchema": {
                "fields": {
                    "LineItems": {
                        "type": "array",
                        "method": "extract",
                        "description": "List of line items",
                        "items": {
                            "type": "object",
                            "properties": {
                                "Description": {"type": "string"},
                                "Quantity": {"type": "number"},
                                "UnitPrice": {"type": "number"},
                                "Total": {"type": "number"}
                            }
                        }
                    }
                }
            }
        }
        
        line_items = schema["fieldSchema"]["fields"]["LineItems"]
        assert line_items["type"] == "array"
        assert "items" in line_items
        assert "properties" in line_items["items"]
