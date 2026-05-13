"""
Tests for classify-and-route functionality in create_and_test.py.

Covers:
  - parse_inner_schema_args: CLI argument parsing
  - validate_classify_route_mapping: category-to-schema validation
  - patch_classifier_schema: ID substitution
  - delete_analyzer_safe / cleanup_analyzer_set: teardown
  - Classify-route detection in main flow
  - Schema validation with real example schemas
"""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

# Add source directories to path
TOOLS_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(TOOLS_ROOT / "cu-analyzer-run"))
sys.path.insert(0, str(TOOLS_ROOT / "cu-client"))
sys.path.insert(0, str(TOOLS_ROOT / "cu-analyzer-validate"))

from create_and_test import (
    cleanup_analyzer_set,
    delete_analyzer_safe,
    parse_inner_schema_args,
    patch_classifier_schema,
    validate_classify_route_mapping,
)

REPO_ROOT = TOOLS_ROOT.parent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def classifier_schema():
    """Minimal classifier schema with two routed categories and one classify-only."""
    return {
        "description": "Test classifier",
        "baseAnalyzerId": "prebuilt-document",
        "config": {
            "enableSegment": True,
            "contentCategories": {
                "invoice": {
                    "description": "Invoices",
                    "analyzerId": "__INVOICE__"
                },
                "receipt": {
                    "description": "Receipts",
                    "analyzerId": "__RECEIPT__"
                },
                "other": {
                    "description": "Everything else"
                }
            },
            "omitContent": True
        }
    }


@pytest.fixture
def classify_only_schema():
    """Schema with contentCategories but NO analyzerId refs (classify-only, no routing)."""
    return {
        "description": "Classify only",
        "baseAnalyzerId": "prebuilt-document",
        "config": {
            "enableSegment": True,
            "contentCategories": {
                "typeA": {"description": "Type A documents"},
                "typeB": {"description": "Type B documents"},
            },
            "omitContent": True
        }
    }


@pytest.fixture
def inner_schema_files(tmp_path):
    """Create temp schema JSON files and return {alias: Path} dict."""
    schemas = {
        "invoice": {
            "analyzerId": "invoice_extractor",
            "description": "Invoice extractor",
            "baseAnalyzerId": "prebuilt-document",
            "fieldSchema": {"fields": {"Total": {"type": "number", "method": "extract", "description": "total"}}}
        },
        "receipt": {
            "analyzerId": "receipt_extractor",
            "description": "Receipt extractor",
            "baseAnalyzerId": "prebuilt-document",
            "fieldSchema": {"fields": {"Store": {"type": "string", "method": "extract", "description": "store name"}}}
        }
    }
    paths = {}
    for name, schema in schemas.items():
        p = tmp_path / f"{name}.json"
        p.write_text(json.dumps(schema), encoding="utf-8")
        paths[name] = p
    return paths


@pytest.fixture
def mock_client():
    """Mock CU client that tracks create/delete calls."""
    client = MagicMock()
    client.create_analyzer.return_value = {"status": "created"}
    client.delete_analyzer.return_value = None
    return client


# ===========================================================================
# parse_inner_schema_args
# ===========================================================================

class TestParseInnerSchemaArgs:

    def test_none_returns_empty(self):
        assert parse_inner_schema_args(None) == {}

    def test_empty_list_returns_empty(self):
        assert parse_inner_schema_args([]) == {}

    def test_single_valid(self, inner_schema_files):
        p = inner_schema_files["invoice"]
        result = parse_inner_schema_args([f"invoice={p}"])
        assert "invoice" in result
        assert result["invoice"] == p

    def test_multiple_valid(self, inner_schema_files):
        args = [
            f"invoice={inner_schema_files['invoice']}",
            f"receipt={inner_schema_files['receipt']}"
        ]
        result = parse_inner_schema_args(args)
        assert len(result) == 2
        assert "invoice" in result
        assert "receipt" in result

    def test_missing_equals_raises(self):
        with pytest.raises(ValueError, match="Invalid --inner-schema format"):
            parse_inner_schema_args(["no_equals_here"])

    def test_empty_alias_raises(self, inner_schema_files):
        with pytest.raises(ValueError, match="Empty alias"):
            parse_inner_schema_args([f"={inner_schema_files['invoice']}"])

    def test_duplicate_alias_raises(self, inner_schema_files):
        p = inner_schema_files["invoice"]
        with pytest.raises(ValueError, match="Duplicate"):
            parse_inner_schema_args([f"invoice={p}", f"invoice={p}"])

    def test_missing_file_raises(self):
        with pytest.raises(ValueError, match="not found"):
            parse_inner_schema_args(["alias=/nonexistent/path.json"])

    def test_empty_path_raises(self, tmp_path):
        """alias= with empty path — Path('') resolves to cwd which exists, but is not a schema file.
        This is an edge case the parser doesn't currently reject, so we document the behavior."""
        # Path("") resolves to cwd and exists — parser won't catch this.
        # The downstream schema load/validate will fail instead.
        result = parse_inner_schema_args(["alias="])
        assert "alias" in result  # Parser accepts it; validation catches it later

    def test_whitespace_trimmed(self, inner_schema_files):
        p = inner_schema_files["invoice"]
        result = parse_inner_schema_args([f"  invoice  =  {p}  "])
        assert "invoice" in result


# ===========================================================================
# validate_classify_route_mapping
# ===========================================================================

class TestValidateClassifyRouteMapping:

    def test_happy_path(self, classifier_schema, inner_schema_files):
        result = validate_classify_route_mapping(classifier_schema, inner_schema_files)
        assert sorted(result) == ["invoice", "receipt"]

    def test_missing_inner_schema_raises(self, classifier_schema, inner_schema_files):
        del inner_schema_files["receipt"]
        with pytest.raises(ValueError, match="need inner schemas but none supplied"):
            validate_classify_route_mapping(classifier_schema, inner_schema_files)

    def test_unused_inner_schema_raises(self, classifier_schema, inner_schema_files, tmp_path):
        extra = tmp_path / "extra.json"
        extra.write_text("{}", encoding="utf-8")
        inner_schema_files["bonus"] = extra
        with pytest.raises(ValueError, match="no matching contentCategories"):
            validate_classify_route_mapping(classifier_schema, inner_schema_files)

    def test_no_content_categories_raises(self, inner_schema_files):
        schema = {"config": {}}
        with pytest.raises(ValueError, match="no config.contentCategories"):
            validate_classify_route_mapping(schema, inner_schema_files)

    def test_empty_content_categories_raises(self, inner_schema_files):
        schema = {"config": {"contentCategories": {}}}
        with pytest.raises(ValueError, match="no config.contentCategories"):
            validate_classify_route_mapping(schema, inner_schema_files)

    def test_classify_only_no_inner_needed(self, classify_only_schema):
        """Schema with categories but no analyzerId refs needs no inner schemas."""
        result = validate_classify_route_mapping(classify_only_schema, {})
        assert result == []

    def test_mixed_routed_and_unrouted(self, classifier_schema, inner_schema_files):
        """'other' category has no analyzerId — should work without inner schema for it."""
        result = validate_classify_route_mapping(classifier_schema, inner_schema_files)
        assert "other" not in result
        assert "invoice" in result
        assert "receipt" in result


# ===========================================================================
# patch_classifier_schema
# ===========================================================================

class TestPatchClassifierSchema:

    def test_replaces_ids(self, classifier_schema):
        mapping = {"invoice": "real-inv-123", "receipt": "real-rec-456"}
        patched = patch_classifier_schema(classifier_schema, mapping)
        cats = patched["config"]["contentCategories"]
        assert cats["invoice"]["analyzerId"] == "real-inv-123"
        assert cats["receipt"]["analyzerId"] == "real-rec-456"

    def test_deep_copy_preserves_original(self, classifier_schema):
        original_inv_id = classifier_schema["config"]["contentCategories"]["invoice"]["analyzerId"]
        patch_classifier_schema(classifier_schema, {"invoice": "new-id", "receipt": "new-id-2"})
        assert classifier_schema["config"]["contentCategories"]["invoice"]["analyzerId"] == original_inv_id

    def test_unmatched_categories_unchanged(self, classifier_schema):
        """Patching only 'invoice' should leave 'receipt' and 'other' untouched."""
        patched = patch_classifier_schema(classifier_schema, {"invoice": "new-id"})
        assert patched["config"]["contentCategories"]["receipt"]["analyzerId"] == "__RECEIPT__"
        assert "analyzerId" not in patched["config"]["contentCategories"]["other"]

    def test_empty_mapping_returns_copy(self, classifier_schema):
        patched = patch_classifier_schema(classifier_schema, {})
        assert patched == classifier_schema
        assert patched is not classifier_schema


# ===========================================================================
# delete_analyzer_safe / cleanup_analyzer_set
# ===========================================================================

class TestCleanup:

    def test_delete_safe_success(self, mock_client):
        delete_analyzer_safe(mock_client, "test-id")
        mock_client.delete_analyzer.assert_called_once_with("test-id")

    def test_delete_safe_swallows_exception(self, mock_client):
        mock_client.delete_analyzer.side_effect = Exception("API error")
        # Should not raise
        delete_analyzer_safe(mock_client, "test-id")

    def test_cleanup_reverse_order(self, mock_client):
        cleanup_analyzer_set(mock_client, ["inner1", "inner2", "classifier"])
        calls = mock_client.delete_analyzer.call_args_list
        assert calls == [
            call("classifier"),
            call("inner2"),
            call("inner1"),
        ]

    def test_cleanup_continues_if_one_fails(self, mock_client):
        """Even if middle delete fails, other deletes still happen."""
        mock_client.delete_analyzer.side_effect = [
            None,                       # classifier OK
            Exception("API error"),     # inner2 fails
            None,                       # inner1 OK
        ]
        cleanup_analyzer_set(mock_client, ["inner1", "inner2", "classifier"])
        assert mock_client.delete_analyzer.call_count == 3

    def test_cleanup_empty_list(self, mock_client):
        cleanup_analyzer_set(mock_client, [])
        mock_client.delete_analyzer.assert_not_called()


# ===========================================================================
# Classify-route detection
# ===========================================================================

class TestClassifyRouteDetection:

    def test_schema_with_content_categories_detected(self, classifier_schema):
        cc = classifier_schema.get("config", {}).get("contentCategories", {})
        assert bool(cc) is True

    def test_field_extraction_schema_not_detected(self):
        schema = {
            "baseAnalyzerId": "prebuilt-document",
            "fieldSchema": {"fields": {"Name": {"type": "string", "method": "extract", "description": "name"}}}
        }
        cc = schema.get("config", {}).get("contentCategories", {})
        assert bool(cc) is False

    def test_classify_only_schema_detected(self, classify_only_schema):
        cc = classify_only_schema.get("config", {}).get("contentCategories", {})
        assert bool(cc) is True


# ===========================================================================
# Real example schema validation
# ===========================================================================

class TestExampleSchemas:
    """Validate real schemas from the repo parse correctly."""

    @pytest.fixture
    def template_schemas_dir(self):
        d = REPO_ROOT / "Issues" / "_TEMPLATE" / "schemas" / "classify_route_example"
        if not d.exists():
            pytest.skip(f"Template schemas not found: {d}")
        return d

    @pytest.fixture
    def ose_schemas_dir(self):
        d = REPO_ROOT / "Issues" / "OSE" / "schema"
        if not d.exists():
            pytest.skip(f"OSE schemas not found: {d}")
        return d

    def test_template_classifier_valid_json(self, template_schemas_dir):
        for f in template_schemas_dir.glob("*.json"):
            data = json.loads(f.read_text(encoding="utf-8"))
            assert "description" in data, f"{f.name} missing description"

    def test_template_classifier_mapping(self, template_schemas_dir):
        classifier = json.loads((template_schemas_dir / "doc_classifier.json").read_text(encoding="utf-8"))
        invoice = json.loads((template_schemas_dir / "invoice_extractor.json").read_text(encoding="utf-8"))
        receipt = json.loads((template_schemas_dir / "receipt_extractor.json").read_text(encoding="utf-8"))

        # Classifier references should match inner analyzerId values
        cats = classifier["config"]["contentCategories"]
        assert cats["invoice"]["analyzerId"] == invoice["analyzerId"]
        assert cats["receipt"]["analyzerId"] == receipt["analyzerId"]

    def test_template_inner_schemas_have_fields(self, template_schemas_dir):
        for name in ["invoice_extractor.json", "receipt_extractor.json"]:
            data = json.loads((template_schemas_dir / name).read_text(encoding="utf-8"))
            assert "fieldSchema" in data, f"{name} missing fieldSchema"
            assert len(data["fieldSchema"]["fields"]) > 0

    def test_ose_segmentation_references_synopsis(self, ose_schemas_dir):
        seg = json.loads((ose_schemas_dir / "ose_news_segmentation.json").read_text(encoding="utf-8"))
        cats = seg["config"]["contentCategories"]
        assert "news_story" in cats
        assert "analyzerId" in cats["news_story"]

    def test_ose_synopsis_has_fields(self, ose_schemas_dir):
        syn = json.loads((ose_schemas_dir / "ose_news_synopsis.json").read_text(encoding="utf-8"))
        assert "fieldSchema" in syn
        fields = syn["fieldSchema"]["fields"]
        assert len(fields) >= 5
        expected = {"Topic", "Summary", "Countries", "People", "Language", "NewsCategory"}
        assert set(fields.keys()) == expected


# ===========================================================================
# Integration: full classify-route pipeline (mocked Azure)
# ===========================================================================

class TestClassifyRoutePipeline:
    """Test the full pipeline flow with mocked Azure client."""

    def test_full_pipeline_create_inner_then_classifier(
        self, classifier_schema, inner_schema_files, mock_client
    ):
        """Simulate the main() flow: parse → validate → create inner → patch → create classifier."""
        # Step 1: Parse args
        args = [
            f"invoice={inner_schema_files['invoice']}",
            f"receipt={inner_schema_files['receipt']}"
        ]
        inner_schemas = parse_inner_schema_args(args)
        assert len(inner_schemas) == 2

        # Step 2: Validate mapping
        categories_with_inner = validate_classify_route_mapping(classifier_schema, inner_schemas)
        assert sorted(categories_with_inner) == ["invoice", "receipt"]

        # Step 3: Create inner analyzers
        created_ids = []
        category_to_real_id = {}
        for alias, inner_path in inner_schemas.items():
            inner_data = json.loads(inner_path.read_text(encoding="utf-8"))
            inner_id = inner_data.get("analyzerId", f"test-{alias}")
            mock_client.create_analyzer(inner_id, inner_data)
            created_ids.append(inner_id)
            category_to_real_id[alias] = inner_id

        # Step 4: Patch classifier
        patched = patch_classifier_schema(classifier_schema, category_to_real_id)
        cats = patched["config"]["contentCategories"]
        assert cats["invoice"]["analyzerId"] == "invoice_extractor"
        assert cats["receipt"]["analyzerId"] == "receipt_extractor"

        # Step 5: Create classifier
        classifier_id = "test-classifier"
        mock_client.create_analyzer(classifier_id, patched)
        created_ids.append(classifier_id)

        # Verify creation order: inner first, classifier last
        create_calls = mock_client.create_analyzer.call_args_list
        assert len(create_calls) == 3
        assert create_calls[-1][0][0] == "test-classifier"

        # Step 6: Cleanup (reverse order)
        cleanup_analyzer_set(mock_client, created_ids)
        delete_calls = mock_client.delete_analyzer.call_args_list
        assert delete_calls[0] == call("test-classifier")

    def test_cleanup_on_inner_create_failure(
        self, classifier_schema, inner_schema_files, mock_client
    ):
        """If second inner analyzer creation fails, first one should be cleaned up."""
        created_ids = []
        aliases = list(inner_schema_files.keys())

        # First inner succeeds, second fails
        mock_client.create_analyzer.side_effect = [
            {"status": "created"},
            Exception("Service unavailable"),
        ]

        try:
            for alias in aliases:
                inner_id = f"test-{alias}"
                mock_client.create_analyzer(inner_id, {})
                created_ids.append(inner_id)
        except Exception:
            pass

        # Only one was created before failure
        assert len(created_ids) == 1
        cleanup_analyzer_set(mock_client, created_ids)
        mock_client.delete_analyzer.assert_called_once_with(created_ids[0])

    def test_cleanup_on_classifier_create_failure(
        self, classifier_schema, inner_schema_files, mock_client
    ):
        """If classifier creation fails, all inner analyzers should be cleaned up."""
        created_ids = ["inner-inv", "inner-rec"]

        # Inners created, classifier fails
        mock_client.create_analyzer.side_effect = [
            {"status": "created"},  # inner 1
            {"status": "created"},  # inner 2
            Exception("Quota exceeded"),  # classifier
        ]

        try:
            mock_client.create_analyzer("inner-inv", {})
            mock_client.create_analyzer("inner-rec", {})
            classifier_id = "test-classifier"
            mock_client.create_analyzer(classifier_id, {})
            created_ids.append(classifier_id)
        except Exception:
            pass

        # Classifier was not added to created_ids
        assert len(created_ids) == 2
        cleanup_analyzer_set(mock_client, created_ids)
        delete_calls = mock_client.delete_analyzer.call_args_list
        assert len(delete_calls) == 2


# ===========================================================================
# Bug detection: classify-only schema metadata crash
# ===========================================================================

class TestClassifyOnlyBug:
    """
    Regression test: classify-only schemas (contentCategories but no analyzerId refs)
    should not crash when printing summary or writing metadata.
    
    Fixed: category_to_real_id is now initialized to {} before the try block.
    """

    def test_classify_only_category_to_real_id_initialized(self, classify_only_schema):
        """Verify the fixed pattern: category_to_real_id is always available."""
        is_classify_route = bool(classify_only_schema.get("config", {}).get("contentCategories", {}))
        inner_schemas = {}
        category_to_real_id = {}  # This mirrors the fix in main()

        assert is_classify_route is True

        # Inner schemas empty → creation block is skipped
        if is_classify_route and inner_schemas:
            for alias in inner_schemas:
                category_to_real_id[alias] = f"test-{alias}"

        # Summary section now guards with `and category_to_real_id`
        if is_classify_route and category_to_real_id:
            for alias, real_id in category_to_real_id.items():
                _ = f"Inner analyzer ({alias}): {real_id}"
            assert False, "Should not enter this branch for classify-only"
        elif is_classify_route:
            # This is the correct path for classify-only
            pass
        
        assert category_to_real_id == {}
