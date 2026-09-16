"""Offline tests for standalone CUAD scoring and result reporting."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

EVALUATION_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EVALUATION_DIR))

from contract_eval_common import (
    f1_score,
    load_run_metadata,
    match_obligations,
    normalize_quote_text,
    normalize_text,
    read_analysis_result,
)
import generate_broad_quality_report as broad_report
import generate_clause_span_report as clause_report


SOURCE = "Buyer shall pay Seller $100 within 30 days after receipt of an invoice."


def _write_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _run_fixture(tmp_path, kind, statuses, *, missing=(), quote=SOURCE):
    result_dir = tmp_path / "results"
    result_dir.mkdir()
    manifest = _write_json(
        tmp_path / "selection.json",
        {
            "documents": [
                {"doc_id": doc_id, "split": "held_out"}
                for doc_id in statuses
            ]
        },
    )
    gold = tmp_path / "gold.jsonl"
    gold.write_text(
        "\n".join(
            json.dumps(
                {
                    "doc_id": doc_id,
                    "source_text": SOURCE,
                    "clauses": [
                        {
                            "category": "Payment",
                            "obligation_type": "Payment",
                            "exact_quote": SOURCE,
                        }
                    ],
                }
            )
            for doc_id in statuses
        ),
        encoding="utf-8",
    )
    mapping = _write_json(tmp_path / "mapping.json", {"Payment": "Payment"})
    _write_json(
        result_dir / "metadata.json",
        {
            "run_id": "offline-fixture",
            "api_version": "2026-06-01-preview",
            "model": "recorded-model",
            "region": "recorded-region",
            "token_summary": {
                "total_input_tokens": 123,
                "total_output_tokens": 45,
            },
            "results": [
                {
                    "document": f"{doc_id}.txt",
                    "status": status,
                    "elapsed_seconds": 60,
                    "error": "" if status == "success" else "Request failed.",
                }
                for doc_id, status in statuses.items()
            ],
        },
    )
    for doc_id, status in statuses.items():
        if status != "success" or doc_id in missing:
            continue
        if kind == "broad":
            fields = {
                "Obligations": {
                    "valueArray": [
                        {
                            "valueObject": {
                                "ObligationType": {"valueString": "Payment"},
                                "Evidence": {
                                    "valueArray": [
                                        {
                                            "valueObject": {
                                                "ExactQuote": {"valueString": quote}
                                            }
                                        }
                                    ]
                                },
                            }
                        }
                    ]
                }
            }
        else:
            fields = {
                "ClauseSpans": {
                    "valueObject": {
                        "Payment": {"valueArray": [{"valueString": quote}]}
                    }
                }
            }
        _write_json(
            result_dir / f"{doc_id}.json",
            {"result": {"contents": [{"fields": fields}]}},
        )
    return result_dir, manifest, gold, mapping


def _score(kind, paths):
    result_dir, manifest, gold, mapping = paths
    if kind == "broad":
        return broad_report.score_run(result_dir, manifest, gold)
    return clause_report.score_run(result_dir, manifest, gold, mapping, 0.55)


def _f1(kind, summary):
    if kind == "broad":
        return summary["quality_all_20_fail_closed"]["clause_discovery_f1"]
    return summary["quality"]["f1"]


def test_matching_and_quote_normalization_remain_deterministic():
    assert normalize_text(" Buyer\u00a0SHALL pay ") == "buyer shall pay"
    assert normalize_quote_text(" Buyer\u00a0SHALL pay ") == "Buyer SHALL pay"
    prediction = {"obligations": [{"exact_quotes": [SOURCE]}]}
    gold = {"obligations": [{"exact_quotes": [SOURCE]}]}
    matches, unmatched_pred, unmatched_gold = match_obligations(prediction, gold)
    assert matches == [(0, 0, 1.0)]
    assert not unmatched_pred
    assert not unmatched_gold
    assert f1_score(1, 1, 2) == pytest.approx((1.0, 0.5, 2 / 3))
    assert f1_score(0, 0, 1) == (0.0, 0.0, 0.0)


@pytest.mark.parametrize("kind", ["broad", "clause"])
def test_standalone_reports_preserve_complete_results_and_returned_usage(tmp_path, kind):
    summary = _score(kind, _run_fixture(tmp_path, kind, {"doc-1": "success"}))
    assert summary["run"]["successful"] == 1
    assert summary["run"]["failed"] == 0
    assert _f1(kind, summary) == 1.0

    report_path = tmp_path / "report.md"
    if kind == "broad":
        assert summary["run"]["region"] == "recorded-region"
        assert summary["run"]["model"] == "recorded-model"
        assert summary["operational"]["reported_tokens"]["input"] == 123
        assert summary["scope_limits"]["atomic_party_role_scored"] is False
        assert summary["scope_limits"]["atomic_completeness_scored"] is False
        broad_report.write_report(summary, report_path.with_suffix(""))
    else:
        assert summary["operational"]["tokens"]["total_input_tokens"] == 123
        clause_report.write_report(summary, report_path)

    markdown = report_path.read_text(encoding="utf-8")
    assert "1/1" in markdown
    assert "100.0%" in markdown
    assert "Southeast Asia" not in markdown
    assert "17 hours" not in markdown
    assert "service log identified" not in markdown
    assert json.loads(report_path.with_suffix(".json").read_text(encoding="utf-8")) == summary
    assert "doc-1" in report_path.with_suffix(".csv").read_text(encoding="utf-8")


@pytest.mark.parametrize("kind", ["broad", "clause"])
def test_failed_documents_remain_in_quality_denominator(tmp_path, kind):
    paths = _run_fixture(
        tmp_path, kind, {"doc-1": "success", "doc-2": "failed"}
    )
    summary = _score(kind, paths)
    assert summary["run"]["successful"] == 1
    assert summary["run"]["failed"] == 1
    assert _f1(kind, summary) == pytest.approx(2 / 3)
    if kind == "broad":
        assert summary["status"] == "FAIL"


@pytest.mark.parametrize("kind", ["broad", "clause"])
@pytest.mark.parametrize("missing_metadata_row", [False, True])
def test_missing_results_are_not_counted_as_success(tmp_path, kind, missing_metadata_row):
    paths = _run_fixture(tmp_path, kind, {"doc-1": "success"}, missing={"doc-1"})
    if missing_metadata_row:
        metadata_path = paths[0] / "metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["results"] = []
        _write_json(metadata_path, metadata)
    summary = _score(kind, paths)
    assert summary["run"]["successful"] == 0
    assert summary["run"]["failed"] == 1
    assert summary["documents"][0]["status"] == "failed"
    assert _f1(kind, summary) == 0.0


@pytest.mark.parametrize("kind", ["broad", "clause"])
def test_empty_benchmarks_fail_instead_of_reporting_success(tmp_path, kind):
    paths = _run_fixture(tmp_path, kind, {})
    with pytest.raises(ValueError, match="no .*documents"):
        _score(kind, paths)


@pytest.mark.parametrize("quote", [SOURCE.lower(), "Buyer must promptly pay Seller."])
def test_broad_grounding_rejects_changed_case_and_paraphrase(tmp_path, quote):
    summary = _score(
        "broad",
        _run_fixture(tmp_path, "broad", {"doc-1": "success"}, quote=quote),
    )
    assert summary["quality_all_20_fail_closed"]["quote_groundedness_on_completed"] == 0.0


def test_missing_run_context_does_not_imply_a_test_environment(tmp_path):
    paths = _run_fixture(tmp_path, "broad", {"doc-1": "success"})
    metadata_path = paths[0] / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    del metadata["region"]
    del metadata["model"]
    _write_json(metadata_path, metadata)
    summary = _score("broad", paths)
    assert summary["run"]["region"] == "not recorded"
    assert summary["run"]["model"] == "not recorded"


def test_broad_report_failure_taxonomy_uses_client_errors():
    assert broad_report._failure_kind("Operation timed out after 1800 seconds") == "timeout"
    assert broad_report._failure_kind("Connection aborted") == "connection_reset"
    assert broad_report._failure_kind("Request failed.") == "request_failed"


def _cli_fixture(tmp_path, kind):
    paths = _run_fixture(tmp_path, kind, {"doc-1": "success"})
    result_dir = paths[0]
    original = result_dir / "doc-1.json"
    raw = json.loads(original.read_text(encoding="utf-8"))
    output = result_dir / "doc-1.txt.json"
    _write_json(output, raw["result"])
    original.unlink()
    (result_dir / "metadata.json").unlink()
    report = {
        "schema": "cu-cli/analyze-report/v1",
        "analyzer": "cuad_unique_id",
        "result_view": "full",
        "counts": {"succeeded": 1, "failed": 0, "skipped": 0, "total": 1},
        "results": [
            {
                "input": "doc-1.txt",
                "status": "succeeded",
                "analyzer": "cuad_unique_id",
                "output": str(output.resolve()),
            }
        ],
    }
    _write_json(result_dir / "analyze-report.json", report)
    return paths, report


@pytest.mark.parametrize("kind", ["broad", "clause"])
def test_native_cli_results_score_without_fabricating_measurements(tmp_path, kind):
    paths, _ = _cli_fixture(tmp_path, kind)
    summary = _score(kind, paths)
    assert summary["run"]["successful"] == 1
    assert summary["run"]["analyzer_id"] == "cuad_unique_id"
    assert summary["documents"][0]["elapsed_seconds"] is None
    assert _f1(kind, summary) == 1.0
    output = tmp_path / "cli-quality.md"
    if kind == "broad":
        assert summary["run"]["wall_seconds"] is None
        assert summary["operational"]["latency_seconds"]["mean"] is None
        assert summary["operational"]["reported_tokens"]["input"] is None
        broad_report.write_report(summary, output.with_suffix(""))
    else:
        assert summary["run"]["active_wall_seconds"] is None
        assert summary["run"]["attempt_count"] is None
        assert summary["operational"]["latency_mean_seconds"] is None
        assert summary["operational"]["tokens"]["total_input_tokens"] is None
        clause_report.write_report(summary, output)
    markdown = output.read_text(encoding="utf-8")
    assert "not recorded" in markdown
    assert "0.0 min" not in markdown
    assert "0.00 hours" not in markdown


@pytest.mark.parametrize("kind", ["broad", "clause"])
@pytest.mark.parametrize("status", ["failed", "skipped"])
def test_cli_failed_and_skipped_rows_do_not_reuse_existing_results(tmp_path, kind, status):
    paths, report = _cli_fixture(tmp_path, kind)
    report["results"][0]["status"] = status
    report["results"][0]["reason"] = "not analyzed in this run"
    _write_json(paths[0] / "analyze-report.json", report)
    summary = _score(kind, paths)
    assert summary["run"]["successful"] == 0
    assert summary["run"]["failed"] == 1
    assert _f1(kind, summary) == 0.0


@pytest.mark.parametrize("kind", ["broad", "clause"])
def test_cli_success_without_saved_output_fails_closed(tmp_path, kind):
    paths, report = _cli_fixture(tmp_path, kind)
    report["results"][0]["output"] = None
    _write_json(paths[0] / "analyze-report.json", report)
    assert _score(kind, paths)["run"]["successful"] == 0


@pytest.mark.parametrize(
    ("field", "value"),
    [("schema", "cu-cli/analyze-report/v2"), ("result_view", "llm-input")],
)
def test_cli_reader_rejects_unknown_report_contracts(tmp_path, field, value):
    paths, report = _cli_fixture(tmp_path, "broad")
    report[field] = value
    _write_json(paths[0] / "analyze-report.json", report)
    with pytest.raises(ValueError, match="cu-cli/analyze-report/v1"):
        load_run_metadata(paths[0])


def test_cli_reader_rejects_ambiguous_document_stems(tmp_path):
    paths, report = _cli_fixture(tmp_path, "broad")
    report["results"].append(dict(report["results"][0], input="another/doc-1.txt"))
    _write_json(paths[0] / "analyze-report.json", report)
    with pytest.raises(ValueError, match="Duplicate document stem"):
        load_run_metadata(paths[0])


def test_cli_reader_rejects_outputs_outside_the_results_directory(tmp_path):
    paths, report = _cli_fixture(tmp_path, "broad")
    report["results"][0]["output"] = str(tmp_path / "outside.json")
    _write_json(paths[0] / "analyze-report.json", report)
    with pytest.raises(ValueError, match="outside"):
        load_run_metadata(paths[0])


@pytest.mark.parametrize("kind", ["broad", "clause"])
def test_explicitly_recorded_zero_usage_and_latency_remain_zero(tmp_path, kind):
    paths = _run_fixture(tmp_path, kind, {"doc-1": "success"})
    metadata_path = paths[0] / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["results"][0]["elapsed_seconds"] = 0
    metadata["token_summary"]["total_input_tokens"] = 0
    _write_json(metadata_path, metadata)
    summary = _score(kind, paths)
    assert summary["documents"][0]["elapsed_seconds"] == 0
    if kind == "broad":
        assert summary["operational"]["reported_tokens"]["input"] == 0
    else:
        assert summary["operational"]["tokens"]["total_input_tokens"] == 0


@pytest.mark.parametrize("kind", ["broad", "clause"])
def test_result_failure_overrides_success_in_cli_status_report(tmp_path, kind):
    paths, report = _cli_fixture(tmp_path, kind)
    output = Path(report["results"][0]["output"])
    raw = json.loads(output.read_text(encoding="utf-8"))
    raw["status"] = "Failed"
    _write_json(output, raw)
    summary = _score(kind, paths)
    assert summary["run"]["successful"] == 0
    assert summary["run"]["failed"] == 1
    assert _f1(kind, summary) == 0.0


@pytest.mark.parametrize("kind", ["broad", "clause"])
def test_malformed_expected_results_raise_shared_format_error(tmp_path, kind):
    paths, report = _cli_fixture(tmp_path, kind)
    _write_json(Path(report["results"][0]["output"]), {"contents": "invalid"})
    with pytest.raises(ValueError, match="contents") as exc:
        _score(kind, paths)
    assert type(exc.value).__name__ == "ResultFormatError"


@pytest.mark.parametrize("kind", ["broad", "clause"])
def test_expected_documents_missing_from_cli_report_remain_in_denominator(tmp_path, kind):
    paths, _ = _cli_fixture(tmp_path, kind)
    _, manifest, gold, _ = paths
    _write_json(
        manifest,
        {"documents": [
            {"doc_id": "doc-1", "split": "held_out"},
            {"doc_id": "doc-2", "split": "held_out"},
        ]},
    )
    record = json.loads(gold.read_text(encoding="utf-8"))
    with gold.open("a", encoding="utf-8") as stream:
        stream.write("\n" + json.dumps({**record, "doc_id": "doc-2"}))
    summary = _score(kind, paths)
    assert summary["run"]["successful"] == 1
    assert summary["run"]["failed"] == 1
    assert _f1(kind, summary) == pytest.approx(2 / 3)


def test_shared_result_loader_preserves_existing_metadata(tmp_path):
    path = _write_json(
        tmp_path / "doc-1.result.json",
        {
            "contents": [{"fields": {}}],
            "_metadata": {"source_file": "original.pdf", "marker": "retained"},
        },
    )
    result = read_analysis_result(path)
    assert result["result"]["contents"] == [{"fields": {}}]
    assert result["_metadata"]["source_file"] == "original.pdf"
    assert result["_metadata"]["marker"] == "retained"


@pytest.mark.parametrize("kind", ["broad", "clause"])
def test_native_cli_lro_envelope_preserves_page_usage_without_inventing_tokens(tmp_path, kind):
    paths, report = _cli_fixture(tmp_path, kind)
    output = Path(report["results"][0]["output"])
    payload = json.loads(output.read_text(encoding="utf-8"))
    _write_json(
        output,
        {
            "id": "offline-operation",
            "status": "Succeeded",
            "result": payload,
            "usage": {"documentPagesStandard": 1},
        },
    )
    loaded = read_analysis_result(output)
    assert loaded["id"] == "offline-operation"
    assert loaded["usage"] == {"documentPagesStandard": 1}
    assert loaded["result"]["contents"] == payload["contents"]
    summary = _score(kind, paths)
    assert summary["run"]["successful"] == 1
    assert _f1(kind, summary) == 1.0
    assert summary["documents"][0]["elapsed_seconds"] is None
    if kind == "broad":
        assert summary["operational"]["reported_tokens"]["input"] is None
    else:
        assert summary["operational"]["tokens"]["total_input_tokens"] is None
