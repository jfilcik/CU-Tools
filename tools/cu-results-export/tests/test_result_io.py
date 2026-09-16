"""Offline native CLI discovery, typed extraction, and honest diagnosis coverage."""

import copy
import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOL))

from cu_result_io import ResultFormatError, load_results, normalize_result, result_payload
from export import (
    _compute_cu_fill_rates, build_table_rows, diagnose_fields, discover_all_fields,
    export_to_csv, extract_all_confidences, flatten_fields, generate_summary,
)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def native_result():
    return {
        "analyzerId": "invoice_v2",
        "contents": [{
            "category": "invoice",
            "markdown": "Invoice 123",
            "fields": {
                "Number": {"type": "string", "valueString": "123", "confidence": 0.95, "source": "D(1,1,2,3,4)"},
                "Total": {"type": "number", "valueNumber": 0, "confidence": 0.91},
                "Paid": {"type": "boolean", "valueBoolean": False},
                "Due": {"type": "date", "valueDate": "2026-10-01"},
                "Vendor": {"type": "object", "valueObject": {
                    "Name": {"type": "string", "valueString": "Acme", "confidence": 0.8},
                }},
                "Items": {"type": "array", "valueArray": [
                    {"type": "object", "valueObject": {
                        "Count": {"type": "integer", "valueInteger": 2, "confidence": 0.7, "source": "D(1,0,0,1,1)"},
                        "Tags": {"type": "array", "valueArray": [
                            {"type": "string", "valueString": "new"},
                        ]},
                    }},
                ]},
            },
        }],
    }


def test_native_typed_fields_grounding_and_categories(tmp_path):
    path = write_json(tmp_path / "invoice.pdf.result.json", native_result())
    before = path.read_bytes()
    results = load_results(path)
    columns = discover_all_fields(results)
    rows = build_table_rows(results, columns)
    row = rows[0]
    assert row["invoice.Number"] == "123"
    assert row["invoice.Total"] == 0
    assert row["invoice.Paid"] is False
    assert row["invoice.Vendor.Name"] == "Acme"
    assert row["invoice.Due"] == "2026-10-01"
    assert row["invoice.Number.confidence"] == 0.95
    assert row["invoice.Number.source"] == "D(1,1,2,3,4)"
    assert json.loads(row["invoice.Items"]) == [{"Count": 2, "Tags": ["new"]}]
    assert json.loads(row["invoice.Items._raw"])["valueArray"][0]["valueObject"]["Count"]["confidence"] == 0.7
    assert row["analyzer_id"] == "invoice_v2"
    assert row["iteration"] == row["run_id"] == row["status"] == row["timestamp"] == ""
    assert row["document"] == "invoice.pdf"
    assert not any("valueString" in column or column.endswith(".type") for column in columns)
    conf = extract_all_confidences(results)[0]
    assert conf["invoice.Vendor.Name"] == 0.8
    assert conf["invoice.Items[0].Count"] == 0.7
    assert path.read_bytes() == before
    output = tmp_path / "export.csv"
    export_to_csv(rows, output, columns)
    with output.open(encoding="utf-8", newline="") as handle:
        assert list(csv.DictReader(handle))[0]["invoice.Number"] == "123"


def test_legacy_envelope_and_values_preserved():
    saved = {
        "_metadata": {"source_file": "old.pdf", "iteration": 4, "run_id": "r"},
        "status": "Succeeded",
        "result": {"fields": {
            "Total": {"value": 12, "confidence": 0.9},
            "Vendor": {"value": {"Name": {"value": "Acme"}}},
            "Tags": {"values": ["a", "b"]},
        }},
    }
    before = copy.deepcopy(saved)
    normalized = normalize_result(saved)
    row = build_table_rows([normalized], discover_all_fields([normalized]))[0]
    assert row["Total"] == 12
    assert row["Vendor.Name"] == "Acme"
    assert json.loads(row["Tags"]) == ["a", "b"]
    assert row["iteration"] == 4 and row["run_id"] == "r"
    assert saved == before


def test_nested_discovery_excludes_metadata_and_preserves_duplicate_names(tmp_path):
    for relative in [
        Path("A") / "trial1" / "invoice.pdf.result.json",
        Path("A") / "trial2" / "invoice.pdf.result.json",
        Path("B") / "trial1" / "invoice.pdf.result.json",
    ]:
        write_json(tmp_path / relative, native_result())
    write_json(tmp_path / "legacy.json", {"result": {"fields": {"N": {"value": 1}}}})
    report = {"schema": "cu-cli/analyze-report/v1", "counts": {"total": 4}, "results": [
        {"input": "invoice.pdf", "status": "failed"},
    ]}
    write_json(tmp_path / "arbitrary-name.json", report)
    write_json(tmp_path / "schemas" / "v1.json", {"fieldSchema": {"fields": {"N": {"type": "string"}}}})
    write_json(tmp_path / "schemas" / "fields-only.json", {
        "fields": {"N": {"type": "string", "method": "extract", "description": "Identifier"}},
    })
    write_json(tmp_path / "experiment.json", {"status": "completed", "results": []})
    write_json(tmp_path / "export.summary.json", {"total_rows": 4})
    write_json(tmp_path / "export.diagnosis.json", [])
    write_json(tmp_path / "comparison.json", {"status": "completed"})
    results = load_results(tmp_path)
    assert len(results) == 4
    assert len({r["_metadata"]["source_file"] for r in results}) == 4
    assert len({r["_metadata"]["result_file"] for r in results}) == 4
    assert any(str(Path("A") / "trial2") in r["_metadata"]["source_file"] for r in results)
    rows = build_table_rows(results, discover_all_fields(results))
    assert generate_summary(rows, [])["unique_result_files"] == 4
    assert len(load_results(tmp_path)) == 4


def test_experiment_execution_state_and_reports_are_not_analysis_results(tmp_path):
    relative = Path("batches") / "analyzer-0001" / "results" / "trial-0001" / "input-0001" / "invoice.pdf.result.json"
    write_json(tmp_path / relative, native_result())
    run = write_json(tmp_path / "run.json", {
        "status": "succeeded", "jobs": [{"input": "missing.pdf", "status": "failed"}],
    })
    report = write_json(tmp_path / "batches" / "analyzer-0001" / "native-report.json", {
        "schema": "cu-cli/analyze-report/v1", "counts": {"failed": 1},
        "results": [{"input": "missing.pdf", "status": "failed"}],
    })
    results = load_results(tmp_path)
    assert len(results) == 1
    assert results[0]["_metadata"]["result_file"] == str(relative)
    for metadata_file in (run, report):
        with pytest.raises(ResultFormatError, match="metadata"):
            load_results(metadata_file)


@pytest.mark.parametrize("data", [
    {}, [], {"schema": "cu-cli/analyze-report/v1", "results": []},
    {"baseAnalyzerId": "prebuilt-document", "fieldSchema": {}},
    {"contents": {}}, {"contents": [None]}, {"contents": [{"fields": None}]},
    {"result": []}, {"result": "bad"},
])
def test_explicit_invalid_or_metadata_file_is_an_error(tmp_path, data):
    path = write_json(tmp_path / "input.json", data)
    with pytest.raises(ResultFormatError, match="input.json"):
        load_results(path)


@pytest.mark.parametrize("data", [{}, [], {"contents": None}, {"fieldSchema": {}}])
def test_named_native_result_never_silently_skipped(tmp_path, data):
    write_json(tmp_path / "nested" / "bad.pdf.result.json", data)
    with pytest.raises(ResultFormatError, match="bad.pdf.result.json"):
        load_results(tmp_path)


@pytest.mark.parametrize("filename", ["bad.pdf.result.json", "legacy-analysis.json"])
def test_malformed_json_fails_directory_discovery(tmp_path, filename):
    (tmp_path / filename).write_text('{"contents": [', encoding="utf-8")
    with pytest.raises(ResultFormatError, match=filename):
        load_results(tmp_path)


def test_failed_empty_and_null_results_stay_in_fill_denominator():
    results = [
        {"contents": [{"fields": {
            "Zero": {"type": "number", "valueNumber": 0},
            "False": {"type": "boolean", "valueBoolean": False},
            "Absent": {"type": "string", "valueString": None},
            "Empty": {"type": "array", "valueArray": []},
        }}]},
        {"contents": []},
        {"status": "Failed", "error": {"code": "Failure"}, "result": {"fields": {
            "Zero": {"value": 99, "confidence": 0.9},
        }}},
        {"contents": [{"category": "other"}]},
    ]
    rates = _compute_cu_fill_rates(results, {"Zero", "False", "Absent", "Empty"})
    assert rates == {"Zero": 25.0, "False": 25.0, "Absent": 0.0, "Empty": 0.0}
    diagnostics = {d["field"]: d for d in diagnose_fields(results, [], {})}
    assert diagnostics["Zero"]["total_docs"] == 4
    assert diagnostics["Zero"]["present_count"] == 1
    assert diagnostics["Zero"]["confidence_count"] == 0
    rows = build_table_rows(results, ["Zero", "False"])
    assert len(rows) == 4
    assert rows[2]["Zero"] == "" and rows[2]["status"] == "Failed"


def test_classification_columns_are_not_lost_or_cross_populated():
    result = {"contents": [
        {"category": "invoice", "fields": {"Number": {"valueString": "I"}}},
        {"category": "receipt", "fields": {"Number": {"valueString": "R"}}},
        {"category": "other"},
    ]}
    rows = build_table_rows([result], discover_all_fields([result]))
    assert rows[0]["invoice.Number"] == "I" and rows[0]["receipt.Number"] == ""
    assert rows[1]["receipt.Number"] == "R" and rows[1]["invoice.Number"] == ""
    assert rows[2]["category"] == "other"


def test_empty_array_not_filled_but_literal_json_string_is_filled():
    result = {"contents": [{"fields": {
        "Empty": {"type": "array", "valueArray": []},
        "Literal": {"type": "string", "valueString": "[]"},
    }}]}
    columns = discover_all_fields([result])
    summary = generate_summary(build_table_rows([result], columns), columns)
    assert summary["fill_rates"]["Empty"] == 0
    assert summary["fill_rates"]["Literal"] == 100


def test_legacy_array_objects_keep_non_cu_type_property():
    fields = {"Items": {"value": [{"type": "product", "description": "widget"}]}}
    assert json.loads(flatten_fields(fields)["Items"]) == [{"type": "product", "description": "widget"}]


def test_layout_and_null_envelopes_are_not_success_shaped(tmp_path):
    write_json(tmp_path / "layout.pdf.result.json", {"contents": [{"markdown": "plain text"}]})
    write_json(tmp_path / "failed.json", {"status": "failed", "result": None})
    results = load_results(tmp_path)
    assert len(results) == 2
    assert result_payload(results[0]) == {}
    assert build_table_rows(results, [])[0]["status"] == "failed"


def test_export_command_offline_and_malformed_exit(tmp_path):
    raw = tmp_path / "raw"
    write_json(raw / "nested" / "invoice.pdf.result.json", native_result())
    target = tmp_path / "out" / "fields.csv"
    process = subprocess.run(
        [sys.executable, str(TOOL / "export.py"), "--input", str(raw), "--output", str(target), "--diagnose"],
        stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8",
        env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert process.returncode == 0, process.stderr
    assert target.exists() and target.with_suffix(".diagnosis.json").exists()
    (raw / "broken.result.json").write_text("{", encoding="utf-8")
    failed = subprocess.run(
        [sys.executable, str(TOOL / "export.py"), "--input", str(raw), "--summary-only"],
        stdin=subprocess.DEVNULL, capture_output=True, text=True,
    )
    assert failed.returncode != 0 and "broken.result.json" in failed.stderr


@pytest.mark.parametrize("diagnose", [False, True])
def test_redirected_cp1252_export_of_lro_envelope(tmp_path, diagnose):
    source = write_json(tmp_path / "invoice.pdf.result.json", {
        "id": "saved-operation",
        "status": "Succeeded",
        "result": native_result(),
        "usage": {"documentPagesStandard": 1},
    })
    target = tmp_path / "fields.csv"
    command = [
        sys.executable, str(TOOL / "export.py"),
        "--input", str(source), "--output", str(target),
    ]
    if diagnose:
        command.append("--diagnose")
    process = subprocess.run(
        command, stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8",
        env={**__import__("os").environ, "PYTHONIOENCODING": "cp1252"},
    )
    assert process.returncode == 0, process.stderr
    assert "✓ Exported 1 rows" in process.stdout
    assert "✓ Summary saved" in process.stdout
    assert target.exists()
    assert json.loads(target.with_suffix(".summary.json").read_text(encoding="utf-8"))["total_rows"] == 1
    if diagnose:
        assert target.with_suffix(".diagnosis.json").exists()


def test_library_import_preserves_stream_encodings():
    code = (
        f"import sys; sys.path.insert(0, {str(TOOL)!r}); "
        "before = (sys.stdout.encoding, sys.stderr.encoding); "
        "import export; "
        "assert before == (sys.stdout.encoding, sys.stderr.encoding); "
        "assert before == ('cp1252', 'cp1252')"
    )
    process = subprocess.run(
        [sys.executable, "-c", code],
        stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8",
        env={**__import__("os").environ, "PYTHONIOENCODING": "cp1252"},
    )
    assert process.returncode == 0, process.stderr
