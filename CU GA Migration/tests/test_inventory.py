"""Explicit local input formats, normalization and fail-closed inventory."""

from __future__ import annotations

import hashlib
import json

import pytest

from cu_migrate.inventory import build_inventory, load_sources
from cu_migrate.models import MigrationReadiness


@pytest.mark.parametrize("wrapper", ["single", "array", "value", "analyzers", "items", "properties"])
def test_accepts_export_shapes(export_file, definition, wrapper):
    if wrapper == "single":
        data = definition
    elif wrapper == "array":
        data = [definition]
    elif wrapper == "properties":
        body = {k: v for k, v in definition.items() if k != "analyzerId"}
        data = {"analyzerId": definition["analyzerId"], "properties": body}
    else:
        data = {wrapper: [definition]}
    path = export_file(data)
    sources = load_sources([path])
    assert len(sources) == 1
    source = sources[0]
    assert source.analyzer_id == "invoice_preview"
    assert source.field_schema == definition["fieldSchema"]
    expected_record = data if wrapper in ("single", "properties") else definition
    assert source.raw_definition == expected_record
    assert source.source_sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
    assert build_inventory(sources)[0].migration_readiness == MigrationReadiness.READY


@pytest.mark.parametrize("alias", ["id", "name"])
def test_official_identity_alias(export_file, definition, alias):
    definition[alias] = definition.pop("analyzerId")
    assert load_sources([export_file(definition)])[0].analyzer_id == "invoice_preview"


def test_explicit_identity_for_idless_definition(export_file, definition):
    definition.pop("analyzerId")
    path = export_file(definition)
    with pytest.raises(ValueError, match="ID is missing"):
        load_sources([path])
    source = load_sources([path], source_id="explicit_source")[0]
    assert source.analyzer_id == "explicit_source"
    assert "analyzerId" not in source.raw_definition


@pytest.mark.parametrize("data", [
    {}, [], None, 42, "wrong", {"value": []}, {"value": {}}, [None],
    {"error": {"message": "service export failed"}},
    {"analyzerId": None}, {"analyzerId": ""},
    {"analyzerId": "x", "id": "y"},
    {"analyzerId": " x "},
    {"analyzerId": "x", "properties": []},
    {"analyzerId": "x", "config": []},
    {"analyzerId": "x", "models": None},
    {"analyzerId": "x", "fieldSchema": []},
    {"analyzerId": "x", "trainingData": "wrong"},
    {"analyzerId": "x", "trainingData": [None]},
    {"analyzerId": "x", "knowledgeSources": {}},
    {"analyzerId": "x", "knowledgeSources": [None]},
    {"analyzerId": "x", "scenario": 123},
    {"analyzerId": "x", "config": {"analysisMode": []}},
    {"value": [{"analyzerId": "x"}], "nextLink": "https://example.invalid/next"},
    {"value": [{"analyzerId": "x"}], "items": [{"analyzerId": "x"}]},
])
def test_malformed_exports_fail(export_file, data):
    with pytest.raises(ValueError):
        load_sources([export_file(data)])


@pytest.mark.parametrize("content", ["{", '{"analyzerId":"x","analyzerId":"y"}', '{"analyzerId":"x","value":NaN}'])
def test_strict_json_decoding(workspace, content):
    path = workspace / "broken.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError):
        load_sources([path])


def test_directory_and_multiple_files(export_file, definition, workspace):
    first = export_file(definition, "exports/first.json")
    second = export_file({**definition, "analyzerId": "second"}, "exports/second.json")
    assert len(load_sources([workspace / "exports"])) == 2
    assert len(load_sources([first, second])) == 2
    with pytest.raises(ValueError, match="Duplicate"):
        load_sources([first, first])


def test_empty_or_missing_inputs_fail(workspace):
    for paths in ([], [workspace], [workspace / "missing.json"]):
        with pytest.raises(ValueError):
            load_sources(paths)


def test_source_id_is_not_for_lists_or_directories(export_file, definition, workspace):
    path = export_file([definition])
    with pytest.raises(ValueError, match="standalone"):
        load_sources([path], "invoice_preview")
    with pytest.raises(ValueError, match="exactly one"):
        load_sources([workspace], "invoice_preview")


def test_source_id_cannot_override_existing_identity(export_file, definition):
    with pytest.raises(ValueError, match="Conflicting"):
        load_sources([export_file(definition)], "different")


@pytest.mark.parametrize("encoding", ["utf-8-sig", "utf-16"])
def test_powershell_json_encoding(workspace, definition, encoding):
    path = workspace / "export.json"
    path.write_text(json.dumps(definition), encoding=encoding)
    assert load_sources([path])[0].analyzer_id == definition["analyzerId"]


def test_metadata_only_inventory_needs_definition(export_file):
    item = build_inventory(load_sources([export_file([{"analyzerId": "summary", "status": "ready"}])]))[0]
    assert item.definition_available is False
    assert item.migration_readiness == MigrationReadiness.REVIEW_NEEDED


def test_nested_removed_feature_is_blocked(export_file, definition):
    definition["config"]["proMode"] = True
    item = build_inventory(load_sources([export_file(definition)]))[0]
    assert item.migration_readiness == MigrationReadiness.BLOCKED


def test_prebuilt_inventory_is_opt_in(export_file):
    sources = load_sources([export_file({"analyzerId": "prebuilt-layout", "baseAnalyzerId": "prebuilt-layout"})])
    with pytest.raises(ValueError, match="No custom"):
        build_inventory(sources)
    assert len(build_inventory(sources, include_prebuilt=True)) == 1
