"""Click command contract and meaningful exit codes without service access."""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from cu_migrate.cli import main


def test_help_needs_no_configuration():
    result = CliRunner().invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "OFFLINE" in result.output
    assert "--endpoint" not in result.output


@pytest.mark.parametrize("arguments", [
    ["--endpoint", "https://example.invalid", "inventory"],
    ["--key", "not-a-real-key", "inventory"],
    ["inventory"],
    ["migrate"],
    ["report"],
])
def test_old_remote_options_and_missing_inputs_rejected(arguments):
    result = CliRunner().invoke(main, arguments)
    assert result.exit_code == 2
    assert "Error:" in result.output


@pytest.mark.parametrize("arguments", [
    ["--mode", "apply"], ["--yes"], ["--endpoint", "https://example.invalid"], ["--key", "not-a-real-key"],
])
def test_obsolete_migration_options_rejected(export_file, definition, arguments):
    result = CliRunner().invoke(main, ["migrate", "--input", str(export_file(definition)), *arguments])
    assert result.exit_code == 2


def test_inventory_json_is_machine_readable(export_file, definition, monkeypatch):
    monkeypatch.setenv("CU_ENDPOINT", "invalid ignored environment value")
    monkeypatch.setenv("CU_KEY", "not-a-real-key")
    result = CliRunner().invoke(main, ["inventory", "--input", str(export_file(definition)), "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)[0]["analyzer_id"] == definition["analyzerId"]


def test_migration_default_is_no_write(export_file, definition, workspace):
    path = export_file(definition)
    result = CliRunner().invoke(main, ["migrate", "--input", str(path)])
    assert result.exit_code == 0, result.output
    assert "no files written" in result.output
    assert list(workspace.iterdir()) == [path]


@pytest.mark.parametrize("command", ["migrate", "report"])
def test_export_commands_write_complete_bundle(export_file, definition, workspace, command):
    args = [command, "--input", str(export_file(definition)), "--output", str(workspace / "out")]
    if command == "migrate":
        args += ["--mode", "export"]
    result = CliRunner().invoke(main, args)
    assert result.exit_code == 0, result.output
    assert "Nothing was deployed" in result.output
    assert (workspace / "out" / "manifest.json").is_file()
    assert (workspace / "out" / "official_cu_commands.md").is_file()


@pytest.mark.parametrize("extra", [
    ["-a", "unknown"], ["--mode", "export"], ["--output", "unused-output"],
])
def test_invalid_plan_invocations_fail(export_file, definition, extra):
    result = CliRunner().invoke(main, ["migrate", "--input", str(export_file(definition)), *extra])
    assert result.exit_code == 1
    assert "Error:" in result.output


def test_malformed_export_returns_click_error(workspace):
    path = workspace / "broken.json"
    path.write_text("{", encoding="utf-8")
    result = CliRunner().invoke(main, ["migrate", "--input", str(path)])
    assert result.exit_code == 1
    assert "Cannot load" in result.output
    assert "Traceback" not in result.output


def test_validation_failure_returns_nonzero_and_keeps_report(export_file, definition, workspace):
    definition["proMode"] = True
    result = CliRunner().invoke(main, [
        "migrate", "--input", str(export_file(definition)), "--mode", "export",
        "--output", str(workspace / "out"),
    ])
    assert result.exit_code == 1
    assert "failed migration checks" in result.output
    assert (workspace / "out" / "migration_report.md").is_file()
    assert (workspace / "out" / "manifest.json").is_file()


def test_output_collision_never_overwrites_source(export_file, definition):
    path = export_file(definition)
    before = path.read_bytes()
    result = CliRunner().invoke(main, [
        "report", "--input", str(path), "--output", str(path),
    ])
    assert result.exit_code == 1
    assert "already exists" in result.output
    assert path.read_bytes() == before


def test_output_io_failure_is_click_error(export_file, definition, workspace, monkeypatch):
    from cu_migrate import executor

    def denied(*args, **kwargs):
        raise PermissionError("synthetic write denied")

    monkeypatch.setattr(executor, "_write_artifacts", denied)
    result = CliRunner().invoke(main, [
        "report", "--input", str(export_file(definition)), "--output", str(workspace / "out"),
    ])
    assert result.exit_code == 1
    assert "synthetic write denied" in result.output
