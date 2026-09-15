import importlib.util
import json
import sys
from pathlib import Path


SPEC = importlib.util.spec_from_file_location(
    "usage_diagnostics", Path(__file__).resolve().parents[1] / "usage_diagnostics.py"
)
usage_diagnostics = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = usage_diagnostics
SPEC.loader.exec_module(usage_diagnostics)


def make_line(enqueue_time: str, correlation_id: str, prompt: list[int], cached: list[int], generated: list[int], *, deployment: str = "dep-a", model: str = "gpt-4o-mini", version: str = "2026-01-01") -> str:
    return json.dumps({
        "EnqueueTime": enqueue_time,
        "correlationId": correlation_id,
        "properties": json.dumps({
            "modelDeploymentName": deployment,
            "modelName": model,
            "modelVersion": version,
            "promptTokens": prompt,
            "cachedTokens": cached,
            "generatedTokens": generated,
        }),
    })


def test_parse_blob_and_correlate_requests():
    blob_text = "\n".join([
        make_line("2026-09-12T20:00:02Z", "c-2", [100], [50], [20]),
        make_line("2026-09-12T20:00:01Z", "c-1", [40, 60], [10, 20], [5, 5]),
        make_line("2026-09-12T20:00:03Z", "c-3", [80], [0], [10], deployment="dep-b", model="gpt-4.1"),
        make_line("2026-09-12T20:00:04Z", "c-4", [30], [15], [4]),
    ])
    records = usage_diagnostics.parse_blob_text(
        "synthetic.json",
        blob_text,
        start=usage_diagnostics.parse_timestamp("2026-09-12T20:00:00Z", name="start"),
        end=usage_diagnostics.parse_timestamp("2026-09-12T21:00:00Z", name="end"),
    )

    assert len(records) == 4
    assert records[1].prompt_tokens == 100
    assert records[1].cached_tokens == 30
    groups, warnings, unassigned = usage_diagnostics.correlate_requests(records, [2, 1])

    assert len(groups) == 2
    assert groups[0]["record_count"] == 2
    assert groups[0]["prompt_tokens"] == 200
    assert groups[0]["cached_tokens"] == 80
    assert groups[0]["generated_tokens"] == 30
    assert groups[0]["cache_hit_ratio"] == 0.4
    assert groups[1]["record_count"] == 1
    assert groups[1]["prompt_tokens"] == 80
    assert groups[1]["models"][0]["modelDeploymentName"] == "dep-b"
    assert warnings == ["Requested 3 correlated model calls but 4 records were available; 1 record(s) remain unassigned"]
    assert usage_diagnostics.aggregate_records(unassigned) == {
        "record_count": 1,
        "prompt_tokens": 30,
        "cached_tokens": 15,
        "generated_tokens": 4,
        "cache_hit_ratio": 0.5,
    }


def test_naive_enqueue_time_is_treated_as_utc():
    # Real AzureOpenAIRequestUsage exports have no timezone suffix on EnqueueTime
    # (unlike the sibling FluentdIngestTimestamp field, which does carry one).
    blob_text = make_line("2026-09-15T20:20:36.6220000", "c-1", [100], [0], [10])
    records = usage_diagnostics.parse_blob_text(
        "synthetic.json",
        blob_text,
        start=usage_diagnostics.parse_timestamp("2026-09-15T20:00:00Z", name="start"),
        end=usage_diagnostics.parse_timestamp("2026-09-15T21:00:00Z", name="end"),
    )
    assert len(records) == 1
    assert records[0].enqueue_time.tzinfo is not None
    assert records[0].enqueue_time.utcoffset().total_seconds() == 0
    assert records[0].enqueue_time.hour == 20
    assert records[0].enqueue_time.minute == 20


def test_start_and_end_still_require_explicit_timezone():
    import pytest

    with pytest.raises(usage_diagnostics.UsageDiagnosticsError, match="must include a timezone"):
        usage_diagnostics.parse_timestamp("2026-09-15T20:00:00", name="start")
