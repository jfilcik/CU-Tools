"""Offline native CLI regression tests; generated files stay in this example."""

from __future__ import annotations

import ast
import copy
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from uuid import uuid4

import pytest

PROJECT = Path(__file__).resolve().parents[2]
REPO = PROJECT.parents[1]
spec = importlib.util.spec_from_file_location("golden_native_evaluate", PROJECT / "evaluation" / "evaluate.py")
assert spec and spec.loader
evaluate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluate)
QUOTE = "Supplier shall deliver the goods."


@pytest.fixture
def workspace():
    parent = PROJECT / "evaluation" / "tests" / ".test-workspaces"
    root = parent / uuid4().hex
    root.mkdir(parents=True)
    try:
        yield root
    finally:
        shutil.rmtree(root)
        if parent.exists() and not any(parent.iterdir()):
            parent.rmdir()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def gold_record(doc_id="sample", source_file=None):
    record = {
        "doc_id": doc_id,
        "parties": [],
        "obligations": [{
            "obligation_id": "O001", "obligor_party_id": "P1",
            "obligee_party_ids": [], "obligation_type": "Delivery",
            "nature": "Affirmative", "action": QUOTE, "business_summary": QUOTE,
            "exact_quotes": [QUOTE], "required_fields": [], "is_post_termination": False,
        }],
    }
    if source_file:
        record["source_file"] = source_file
    return record


def native_payload():
    return {
        "analyzerId": "golden_test_v2", "apiVersion": "2026-06-01-preview",
        "contents": [{"fields": {
            "Parties": {"type": "array", "valueArray": []},
            "Obligations": {"type": "array", "valueArray": [{
                "type": "object", "valueObject": {
                    "ObligationType": {"type": "string", "valueString": "Delivery"},
                    "IsPostTermination": {"type": "boolean", "valueBoolean": False},
                    "Evidence": {"type": "array", "valueArray": [{
                        "type": "object", "valueObject": {
                            "ExactQuote": {"type": "string", "valueString": QUOTE},
                        },
                    }]},
                },
            }]},
        }}],
    }


def inputs(workspace, gold):
    samples, results = workspace / "samples", workspace / "results"
    samples.mkdir()
    results.mkdir()
    for row in gold:
        path = samples / row.get("source_file", row["doc_id"] + ".txt")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(QUOTE, encoding="utf-8")
    return samples, results


def report(results, rows, path=None):
    counts = {status: sum(row["status"] == status for row in rows) for status in ("succeeded", "failed", "skipped")}
    return write_json(path or results / "report.json", {
        "schema": "cu-cli/analyze-report/v1", "analyzer": "golden_test_v2",
        "result_view": "full", "counts": {**counts, "total": len(rows)}, "results": rows,
    })


def score(gold, samples, results, report_path=None):
    return evaluate.evaluate_mode("Agentic", gold, samples, results, report_path)


@pytest.mark.parametrize("envelope", [False, True], ids=["root-contents", "lro-envelope"])
def test_native_contents_and_unknown_measurements(workspace, envelope):
    gold = [gold_record()]
    samples, results = inputs(workspace, gold)
    payload = native_payload()
    if envelope:
        payload = {
            "id": "offline-operation-id",
            "status": "Succeeded",
            "result": payload,
            "usage": {"documentPagesStandard": 1},
        }
    result_path = write_json(results / "sample.txt.result.json", payload)
    original = result_path.read_bytes()
    metrics = score(gold, samples, results)
    assert metrics["completed_count"] == metrics["matched_obligations"] == 1
    assert metrics["documents"][0]["source_file"] == "sample.txt"
    assert metrics["documents"][0]["result_file"] == "sample.txt.result.json"
    assert metrics["documents"][0]["service_status"] == ("Succeeded" if envelope else None)
    assert metrics["api_version"] == "2026-06-01-preview"
    for key in ("total_input_tokens", "total_output_tokens", "total_tokens", "observed_input_tokens"):
        assert metrics[key] is None
    assert all(value is None for value in metrics["latency_seconds"].values())
    assert metrics["measurement_coverage"]["elapsed_seconds"] == 0
    assert metrics["documents"][0]["post_termination_present"] == 1
    assert result_path.read_bytes() == original


def test_nested_sources_and_same_stem_different_extensions(workspace):
    gold = [
        gold_record("north", "north/sample.txt"),
        gold_record("south", "south/sample.txt"),
        gold_record("pdf", "north/sample.pdf"),
    ]
    samples, results = inputs(workspace, gold)
    for row in gold:
        write_json(results / (row["source_file"] + ".result.json"), native_payload())
    metrics = score(gold, samples, results)
    assert metrics["completed_count"] == metrics["matched_obligations"] == 3
    assert {row["source_file"] for row in metrics["documents"]} == {row["source_file"] for row in gold}


def test_missing_failed_skipped_and_missing_output_keep_gold_denominator(workspace):
    gold = [gold_record(name) for name in ("good", "failed", "skipped", "missing_output", "missing")]
    samples, results = inputs(workspace, gold)
    for name in ("good", "failed", "skipped"):
        write_json(results / f"{name}.txt.result.json", native_payload())
    report(results, [
        {"input": str(samples / "good.txt"), "status": "succeeded", "output": str(results / "good.txt.result.json")},
        {"input": str(samples / "failed.txt"), "status": "failed", "error": "request failed"},
        {"input": str(samples / "skipped.txt"), "status": "skipped", "output": str(results / "skipped.txt.result.json"), "reason": "result file already exists"},
        {"input": str(samples / "missing_output.txt"), "status": "succeeded", "output": str(results / "missing_output.txt.result.json")},
    ])
    metrics = score(gold, samples, results)
    assert metrics["document_count"] == metrics["gold_obligations"] == 5
    assert metrics["completed_count"] == metrics["matched_obligations"] == 1
    assert metrics["recall"] == metrics["completion_rate"] == 0.2
    assert sum(doc["false_negative_count"] for doc in metrics["documents"]) == 4
    assert metrics["total_tokens"] is None
    assert all(doc["predicted_count"] == 0 for doc in metrics["documents"][1:])
    assert metrics["documents"][1]["error"] == "request failed"


def test_empty_run_and_report_only_failures(workspace):
    gold = [gold_record()]
    samples, results = inputs(workspace, gold)
    empty = score(gold, samples, results)
    report(results, [{"input": "sample.txt", "status": "failed", "error": "offline fixture"}])
    failed = score(gold, samples, results)
    for metrics in (empty, failed):
        assert metrics["gold_obligations"] == metrics["document_count"] == 1
        assert metrics["completed_count"] == metrics["matched_obligations"] == 0
        assert metrics["total_tokens"] is None
        assert metrics["latency_seconds"]["total"] is None


def test_legacy_manifest_envelope_and_explicit_zero_preserved(workspace):
    gold = [gold_record()]
    samples, results = inputs(workspace, gold)
    write_json(results / "sample.json", {
        "_metadata": {"document": "sample.txt"}, "status": "Succeeded",
        "result": native_payload(),
        "usage": {"tokens": {"model-input": 20, "model-output": 7}},
    })
    write_json(results / "metadata.json", {
        "run_id": "saved_legacy_run", "results": [{
            "document": "sample.txt", "status": "success", "result_file": "sample.json",
            "elapsed_seconds": 0, "input_tokens": 20, "output_tokens": 7,
        }],
    })
    metrics = score(gold, samples, results)
    assert metrics["result_format"] == "legacy"
    assert metrics["run_id"] == "saved_legacy_run"
    assert metrics["total_tokens"] == 27
    assert metrics["latency_seconds"]["mean"] == 0
    assert metrics["matched_obligations"] == 1


def test_legacy_envelope_without_manifest_uses_document_metadata(workspace):
    gold = [gold_record("nested/sample")]
    samples, results = inputs(workspace, gold)
    write_json(results / "legacy.json", {
        "_metadata": {"document": "nested\\sample.txt"}, "status": "Succeeded",
        "result": native_payload(),
    })
    assert score(gold, samples, results)["matched_obligations"] == 1


@pytest.mark.parametrize("status", ["Failed", "Canceled", "Running", "NotStarted"])
def test_unsuccessful_result_payload_never_contributes_predictions(workspace, status):
    gold = [gold_record()]
    samples, results = inputs(workspace, gold)
    write_json(results / "sample.txt.result.json", {"status": status, "result": native_payload()})
    assert score(gold, samples, results)["predicted_obligations"] == 0


def test_partial_structured_measurements_are_not_whole_run_totals(workspace):
    gold = [gold_record("first"), gold_record("second")]
    samples, results = inputs(workspace, gold)
    payload = native_payload()
    payload["usage"] = {"tokens": {"model-input": 0, "other-input": 10, "model-output": 3}}
    payload["_metadata"] = {"elapsed_seconds": 2}
    write_json(results / "first.txt.result.json", payload)
    write_json(results / "second.txt.result.json", native_payload())
    metrics = score(gold, samples, results)
    assert metrics["total_tokens"] is None
    assert metrics["total_input_tokens"] is None
    assert metrics["observed_input_tokens"] == 10
    assert metrics["observed_output_tokens"] == 3
    assert metrics["measurement_coverage"]["input_tokens"] == 1
    assert all(value is None for value in metrics["latency_seconds"].values())


def test_explicit_zero_usage_is_known_not_unknown(workspace):
    gold = [gold_record()]
    samples, results = inputs(workspace, gold)
    payload = native_payload()
    payload["usage"] = {"tokens": {"model-input": 0, "model-output": 0}}
    write_json(results / "sample.txt.result.json", payload)
    assert score(gold, samples, results)["total_tokens"] == 0


@pytest.mark.parametrize("bad", [-1, True, "12", float("nan"), float("inf"), 1.5])
def test_invalid_measurements_fail_closed(workspace, bad):
    gold = [gold_record()]
    samples, results = inputs(workspace, gold)
    payload = native_payload()
    payload["usage"] = {"tokens": {"model-input": bad}}
    write_json(results / "sample.txt.result.json", payload)
    with pytest.raises(ValueError, match="numeric measurement"):
        score(gold, samples, results)


@pytest.mark.parametrize("payload", [
    [], {"unrecognized": "data"}, {"contents": "not an array"},
    {"contents": [{"fields": []}]},
    {"contents": []},
    {"contents": [{"fields": {"InvoiceTotal": {"valueNumber": 1}}}]},
    {"contents": [{"fields": {"Obligations": {"valueArray": ["invalid"]}}}]},
    {"contents": [{"fields": {"Obligations": {"valueString": "invalid"}}}]},
    {"contents": [{"fields": {}}, {"fields": {}}]},
    {"status": "surprise", "result": {}},
])
def test_unrecognized_or_malformed_results_fail_closed(workspace, payload):
    gold = [gold_record()]
    samples, results = inputs(workspace, gold)
    write_json(results / "sample.txt.result.json", payload)
    with pytest.raises(ValueError):
        score(gold, samples, results)


def test_invalid_json_result_fails_closed(workspace):
    gold = [gold_record()]
    samples, results = inputs(workspace, gold)
    (results / "sample.txt.result.json").write_text("{bad", encoding="utf-8")
    with pytest.raises(ValueError):
        score(gold, samples, results)


@pytest.mark.parametrize("file_name", ["unrelated.txt.result.json", "other/sample.txt.result.json", "sample.pdf.result.json"])
def test_unrelated_sources_never_match_by_stem(workspace, file_name):
    gold = [gold_record()]
    samples, results = inputs(workspace, gold)
    write_json(results / file_name, native_payload())
    with pytest.raises(ValueError):
        score(gold, samples, results)


def test_duplicate_native_and_legacy_identity_fails_closed(workspace):
    gold = [gold_record()]
    samples, results = inputs(workspace, gold)
    write_json(results / "sample.txt.result.json", native_payload())
    write_json(results / "saved.json", {"_metadata": {"document": "sample.txt"}, "result": native_payload()})
    with pytest.raises(ValueError, match="Duplicate result"):
        score(gold, samples, results)


@pytest.mark.parametrize("identity", ["../sample.txt", "/outside/sample.txt", "elsewhere/sample.txt", "https://example.invalid/sample.txt"])
def test_bad_source_metadata_is_not_silently_accepted(workspace, identity):
    gold = [gold_record()]
    samples, results = inputs(workspace, gold)
    payload = native_payload()
    payload["_metadata"] = {"source_file": identity}
    write_json(results / "sample.txt.result.json", payload)
    with pytest.raises(ValueError):
        score(gold, samples, results)


@pytest.mark.parametrize("change", ["duplicate", "unrelated", "bad_status", "wrong_output", "outside_output", "unlisted_result"])
def test_invalid_native_manifest_fails_closed(workspace, change):
    gold = [gold_record()]
    samples, results = inputs(workspace, gold)
    write_json(results / "sample.txt.result.json", native_payload())
    rows = [{"input": "sample.txt", "status": "succeeded", "output": "sample.txt.result.json"}]
    if change == "duplicate":
        rows.append(copy.deepcopy(rows[0]))
    elif change == "unrelated":
        rows[0]["input"] = "other.txt"
    elif change == "bad_status":
        rows[0]["status"] = "completed"
    elif change == "wrong_output":
        rows[0]["output"] = "wrong.txt.result.json"
    elif change == "outside_output":
        rows[0]["output"] = str(workspace / "outside.json")
    else:
        rows = []
    report(results, rows)
    with pytest.raises(ValueError):
        score(gold, samples, results)


def test_explicit_report_and_relative_windows_paths(workspace):
    gold = [gold_record("nested/sample")]
    samples, results = inputs(workspace, gold)
    write_json(results / "nested" / "sample.txt.result.json", native_payload())
    report_path = report(results, [{
        "input": "nested\\sample.txt", "status": "succeeded",
        "output": "nested\\sample.txt.result.json",
    }], workspace / "custom.report.json")
    assert score(gold, samples, results, report_path)["completion_rate"] == 1


def test_report_paths_relative_to_working_directory(workspace, monkeypatch):
    gold = [gold_record("nested/sample")]
    samples, results = inputs(workspace, gold)
    write_json(results / "nested" / "sample.txt.result.json", native_payload())
    monkeypatch.chdir(workspace)
    report(results, [{
        "input": "samples/nested/sample.txt", "status": "succeeded",
        "output": "results/nested/sample.txt.result.json",
    }])
    assert score(gold, samples, results)["matched_obligations"] == 1


@pytest.mark.parametrize("change", ["counts", "result_view"])
def test_invalid_report_totals_and_non_json_output_are_rejected(workspace, change):
    gold = [gold_record()]
    samples, results = inputs(workspace, gold)
    path = report(results, [])
    payload = json.loads(path.read_text(encoding="utf-8"))
    if change == "counts":
        payload["counts"]["total"] = 10
    else:
        payload["result_view"] = "llm-input"
    write_json(path, payload)
    with pytest.raises(ValueError):
        score(gold, samples, results)


def test_report_schema_and_mixed_formats_fail_closed(workspace):
    gold = [gold_record()]
    samples, results = inputs(workspace, gold)
    write_json(results / "report.json", {"schema": "unknown", "results": []})
    with pytest.raises(ValueError, match="schema"):
        score(gold, samples, results)
    report(results, [])
    write_json(results / "metadata.json", {"results": []})
    with pytest.raises(ValueError, match="mix"):
        score(gold, samples, results)


def test_non_result_sidecars_are_excluded(workspace):
    gold = [gold_record()]
    samples, results = inputs(workspace, gold)
    write_json(results / "schema.json", {"fieldSchema": {"fields": {}}})
    write_json(results / "run.manifest.json", {"documents": []})
    write_json(results / "custom.report.json", {"schema": "cu-cli/analyze-report/v1", "results": []})
    write_json(results / "sample.txt.result.json", native_payload())
    assert score(gold, samples, results)["completed_count"] == 1


def test_expected_document_ids_and_sources_must_be_unique():
    for gold in (
        [gold_record(), gold_record()],
        [gold_record("one", "SAMPLE.txt"), gold_record("two", "sample.txt")],
    ):
        with pytest.raises(ValueError, match="Duplicate"):
            evaluate.expected_sources(gold)


@pytest.mark.parametrize("change", ["analyzerId", "apiVersion"])
def test_mixed_analyzers_or_api_versions_are_rejected(workspace, change):
    gold = [gold_record("one"), gold_record("two")]
    samples, results = inputs(workspace, gold)
    write_json(results / "one.txt.result.json", native_payload())
    payload = native_payload()
    payload[change] = "other"
    write_json(results / "two.txt.result.json", payload)
    with pytest.raises(ValueError, match="Mixed"):
        score(gold, samples, results)


def test_saved_legacy_metrics_are_reproduced_without_writing_them():
    gold = evaluate.load_gold(evaluate.DEFAULT_GOLD)
    for mode in ("standard", "agentic"):
        result_dir = PROJECT / "test_results" / mode
        saved_metrics = PROJECT / "evaluation" / "output" / f"{mode}_metrics.json"
        if not (result_dir / "metadata.json").is_file() or not saved_metrics.is_file():
            pytest.skip("Historical raw outputs/metrics are intentionally not versioned")
        before = saved_metrics.read_bytes()
        expected = json.loads(before)
        actual = evaluate.evaluate_mode(mode.title(), gold, evaluate.DEFAULT_SAMPLES, result_dir)
        for key, value in expected.items():
            if isinstance(value, (int, float)):
                assert actual[key] == pytest.approx(value), key
        assert actual["latency_seconds"] == pytest.approx(expected["latency_seconds"])
        for left, right in zip(actual["documents"], expected["documents"], strict=True):
            for key, value in right.items():
                assert left[key] == value, (mode, left["doc_id"], key)
        assert saved_metrics.read_bytes() == before


def test_new_report_retains_unknowns_without_reusing_historical_verdict(workspace, monkeypatch):
    gold = [gold_record()]
    samples, results = inputs(workspace, gold)
    write_json(results / "sample.txt.result.json", native_payload())
    gold_path = workspace / "gold.jsonl"
    gold_path.write_text(json.dumps(gold[0]) + "\n", encoding="utf-8")
    output = workspace / "new_evaluation"
    args = [
        "evaluate.py", "--gold", str(gold_path), "--samples", str(samples),
        "--standard-results", str(results), "--agentic-results", str(results),
        "--output", str(output),
    ]
    historical_path = PROJECT / "REPORT.md"
    historical = historical_path.read_bytes()
    monkeypatch.setattr(sys, "argv", args)
    evaluate.main()
    text = (output / "REPORT.md").read_text(encoding="utf-8")
    assert "unknown" in text
    assert "Southeast Asia" not in text
    assert "## Independent qualitative review" not in text
    assert json.loads((output / "standard_metrics.json").read_text())["total_tokens"] is None
    assert historical_path.read_bytes() == historical
    with pytest.raises(FileExistsError, match="overwrite"):
        evaluate.main()


def notebook_cells():
    notebook = json.loads((PROJECT / "notebooks" / "standard_vs_agentic.ipynb").read_text(encoding="utf-8"))
    return {cell["id"]: cell for cell in notebook["cells"]}


def test_notebook_code_syntax_and_no_stale_execution_outputs():
    for name, cell in notebook_cells().items():
        if cell["cell_type"] != "code":
            continue
        source = "".join(cell["source"])
        compile(source, f"notebook:{name}", "exec")
        ast.parse(source)
        assert cell["execution_count"] is None
        assert cell["outputs"] == []
        assert "cu-analyzer-run" not in source
        assert "cu_cli" not in source


def test_dataset_preparation_can_keep_cli_source_input_only(workspace):
    spec = importlib.util.spec_from_file_location("golden_cli_prepare", PROJECT / "scripts" / "prepare_dataset.py")
    assert spec and spec.loader
    prepare = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prepare)
    output = workspace / "cli_inputs"
    manifest = workspace / "cli_inputs.manifest.json"
    materialized = prepare.prepare_dataset(
        prepare.DEFAULT_SOURCE, output_dir=output, manifest_output=manifest,
    )
    assert len(materialized["documents"]) == 10
    assert len(list(output.iterdir())) == 10
    assert all(path.suffix == ".txt" for path in output.iterdir())
    assert json.loads(manifest.read_text(encoding="utf-8")) == materialized


def notebook_namespace(monkeypatch, workspace):
    calls = []
    def fake_run(command, **kwargs):
        assert kwargs["check"] is True
        calls.append(list(command))
        return SimpleNamespace(stdout="cu, version 0.1.0b1\n", returncode=0)

    display_module = ModuleType("IPython.display")
    display_module.Markdown = lambda value: value
    display_module.display = lambda value: None
    monkeypatch.setitem(sys.modules, "IPython.display", display_module)
    monkeypatch.setenv("CU_GOLDEN_CLI", "official-cu")
    monkeypatch.delenv("CU_GOLDEN_RUN_LIVE", raising=False)
    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.chdir(REPO)
    namespace = {}
    cells = notebook_cells()
    for name in ("benchmark-config", "validate-schemas", "plan-runs"):
        exec("".join(cells[name]["source"]), namespace)
    namespace["NEW_RESULTS"] = workspace / "new_cli_results"
    return namespace, calls, cells


def test_notebook_default_is_offline_and_native_contracts_are_exact(workspace, monkeypatch):
    namespace, calls, cells = notebook_namespace(monkeypatch, workspace)
    before = len(calls)
    exec("".join(cells["live-runs"]["source"]), namespace)
    assert namespace["RUN_LIVE"] is False
    assert len(calls) == before
    assert not namespace["NEW_RESULTS"].exists()
    assert len([call for call in calls if call[1:3] == ["analyzer", "validate"]]) == 2
    plans = [call for call in calls if call[1] == "analyze"]
    assert len(plans) == 2
    for call in plans:
        assert "--dry-run" in call and "--yes" not in call
        assert call[call.index("--on-existing") + 1] == "error"
        assert call[call.index("--concurrency") + 1] == "5"
        assert "--json" in call and "--report-file" in call


def test_notebook_live_cells_mocked_only_and_exit_failure_stops_next_mode(workspace, monkeypatch):
    namespace, calls, cells = notebook_namespace(monkeypatch, workspace)
    namespace["RUN_LIVE"] = True
    exec("".join(cells["live-runs"]["source"]), namespace)
    creates = [call for call in calls if call[1:3] == ["analyzer", "create"]]
    shows = [call for call in calls if call[1:3] == ["analyzer", "show"]]
    paid = [call for call in calls if call[1] == "analyze" and "--yes" in call]
    assert len(creates) == len(shows) == len(paid) == 2
    assert all("--name" in call and "--schema" in call for call in creates)
    assert all("--json" not in call and "--output-file" not in call for call in shows)
    assert paid[0][paid[0].index("--api-version") + 1] == "2025-11-01"
    assert paid[1][paid[1].index("--api-version") + 1] == "2026-06-01-preview"

    namespace["NEW_RESULTS"] = workspace / "failed_cli_results"
    attempts = []
    def fail_analyze(command, **kwargs):
        attempts.append(command)
        if command[1] == "analyze":
            raise subprocess.CalledProcessError(1, command)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(subprocess, "run", fail_analyze)
    with pytest.raises(subprocess.CalledProcessError):
        exec("".join(cells["live-runs"]["source"]), namespace)
    assert len(attempts) == 3
    assert not any(namespace["AGENTIC_ID"] in call for call in attempts)


@pytest.mark.parametrize("mode,version", [("standard", "2025-11-01"), ("agentic", "2026-06-01-preview")])
def test_official_cli_schema_validation_and_dry_run_only(workspace, mode, version):
    cli = REPO / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / ("cu.exe" if sys.platform == "win32" else "cu")
    if not cli.is_file():
        pytest.skip("Pinned official CLI virtual environment is not installed")
    schema = PROJECT / "schemas" / f"contract_obligations_{mode}_v1.json"
    validation = subprocess.run(
        [str(cli), "analyzer", "validate", str(schema), "--api-version", version],
        stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    assert validation.returncode == 0, validation.stdout + validation.stderr
    samples = workspace / "samples"
    samples.mkdir()
    (samples / "one.txt").write_text(QUOTE, encoding="utf-8")
    output = workspace / "new_results"
    plan = subprocess.run([
        str(cli), "analyze", "--source", str(samples), "--recursive",
        "--analyzer", "golden_offline_v2", "--json", "--output-dir", str(output),
        "--report-file", str(output / "report.json"), "--api-version", version,
        "--concurrency", "5", "--on-existing", "error", "--usage", "--time", "--dry-run",
    ], stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    assert plan.returncode == 0, plan.stdout + plan.stderr
    assert not output.exists()
