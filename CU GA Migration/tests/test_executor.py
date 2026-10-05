"""Offline pipeline integration, evidence preservation and output safety."""

from __future__ import annotations

import hashlib
import json
import re

import pytest

from cu_migrate.executor import execute
from cu_migrate.inventory import load_sources
from cu_migrate.models import RunMode, ValidationStatus
from cu_migrate.reports import write_reports


def test_export_preserves_source_and_evidence(export_file, definition, workspace):
    path = export_file({"value": [definition]})
    before = path.read_bytes()
    output = workspace / "review"
    run = execute(load_sources([path]), mode=RunMode.EXPORT, output_dir=output)
    assert run.failure_count == 0
    assert run.warning_count == 1
    assert path.read_bytes() == before
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    evidence = manifest["source_exports"][0]
    assert evidence["sha256"] == hashlib.sha256(before).hexdigest()
    assert (output / evidence["backup"]).read_bytes() == before
    entry = manifest["analyzers"][0]
    assert json.loads((output / entry["source_backup"]).read_text(encoding="utf-8")) == definition
    payload = json.loads((output / entry["payload"]).read_text(encoding="utf-8"))
    assert payload["fieldSchema"] == definition["fieldSchema"]
    assert payload["config"] == definition["config"]
    assert "scenario" not in payload
    assert "analyzerId" not in payload
    assert manifest["deployed"] is False
    assert entry["deployed"] is False
    assert entry["create_command"] == (
        "cu analyzer create --name invoice_preview_ga_v1 "
        "--schema '.\\proposed\\invoice_preview_ga_v1.json' --api-version 2025-11-01"
    )
    report = (output / "migration_report.md").read_text(encoding="utf-8")
    assert "OFFLINE PROPOSALS ONLY" in report
    assert evidence["sha256"] in report
    assert json.loads((output / "migration_run.json").read_text(encoding="utf-8"))["results"][0]["source"]["raw_definition"] == definition


def test_single_selected_and_all_scopes(export_file, definition):
    sources = load_sources([export_file([definition, {**definition, "analyzerId": "second"}])])
    assert execute(sources).scope == "all"
    assert execute(sources, ["second"]).scope == "single"
    selected = execute(sources, ["second", "invoice_preview"])
    assert selected.scope == "selected"
    assert selected.selected_analyzers == ["second", "invoice_preview"]


@pytest.mark.parametrize("ids", [["missing"], ["invoice_preview", "missing"], [], ["invoice_preview", "invoice_preview"]])
def test_invalid_selection_writes_nothing(export_file, definition, workspace, ids):
    output = workspace / "out"
    with pytest.raises(ValueError):
        execute(load_sources([export_file(definition)]), ids, RunMode.EXPORT, output)
    assert not output.exists()


def test_dry_run_writes_nothing(export_file, definition, workspace):
    source = export_file(definition)
    before = list(workspace.iterdir())
    execute(load_sources([source]))
    assert list(workspace.iterdir()) == before
    with pytest.raises(ValueError, match="only valid"):
        execute(load_sources([source]), output_dir=workspace / "out")


def test_export_requires_new_directory(export_file, definition, workspace):
    sources = load_sources([export_file(definition)])
    with pytest.raises(ValueError, match="required"):
        execute(sources, mode=RunMode.EXPORT)
    with pytest.raises(ValueError, match="already exists"):
        execute(sources, mode=RunMode.EXPORT, output_dir=workspace)
    output = workspace / "out"
    run = execute(sources, mode=RunMode.EXPORT, output_dir=output)
    before = (output / "manifest.json").read_bytes()
    with pytest.raises(ValueError, match="already exists"):
        execute(sources, mode=RunMode.EXPORT, output_dir=output)
    with pytest.raises(FileExistsError, match="overwrite"):
        write_reports(run, output)
    assert (output / "manifest.json").read_bytes() == before


def test_source_change_after_loading_is_rejected(export_file, definition, workspace):
    path = export_file(definition)
    sources = load_sources([path])
    path.write_text("{}", encoding="utf-8")
    output = workspace / "out"
    with pytest.raises(ValueError, match="changed after loading"):
        execute(sources, mode=RunMode.EXPORT, output_dir=output)
    assert not output.exists()


@pytest.mark.parametrize("change", [
    {"proMode": True}, {"analysisMode": "pro"}, {"faceAnalysis": True},
    {"personDirectory": True}, {"scenario": "unknown"},
    {"trainingData": {}},
    {"trainingData": {"unsupportedReference": True}},
    {"trainingData": [{"azureBlobSource": "invalid"}]},
    {"models": {}}, {"models": {"completion": 123}},
    {"fieldSchema": {"fields": {"Total": {"type": "unknown"}}}},
    {"trainingData": {"blobContainerUrl": "https://example.invalid/training", "fieldMappings": 123}},
])
def test_blocking_findings_survive_transformation(export_file, definition, workspace, change):
    run = execute(
        load_sources([export_file({**definition, **change})]),
        mode=RunMode.EXPORT, output_dir=workspace / "out",
    )
    assert run.failure_count == 1
    result = run.results[0]
    assert result.validation_status == ValidationStatus.FAIL
    if result.proposed:
        assert result.proposed.validation_status == ValidationStatus.FAIL
    manifest = json.loads((workspace / "out" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["analyzers"][0]["create_command"] is None
    assert not list((workspace / "out" / "proposed").iterdir())


def test_metadata_only_cannot_be_migrated(export_file):
    run = execute(load_sources([export_file({"analyzerId": "summary"})]))
    assert run.failure_count == 1
    assert run.results[0].proposed is None
    assert "cu analyzer show NAME' (JSON stdout)" in run.results[0].findings[0].message
    assert "--json" not in run.results[0].findings[0].message


def test_training_array_and_existing_knowledge_preserved(export_file, definition):
    existing = {"kind": "azureBlob", "azureBlobSource": {"containerUrl": "https://example.invalid/existing"}}
    definition["knowledgeSources"] = [existing]
    definition["trainingData"] = [
        {"blobContainerUrl": "https://example.invalid/training", "prefix": "labels/",
         "fieldMappings": [{"fieldId": "Total", "label": "Total"}]},
    ]
    path = export_file(definition)
    before = path.read_bytes()
    result = execute(load_sources([path])).results[0]
    assert result.validation_status == ValidationStatus.WARN
    assert result.proposed.knowledge_sources[0] == existing
    converted = result.proposed.knowledge_sources[1]
    assert converted["azureBlobSource"]["prefix"] == "labels/"
    assert converted["fieldMappings"] == definition["trainingData"][0]["fieldMappings"]
    assert path.read_bytes() == before


def test_existing_knowledge_and_models_are_not_dropped(export_file, definition):
    definition["knowledgeSources"] = [
        {"kind": "azureBlob", "azureBlobSource": {"containerUrl": "https://example.invalid/existing"}},
    ]
    definition["models"] = {"completion": "chosen-model", "embedding": "chosen-embedding"}
    result = execute(load_sources([export_file(definition)])).results[0]
    assert result.proposed.knowledge_sources == definition["knowledgeSources"]
    assert result.proposed.models == definition["models"]


@pytest.mark.parametrize("identifier", ["legacy-name", "already_ga_v1", "../unsafe", "a" * 100])
def test_generated_id_valid_and_versioned(export_file, definition, identifier):
    definition["analyzerId"] = identifier
    result = execute(load_sources([export_file(definition)])).results[0]
    target = result.proposed.analyzer_id
    assert re.fullmatch(r"[A-Za-z0-9_]{1,64}", target)
    assert target.endswith("_ga_v1")
    assert target != identifier


def test_colliding_generated_ids_are_blocked(export_file, definition, workspace):
    sources = load_sources([export_file([{**definition, "analyzerId": "a-b"}, {**definition, "analyzerId": "a_b"}])])
    run = execute(sources, mode=RunMode.EXPORT, output_dir=workspace / "out")
    assert run.failure_count == 2
    assert len(list((workspace / "out" / "blocked").iterdir())) == 2
    assert "cu analyzer create" not in (workspace / "out" / "official_cu_commands.md").read_text(encoding="utf-8")


def test_target_cannot_reuse_unselected_source_id(export_file, definition):
    sources = load_sources([export_file([definition, {**definition, "analyzerId": "invoice_preview_ga_v1"}])])
    assert execute(sources, ["invoice_preview"]).failure_count == 1


def test_mixed_batch_preserves_good_proposals_and_failed_evidence(export_file, definition, workspace):
    sources = load_sources([export_file([definition, {**definition, "analyzerId": "blocked_source", "proMode": True}])])
    run = execute(sources, mode=RunMode.EXPORT, output_dir=workspace / "out")
    assert (run.warning_count, run.failure_count) == (1, 1)
    commands = (workspace / "out" / "official_cu_commands.md").read_text(encoding="utf-8")
    assert "--name invoice_preview_ga_v1" in commands
    assert "--name blocked_source_ga_v1" not in commands
    assert len(list((workspace / "out" / "backups").iterdir())) == 2
