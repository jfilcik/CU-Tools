"""Cost coverage from native and historical JSON, without credentials or services."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOL))
from cu_cost_estimator import (
    CostEstimator, ProcessingRequest, UsageData, extract_usage_from_cu_output,
)
from generate_cost_summary import generate_cost_summary


def usage(model="gpt-4.1", incoming=100, outgoing=20, pages=1, ctx=1000):
    return {
        "tokens": {f"{model}-input": incoming, f"{model}-output": outgoing},
        "documentPagesStandard": pages,
        "contextualizationToken": ctx,
    }


def write_result(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.mark.parametrize("shape", ["native", "envelope", "nested"])
def test_usage_locations_and_singular_contextualization(tmp_path, shape):
    payload = {"contents": [{"fields": {}}]}
    if shape == "native":
        data = {**payload, "usage": usage()}
    elif shape == "envelope":
        data = {"result": payload, "usage": usage()}
    else:
        data = {"result": {**payload, "usage": usage()}}
    path = write_result(tmp_path / "a.pdf.result.json", data)
    actual = extract_usage_from_cu_output(str(path))
    assert actual["input_tokens"] == 100
    assert actual["output_tokens"] == 20
    assert actual["document_pages"] == 1
    assert actual["contextualization_tokens"] == 1000
    assert actual["models"] == ["gpt-4.1"]


def test_plural_contextualization_legacy_alias(tmp_path):
    measured = usage()
    measured["contextualizationTokens"] = measured.pop("contextualizationToken")
    path = write_result(tmp_path / "old.json", {"result": {}, "usage": measured})
    assert extract_usage_from_cu_output(str(path))["contextualization_tokens"] == 1000


def test_nested_results_count_once_and_keep_repeated_basename(tmp_path, capsys):
    write_result(tmp_path / "top.result.json", {"contents": [], "usage": usage()})
    for trial in ("trial1", "trial2"):
        write_result(tmp_path / "raw" / "A" / trial / "doc.pdf.result.json", {"contents": [], "usage": usage()})
    write_result(tmp_path / "anything.json", {
        "schema": "cu-cli/analyze-report/v1", "counts": {"failed": 1}, "results": [],
    })
    write_result(tmp_path / "schema.json", {"fieldSchema": {}})
    write_result(tmp_path / "experiment.json", {"status": "completed"})
    write_result(tmp_path / "run.json", {"status": "succeeded", "jobs": [{"status": "failed"}]})
    result = generate_cost_summary(str(tmp_path))
    assert capsys.readouterr().out == ""
    assert result["batch_summary"]["total_documents"] == 3
    assert result["usage_summary"]["total_input_tokens"] == 300
    assert len({item["result_file"] for item in result["documents"]}) == 3
    assert result["cost_breakdown"]["total_cost"] == pytest.approx(3 * (0.005 + 0.001 + 0.0002 + 0.00016))
    assert result["batch_summary"]["successfully_processed"] == 0
    assert result["batch_summary"]["status_unknown"] == 3
    assert "not actual spend" in result["pricing_note"]


def test_missing_usage_unknown_not_zero_and_failed_results_count(tmp_path):
    write_result(tmp_path / "good.result.json", {"contents": [], "usage": usage()})
    write_result(tmp_path / "unknown.result.json", {"contents": [{"fields": {}}]})
    write_result(tmp_path / "failed.json", {"status": "failed", "error": {"code": "Failure"}})
    summary = generate_cost_summary(str(tmp_path), model="gpt-4.1")
    assert summary["batch_summary"]["total_documents"] == 3
    assert summary["batch_summary"]["failed_to_process"] == 1
    assert summary["coverage"]["results_with_usage"] == 1
    assert summary["coverage"]["usage_percent"] == 33.3
    assert summary["cost_breakdown"]["total_cost"] is None
    assert summary["usage_summary"]["total_input_tokens"] is None
    assert summary["covered_usage_summary"]["total_input_tokens"] == 100
    assert summary["covered_cost_breakdown"]["total_cost"] > 0
    assert summary["cost_per_document"] is None


def test_all_missing_usage_produces_unknown_summary(tmp_path):
    path = write_result(tmp_path / "a.pdf.result.json", {"contents": []})
    with pytest.raises(ValueError, match="No structured usage"):
        extract_usage_from_cu_output(str(path))
    summary = generate_cost_summary(str(tmp_path))
    assert summary["cost_breakdown"]["total_cost"] is None
    assert summary["covered_cost_breakdown"]["total_cost"] is None
    assert summary["coverage"]["cost_percent"] == 0


def test_actual_zero_usage_is_known_zero_not_missing(tmp_path):
    path = write_result(tmp_path / "zero.result.json", {
        "contents": [], "usage": usage(incoming=0, outgoing=0, pages=0, ctx=0),
    })
    assert extract_usage_from_cu_output(str(path))["input_tokens"] == 0
    summary = generate_cost_summary(str(tmp_path))
    assert summary["coverage"]["complete"]
    assert summary["cost_breakdown"]["total_cost"] == 0
    assert summary["cost_per_document"] == 0
    assert summary["cost_per_page"] is None
    # Explicitly measured zero pages must not fall back to the requested quantity.
    breakdown = CostEstimator().estimate_from_usage(ProcessingRequest(
        "document", 1000, usage_data=UsageData(0, 0),
    ))
    assert breakdown.total_cost == 0


@pytest.mark.parametrize("missing", ["tokens", "contextualizationToken", "documentPagesStandard"])
def test_incomplete_usage_is_not_zero_filled(tmp_path, missing):
    measured = usage()
    measured.pop(missing)
    path = write_result(tmp_path / "incomplete.result.json", {"contents": [], "usage": measured})
    with pytest.raises(ValueError):
        extract_usage_from_cu_output(str(path))
    assert generate_cost_summary(str(tmp_path))["cost_breakdown"]["total_cost"] is None


@pytest.mark.parametrize("tokens", [
    {}, {"m-input": 0}, {"unknown": 10}, {"m-input": -1, "m-output": 0},
    {"m-input": None, "m-output": 0}, {"m-input": True, "m-output": 0},
    {"m-input": "100", "m-output": 0}, {"m-input": 1.5, "m-output": 0},
])
def test_no_token_guessing_or_invalid_counts(tmp_path, tokens):
    path = write_result(tmp_path / "invalid.result.json", {
        "contents": [], "usage": {**usage(), "tokens": tokens},
    })
    with pytest.raises(ValueError):
        extract_usage_from_cu_output(str(path))


def test_unpriced_or_mismatched_models_remain_unknown(tmp_path):
    path = write_result(tmp_path / "new.result.json", {"contents": [], "usage": usage(model="new-model")})
    summary = generate_cost_summary(str(path))
    assert summary["coverage"]["results_with_usage"] == 1
    assert summary["coverage"]["results_with_cost_estimate"] == 0
    assert summary["cost_breakdown"]["total_cost"] is None
    mismatch = generate_cost_summary(str(path), model="gpt-4o")
    assert mismatch["cost_breakdown"]["total_cost"] is None
    assert "differs" in mismatch["documents"][0]["error"]


def test_multiple_models_not_repriced_as_one(tmp_path):
    measured = usage()
    measured["tokens"].update({"gpt-4o-input": 100, "gpt-4o-output": 20})
    path = write_result(tmp_path / "mixed.result.json", {"contents": [], "usage": measured})
    summary = generate_cost_summary(str(path))
    assert summary["coverage"]["results_with_usage"] == 1
    assert summary["cost_breakdown"]["total_cost"] is None
    assert "Multiple measured models" in summary["documents"][0]["error"]


def test_malformed_actual_result_fails_summary(tmp_path):
    (tmp_path / "broken.result.json").write_text("{", encoding="utf-8")
    with pytest.raises(ValueError, match="broken.result.json"):
        generate_cost_summary(str(tmp_path))


def test_report_is_not_explicit_analysis_input(tmp_path):
    path = write_result(tmp_path / "report.json", {"schema": "cu-cli/analyze-report/v1", "results": []})
    with pytest.raises(ValueError, match="metadata"):
        generate_cost_summary(str(path))


def test_cli_zero_usage_and_machine_readable_json(tmp_path):
    path = write_result(tmp_path / "zero.result.json", {"contents": [], "usage": usage(incoming=0, outgoing=0, pages=0, ctx=0)})
    commands = [
        [str(TOOL / "cu_cost_estimator.py"), "estimate-usage", "--cu-output", str(path), "--json"],
        [str(TOOL / "cu_cost_estimator.py"), "estimate-usage", "--input-tokens", "0", "--output-tokens", "0",
         "--ctx-tokens", "0", "--pages", "0", "--model", "gpt-4.1", "--json"],
        [str(TOOL / "generate_cost_summary.py"), str(tmp_path), "--json"],
    ]
    for command in commands:
        process = subprocess.run([sys.executable, *command], stdin=subprocess.DEVNULL, capture_output=True, text=True)
        assert process.returncode == 0, process.stderr
        assert isinstance(json.loads(process.stdout), dict)


def test_missing_usage_command_fails_nonzero(tmp_path):
    path = write_result(tmp_path / "a.result.json", {"contents": []})
    process = subprocess.run(
        [sys.executable, str(TOOL / "cu_cost_estimator.py"), "estimate-usage", "--cu-output", str(path), "--json"],
        stdin=subprocess.DEVNULL, capture_output=True, text=True,
    )
    assert process.returncode != 0
    assert "No structured usage" in process.stderr


def test_explicit_usage_requires_page_and_context_counts():
    process = subprocess.run(
        [sys.executable, str(TOOL / "cu_cost_estimator.py"), "estimate-usage", "--input-tokens", "0",
         "--output-tokens", "0", "--model", "gpt-4.1", "--json"],
        stdin=subprocess.DEVNULL, capture_output=True, text=True,
    )
    assert process.returncode != 0
    assert "requires --ctx-tokens and --pages" in process.stderr


def test_null_envelope_usage_does_not_hide_nested_usage(tmp_path):
    path = write_result(tmp_path / "a.result.json", {
        "usage": None, "result": {"contents": [], "usage": usage()},
    })
    assert extract_usage_from_cu_output(str(path))["input_tokens"] == 100


def test_text_output_is_written_and_not_empty(tmp_path):
    raw = tmp_path / "raw"
    write_result(raw / "a.result.json", {"contents": []})
    output = tmp_path / "summary.txt"
    process = subprocess.run(
        [sys.executable, str(TOOL / "generate_cost_summary.py"), str(raw), "--output", str(output)],
        stdin=subprocess.DEVNULL, capture_output=True, text=True,
    )
    assert process.returncode == 0, process.stderr
    assert "Full-batch estimate: unknown" in output.read_text(encoding="utf-8")


def test_legacy_explicit_batch_rejects_missing_counts_or_prices():
    with pytest.raises(ValueError, match="requires"):
        CostEstimator().analyze_batch_results([{"file_name": "no-usage.pdf"}])
    with pytest.raises(ValueError, match="Missing model pricing"):
        CostEstimator().analyze_batch_results([{
            "pages": 1, "actual_input_tokens": 0, "actual_output_tokens": 0, "model_name": "unknown",
        }])
