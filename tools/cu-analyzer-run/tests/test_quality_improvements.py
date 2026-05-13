"""
Tests for new quality improvement features:
  - discover_schema_dir / build_schema_dag / topo_sort_schemas
  - extract_token_usage
  - comparison report (load_result_files, extract_confidence_map, extract_value_map, generate_comparison_report)
"""
import json
import sys
from pathlib import Path

import pytest

TOOLS_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(TOOLS_ROOT / "cu-analyzer-run"))
sys.path.insert(0, str(TOOLS_ROOT / "cu-client"))
sys.path.insert(0, str(TOOLS_ROOT / "cu-analyzer-validate"))

from create_and_test import (
    build_schema_dag,
    discover_schema_dir,
    extract_confidence_map,
    extract_token_usage,
    extract_value_map,
    find_root_schemas,
    generate_comparison_report,
    load_result_files,
    topo_sort_schemas,
)

REPO_ROOT = TOOLS_ROOT.parent


# ===========================================================================
# Fixtures
# ===========================================================================

def _write_schema(path, analyzer_id, categories=None, fields=None):
    """Helper to write a schema file."""
    schema = {
        "analyzerId": analyzer_id,
        "description": f"Test schema {analyzer_id}",
        "baseAnalyzerId": "prebuilt-document",
    }
    if categories:
        schema["config"] = {
            "enableSegment": True,
            "contentCategories": categories,
            "omitContent": True,
        }
    if fields:
        schema["fieldSchema"] = {"fields": fields}
    path.write_text(json.dumps(schema), encoding="utf-8")


def _write_result(path, doc_name, fields, usage=None):
    """Helper to write a CU result file."""
    result = {
        "_metadata": {"document": doc_name, "run_id": "test", "iteration": 1},
        "result": {"fields": fields},
    }
    if usage:
        result["usage"] = usage
    path.write_text(json.dumps(result), encoding="utf-8")


# ===========================================================================
# discover_schema_dir
# ===========================================================================

class TestDiscoverSchemaDir:

    def test_basic_discovery(self, tmp_path):
        _write_schema(tmp_path / "inner.json", "inner_ext", fields={"F": {"type": "string"}})
        _write_schema(tmp_path / "outer.json", "outer_cls", categories={
            "cat1": {"description": "Cat 1", "analyzerId": "inner_ext"}
        })
        schemas, paths = discover_schema_dir(tmp_path)
        assert set(schemas.keys()) == {"inner_ext", "outer_cls"}
        assert paths["inner_ext"].name == "inner.json"

    def test_skips_non_schema_json(self, tmp_path):
        (tmp_path / "readme.json").write_text('{"title": "README"}', encoding="utf-8")
        _write_schema(tmp_path / "analyzer.json", "my_analyzer", fields={"F": {"type": "string"}})
        schemas, _ = discover_schema_dir(tmp_path)
        assert len(schemas) == 1
        assert "my_analyzer" in schemas

    def test_errors_on_schema_without_id(self, tmp_path):
        schema = {"baseAnalyzerId": "prebuilt-document", "fieldSchema": {"fields": {}}}
        (tmp_path / "bad.json").write_text(json.dumps(schema), encoding="utf-8")
        with pytest.raises(ValueError, match="no analyzerId"):
            discover_schema_dir(tmp_path)

    def test_errors_on_duplicate_id(self, tmp_path):
        _write_schema(tmp_path / "a.json", "same_id", fields={"F": {"type": "string"}})
        _write_schema(tmp_path / "b.json", "same_id", fields={"G": {"type": "string"}})
        with pytest.raises(ValueError, match="Duplicate analyzerId"):
            discover_schema_dir(tmp_path)

    def test_errors_on_invalid_json(self, tmp_path):
        (tmp_path / "bad.json").write_text("{invalid json", encoding="utf-8")
        with pytest.raises(ValueError, match="Invalid JSON"):
            discover_schema_dir(tmp_path)

    def test_errors_on_empty_dir(self, tmp_path):
        with pytest.raises(ValueError, match="No analyzer schemas found"):
            discover_schema_dir(tmp_path)

    def test_real_template_schemas(self):
        d = REPO_ROOT / "Issues" / "_TEMPLATE" / "schemas" / "classify_route_example"
        if not d.exists():
            pytest.skip("Template schemas not found")
        schemas, paths = discover_schema_dir(d)
        assert len(schemas) == 3
        assert "doc_classifier" in schemas
        assert "invoice_extractor" in schemas
        assert "receipt_extractor" in schemas


# ===========================================================================
# build_schema_dag / topo_sort / find_root
# ===========================================================================

class TestSchemaDag:

    def test_simple_dag(self):
        schemas = {
            "leaf1": {"config": {}},
            "leaf2": {"config": {}},
            "root": {"config": {"contentCategories": {
                "a": {"analyzerId": "leaf1"},
                "b": {"analyzerId": "leaf2"},
            }}}
        }
        dag = build_schema_dag(schemas)
        assert dag == {"leaf1": [], "leaf2": [], "root": ["leaf1", "leaf2"]}

    def test_topo_sort_leaf_first(self):
        dag = {"leaf1": [], "leaf2": [], "root": ["leaf1", "leaf2"]}
        order = topo_sort_schemas(dag)
        assert order.index("leaf1") < order.index("root")
        assert order.index("leaf2") < order.index("root")

    def test_three_level_nesting(self):
        dag = {
            "inner": [],
            "mid": ["inner"],
            "outer": ["mid"],
        }
        order = topo_sort_schemas(dag)
        assert order == ["inner", "mid", "outer"]

    def test_cycle_detection(self):
        dag = {"a": ["b"], "b": ["a"]}
        with pytest.raises(ValueError, match="Circular dependency"):
            topo_sort_schemas(dag)

    def test_external_refs_excluded(self):
        schemas = {
            "local": {"config": {"contentCategories": {
                "a": {"analyzerId": "external_deployed_analyzer"},
            }}}
        }
        dag = build_schema_dag(schemas)
        # external_deployed_analyzer is NOT in schemas, so not in deps
        assert dag == {"local": []}

    def test_find_root_schemas(self):
        dag = {"leaf1": [], "leaf2": [], "mid": ["leaf1"], "root": ["mid", "leaf2"]}
        roots = find_root_schemas(dag)
        assert roots == ["root"]

    def test_find_multiple_roots(self):
        dag = {"a": [], "b": [], "c": ["a"]}
        roots = find_root_schemas(dag)
        assert sorted(roots) == ["b", "c"]

    def test_real_template_dag(self):
        d = REPO_ROOT / "Issues" / "_TEMPLATE" / "schemas" / "classify_route_example"
        if not d.exists():
            pytest.skip("Template schemas not found")
        schemas, _ = discover_schema_dir(d)
        dag = build_schema_dag(schemas)
        order = topo_sort_schemas(dag)
        # doc_classifier should be last (it references the others)
        assert order[-1] == "doc_classifier"
        roots = find_root_schemas(dag)
        assert roots == ["doc_classifier"]


# ===========================================================================
# extract_token_usage
# ===========================================================================

class TestExtractTokenUsage:

    def test_standard_result(self):
        result = {
            "usage": {
                "documentPagesStandard": 2,
                "contextualizationTokens": 1000,
                "tokens": {"gpt-4.1-input": 5000, "gpt-4.1-output": 300}
            }
        }
        usage = extract_token_usage(result)
        assert usage["input_tokens"] == 5000
        assert usage["output_tokens"] == 300
        assert usage["total_tokens"] == 5300
        assert usage["contextualization_tokens"] == 1000
        assert usage["document_pages"] == 2

    def test_empty_result(self):
        usage = extract_token_usage({})
        assert usage["input_tokens"] == 0
        assert usage["output_tokens"] == 0
        assert usage["total_tokens"] == 0

    def test_multi_model_tokens(self):
        result = {
            "usage": {
                "tokens": {
                    "gpt-4.1-input": 3000,
                    "gpt-4.1-output": 200,
                    "gpt-4o-input": 1000,
                    "gpt-4o-output": 50,
                }
            }
        }
        usage = extract_token_usage(result)
        assert usage["input_tokens"] == 4000
        assert usage["output_tokens"] == 250


# ===========================================================================
# Comparison report
# ===========================================================================

class TestComparisonReport:

    @pytest.fixture
    def prev_dir(self, tmp_path):
        d = tmp_path / "prev"
        d.mkdir()
        _write_result(d / "doc1.json", "doc1.pdf", {
            "Name": {"valueString": "Alice", "confidence": 0.9},
            "Total": {"valueNumber": 100.0, "confidence": 0.8},
        })
        return d

    @pytest.fixture
    def curr_dir(self, tmp_path):
        d = tmp_path / "curr"
        d.mkdir()
        _write_result(d / "doc1.json", "doc1.pdf", {
            "Name": {"valueString": "Alice", "confidence": 0.95},
            "Total": {"valueNumber": 105.0, "confidence": 0.85},
        })
        return d

    def test_load_result_files(self, prev_dir):
        results = load_result_files(prev_dir)
        assert "doc1.pdf" in results

    def test_load_skips_metadata(self, prev_dir):
        (prev_dir / "metadata.json").write_text('{"test": true}', encoding="utf-8")
        results = load_result_files(prev_dir)
        assert len(results) == 1

    def test_extract_confidence_map(self):
        result = {"result": {"fields": {
            "Name": {"valueString": "X", "confidence": 0.9},
            "Score": {"valueNumber": 5, "confidence": 0.7},
        }}}
        conf = extract_confidence_map(result)
        assert conf == {"Name": 0.9, "Score": 0.7}

    def test_extract_value_map(self):
        result = {"result": {"fields": {
            "Name": {"valueString": "Alice", "confidence": 0.9},
            "Total": {"valueNumber": 100, "confidence": 0.8},
        }}}
        vals = extract_value_map(result)
        assert vals == {"Name": "Alice", "Total": 100}

    def test_generate_comparison_report(self, prev_dir, curr_dir, tmp_path):
        report_path = tmp_path / "comparison.md"
        generate_comparison_report(curr_dir, prev_dir, report_path)
        assert report_path.exists()
        content = report_path.read_text(encoding="utf-8")
        assert "Comparison Report" in content
        assert "doc1.pdf" in content
        assert "Name" in content
        assert "Total" in content

    def test_comparison_confidence_delta(self, prev_dir, curr_dir, tmp_path):
        report_path = tmp_path / "comparison.md"
        generate_comparison_report(curr_dir, prev_dir, report_path)
        content = report_path.read_text(encoding="utf-8")
        assert "+0.050" in content  # Name confidence delta
        assert "+0.050" in content  # Total confidence delta

    def test_comparison_empty_previous(self, curr_dir, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        with pytest.raises(ValueError, match="No results found"):
            generate_comparison_report(curr_dir, empty, tmp_path / "report.md")

    def test_comparison_no_matching_docs(self, tmp_path):
        prev = tmp_path / "prev"
        prev.mkdir()
        curr = tmp_path / "curr"
        curr.mkdir()
        _write_result(prev / "a.json", "a.pdf", {"X": {"valueString": "1", "confidence": 0.9}})
        _write_result(curr / "b.json", "b.pdf", {"X": {"valueString": "2", "confidence": 0.9}})
        report_path = tmp_path / "report.md"
        generate_comparison_report(curr, prev, report_path)
        content = report_path.read_text(encoding="utf-8")
        assert "No matching documents" in content
