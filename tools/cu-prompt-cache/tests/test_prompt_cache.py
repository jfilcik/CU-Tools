"""Synthetic tests; no customer records, credentials, or live service dependencies."""

import copy
import importlib.util
import io
import json
import unittest
from pathlib import Path
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location(
    "prompt_cache", Path(__file__).resolve().parents[1] / "prompt_cache.py"
)
cache = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cache)
RUNS = [{"run_id": "ga-route-1", "request_id": "request-1", "operation_id": "operation-1"}]
MAPPING = {
    "table": "Telemetry", "timestamp": "Timestamp", "request_id": "RequestId",
    "operation_id": "OperationId", "client_request_id": "ClientRequestId",
    "span_name": "SpanName", "trace_id": "TraceId", "call_id": "SpanId",
    "attributes": "Attributes", "span_names": ["model_call"],
    "cache_metric_source": "normalized_zero_default",
    "fields": {
        "model": "model", "status": "status", "prompt_tokens": "usage.input",
        "completion_tokens": "usage.output", "cached_input_tokens": "usage.cached",
        "workflow": "workflow",
    },
}
SCHEMA = [
    {"ColumnName": MAPPING[role], "ColumnType": "datetime" if role == "timestamp" else "string"}
    for role in cache.COLUMNS
]
START, END = "2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z"
PRICES = {
    "model-a": {"input_per_million": "2", "cached_input_per_million": "1", "output_per_million": "8"},
    "model-b": {"input_per_million": "4", "cached_input_per_million": "1", "output_per_million": "16"},
}


def row(**overrides):
    return {
        "run_id": "ga-route-1", "request_id": "engine-request-1", "call_id": "trace-1:span-1",
        "timestamp": START, "model": "model-a", "status": "success",
        "prompt_tokens": 1000, "completion_tokens": 100, "cached_input_tokens": 500,
        "cache_metric_source": "provider_reported", **overrides,
    }


def kusto(rows):
    names = list(rows[0]) if rows else ["unused"]
    return {"Tables": [{
        "TableName": "Table_0", "Columns": [{"ColumnName": name} for name in names],
        "Rows": [[item[name] for name in names] for item in rows],
    }]}


class SummaryTests(unittest.TestCase):
    def test_weighted_ratio_fanout_and_mixed_models(self):
        result = cache.summarize([
            row(),
            row(call_id="trace-1:span-2", model="model-b", prompt_tokens=9000, cached_input_tokens=900),
        ], RUNS, PRICES)
        self.assertEqual(result["total"]["call_count"], 2)
        self.assertEqual(len(result["models"]), 2)
        self.assertEqual(len(result["requests"]), 1)
        self.assertEqual(result["total"]["cache_ratio"], 0.14)
        self.assertEqual(result["requests"][0]["cache_ratio"], 0.14)
        self.assertEqual(result["total"]["cost_estimate"]["known_cached_discount"], "0.0032")
        self.assertFalse(result["total"]["cost_estimate"]["customer_metered_savings_verified"])

    def test_duplicate_rows_do_not_double_bill(self):
        result = cache.summarize([row(), row()], RUNS)
        self.assertEqual(result["duplicate_rows_removed"], 1)
        self.assertEqual(result["total"]["prompt_tokens"], 1000)

    def test_conflicting_duplicate_is_error(self):
        with self.assertRaises(cache.TelemetryError):
            cache.summarize([row(), row(cached_input_tokens=501)], RUNS)

    def test_call_id_cannot_belong_to_two_requests_or_runs(self):
        for override in ({"request_id": "other"}, {"run_id": "other"}):
            with self.subTest(override=override), self.assertRaises(cache.TelemetryError):
                cache.summarize([row(), row(**override)], RUNS)

    def test_missing_cache_not_zero(self):
        result = cache.summarize([
            row(),
            row(call_id="trace-1:span-2", prompt_tokens=9000, cached_input_tokens=None),
        ], RUNS, PRICES)["total"]
        self.assertIsNone(result["cache_ratio"])
        self.assertIsNone(result["cached_input_tokens"])
        self.assertEqual(result["known_cached_input_tokens"], 500)
        self.assertEqual(result["known_cache_ratio"], 0.5)
        self.assertEqual(result["cache_metric_prompt_coverage"], 0.1)
        self.assertEqual(result["cache_ratio_lower_bound"], 0.05)
        self.assertEqual(result["cache_ratio_upper_bound"], 0.95)
        self.assertIsNone(result["cost_estimate"]["cache_adjusted"])

    def test_normalized_zero_is_unknown_but_preserved(self):
        result = cache.summarize([
            row(cached_input_tokens=0, cache_metric_source="normalized_zero_default")
        ], RUNS)
        self.assertIsNone(result["total"]["cached_input_tokens"])
        self.assertEqual(result["total"]["normalized_zero_calls"], 1)
        self.assertEqual(result["calls"][0]["reported_cached_input_tokens"], 0)

    def test_reported_zero_is_known_cache_miss(self):
        result = cache.summarize([row(cached_input_tokens=0)], RUNS)["total"]
        self.assertEqual(result["cache_ratio"], 0)
        self.assertTrue(result["cache_metrics_complete"])

    def test_zero_input_ratio_undefined(self):
        result = cache.summarize([row(prompt_tokens=0, cached_input_tokens=0)], RUNS)["total"]
        self.assertIsNone(result["cache_ratio"])
        self.assertEqual(result["cached_input_tokens"], 0)

    def test_failed_attempt_is_not_removed_or_counted_as_free(self):
        result = cache.summarize([
            row(),
            row(call_id="trace-1:span-2", status="failed", model=None,
                prompt_tokens=None, completion_tokens=None, cached_input_tokens=None),
        ], RUNS, PRICES)["total"]
        self.assertEqual(result["call_count"], 2)
        self.assertFalse(result["usage_complete"])
        self.assertIsNone(result["prompt_tokens"])
        self.assertIsNone(result["cache_ratio"])
        self.assertIsNone(result["cost_estimate"]["uncached_baseline"])
        self.assertIsNone(result["cost_estimate"]["cache_adjusted"])

    def test_invalid_and_overflow_tokens(self):
        for value in (True, -1, 1.5, 1000.0, "1.0", "1e3", float("inf"), float("nan"),
                      cache.MAX_INT + 1, "9" * 100):
            with self.subTest(value=value), self.assertRaises(cache.TelemetryError):
                cache.summarize([row(prompt_tokens=value)], RUNS)
        with self.assertRaises(cache.TelemetryError):
            cache.summarize([row(cached_input_tokens=1001)], RUNS)
        with self.assertRaises(cache.TelemetryError):
            cache.summarize([
                row(prompt_tokens=cache.MAX_INT),
                row(call_id="another", prompt_tokens=1, cached_input_tokens=0),
            ], RUNS)

    def test_numeric_integer_strings(self):
        result = cache.summarize([row(prompt_tokens="1000", cached_input_tokens="500")], RUNS)
        self.assertEqual(result["total"]["cache_ratio"], 0.5)

    def test_missing_metrics_ids_model_provenance_or_timestamp_fail(self):
        for field in ("run_id", "request_id", "call_id", "prompt_tokens", "completion_tokens",
                      "cached_input_tokens", "model", "cache_metric_source", "timestamp", "status"):
            item = row()
            item.pop(field)
            with self.subTest(field=field), self.assertRaises(cache.TelemetryError):
                cache.summarize([item], RUNS)
        with self.assertRaises(cache.TelemetryError):
            cache.summarize([row(call_id="trace:")], RUNS)

    def test_expected_runs_must_all_have_calls(self):
        extra = [{"run_id": "preview-route-1", "request_id": "request-2"}]
        with self.assertRaisesRegex(cache.TelemetryError, "preview-route-1"):
            cache.summarize([row()], RUNS + extra)
        with self.assertRaisesRegex(cache.TelemetryError, "empty results are not a cache miss"):
            cache.summarize([], RUNS)

    def test_one_run_can_have_multiple_engine_requests(self):
        result = cache.summarize([
            row(), row(call_id="other", request_id="engine-request-2"),
        ], RUNS)
        self.assertEqual(len(result["requests"]), 2)
        self.assertEqual(result["runs"][0]["call_count"], 2)

    def test_unknown_models_prices_and_nonfinite_prices_fail(self):
        with self.assertRaises(cache.TelemetryError):
            cache.summarize([row(model="model-c")], RUNS, PRICES)
        for value in ("NaN", "Infinity", float("inf"), -1, True, "1e200"):
            prices = copy.deepcopy(PRICES)
            prices["model-a"]["input_per_million"] = value
            with self.subTest(value=value), self.assertRaises(cache.TelemetryError):
                cache.summarize([row()], RUNS, prices)
        prices = copy.deepcopy(PRICES)
        prices["model-a"]["cached_input_per_million"] = 10
        with self.assertRaises(cache.TelemetryError):
            cache.summarize([row()], RUNS, prices)

    def test_metadata_only_output(self):
        result = cache.summarize([row(prompt="SECRET", response_headers="SECRET", content="SECRET")], RUNS)
        self.assertNotIn("SECRET", json.dumps(result))

    def test_runs_fail_ambiguous_missing_or_url_ids(self):
        for runs in (
            [], RUNS + RUNS,
            [{"run_id": "other", "request_id": "request-1"}] + RUNS,
            [{"run_id": "empty"}],
            [{"run_id": "x", "request_id": "https://example.test/?sig=secret"}],
        ):
            with self.subTest(runs=runs), self.assertRaises(cache.TelemetryError):
                cache.load_runs(runs)


class ExportAndQueryTests(unittest.TestCase):
    def test_kusto_export(self):
        self.assertEqual(cache.summarize(kusto([row()]), RUNS)["total"]["cache_ratio"], 0.5)

    def test_kusto_partial_failure_even_with_rows(self):
        payload = kusto([row()])
        payload["Tables"].append({
            "TableName": "Table_2",
            "Columns": [{"ColumnName": "Severity"}, {"ColumnName": "StatusCode"}],
            "Rows": [[2, 400]],
        })
        with self.assertRaises(cache.TelemetryError):
            cache.summarize(payload, RUNS)
        for payload in ({"error": {"message": "bad"}}, {"Tables": []}, {"HasErrors": True},
                        {"Exceptions": ["failed"]}, {"Tables": [{"Rows": []}]}):
            with self.subTest(payload=payload), self.assertRaises(cache.TelemetryError):
                cache.export_rows(payload)

    def test_query_is_bounded_schema_checked_and_metadata_only(self):
        query = cache.generate_query(MAPPING, SCHEMA, RUNS, START, END, 50)
        self.assertIn("OperationId in (ids)", query)
        self.assertIn("ClientRequestId in (ids)", query)
        self.assertIn("materialize(", query)
        self.assertIn("Timestamp >= start and Timestamp < end", query)
        self.assertIn('a["usage.cached"]', query)
        self.assertIn("take 51", query)
        self.assertNotIn("response_headers", query)
        self.assertNotIn("project *", query)
        self.assertNotIn("status ==", query)  # Failed/retried spans are not filtered out.

    def test_mapping_rejects_expressions_and_missing_columns(self):
        for role, value in (("table", "Telemetry; print 1"), ("timestamp", "todatetime(Timestamp)"),
                            ("call_id", "absent")):
            mapping = copy.deepcopy(MAPPING)
            mapping[role] = value
            with self.subTest(role=role), self.assertRaises(cache.TelemetryError):
                cache.generate_query(mapping, SCHEMA, RUNS, START, END)
        mapping = copy.deepcopy(MAPPING)
        mapping["fields"]["prompt_tokens"] = 'x"]; print "'
        with self.assertRaises(cache.TelemetryError):
            cache.generate_query(mapping, SCHEMA, RUNS, START, END)

    def test_all_severity_tables_are_schema_checked_and_queried(self):
        mapping = {**MAPPING, "additional_tables": ["TelemetryErrors"]}
        schema = {"schemas": {"Telemetry": SCHEMA, "TelemetryErrors": SCHEMA}}
        query = cache.generate_query(mapping, schema, RUNS, START, END)
        self.assertIn("union isfuzzy=false", query)
        self.assertIn("TelemetryErrors | where Timestamp >= start", query)
        with self.assertRaises(cache.TelemetryError):
            cache.generate_query(mapping, SCHEMA, RUNS, START, END)
        missing = {"schemas": {"Telemetry": SCHEMA}}
        with self.assertRaises(cache.TelemetryError):
            cache.generate_query(mapping, missing, RUNS, START, END)
        duplicate = {**MAPPING, "additional_tables": ["Telemetry"]}
        with self.assertRaises(cache.TelemetryError):
            cache.generate_query(duplicate, schema, RUNS, START, END)

    def test_fetch_cannot_silently_skip_error_table(self):
        mapping = {**MAPPING, "additional_tables": ["TelemetryErrors"]}
        with patch.object(cache, "azure_token", return_value="not-a-real-token"), \
             patch.object(cache, "execute_kusto", side_effect=[SCHEMA, cache.TelemetryError("access denied")]), \
             self.assertRaisesRegex(cache.TelemetryError, "access denied"):
            cache.fetch(mapping, RUNS, "https://example.kusto.windows.net", "Example", START, END)

    def test_invalid_windows_types_and_limits(self):
        for start, end in ((START, START), (END, START), (START, "2026-01-03T00:00:00Z"),
                           ("2026-01-01T00:00:00", END), ("not-a-date", END)):
            with self.subTest(start=start, end=end), self.assertRaises(cache.TelemetryError):
                cache.generate_query(MAPPING, SCHEMA, RUNS, start, end)
        schema = copy.deepcopy(SCHEMA)
        schema[0]["ColumnType"] = "string"
        with self.assertRaises(cache.TelemetryError):
            cache.generate_query(MAPPING, schema, RUNS, START, END)
        for cap in (0, 100001, True, 1.5):
            with self.subTest(cap=cap), self.assertRaises(cache.TelemetryError):
                cache.generate_query(MAPPING, SCHEMA, RUNS, START, END, cap)

    def test_cluster_url_rejects_credentials_ports_and_non_kusto(self):
        for url in ("http://x.kusto.windows.net", "https://evil.test",
                    "https://x.kusto.windows.net?sig=secret",
                    "https://user:secret@x.kusto.windows.net",
                    "https://x.kusto.windows.net:443", "https://x.kusto.windows.net/query",
                    "https://x.kusto.windows.net:bad", "https://[bad"):
            with self.subTest(url=url), self.assertRaises(cache.TelemetryError):
                cache.cluster_url(url)
        self.assertEqual(cache.cluster_url("https://example.kusto.windows.net/"),
                         "https://example.kusto.windows.net")

    def test_fetch_verifies_schema_and_rejects_truncation(self):
        with patch.object(cache, "azure_token", return_value="not-a-real-token"), \
             patch.object(cache, "execute_kusto", side_effect=[SCHEMA, [row()]]) as execute:
            result = cache.fetch(MAPPING, RUNS, "https://example.kusto.windows.net", "Example", START, END)
            self.assertEqual(len(result), 1)
            self.assertEqual(execute.call_args_list[0].args[2], "Telemetry | getschema")
        with patch.object(cache, "azure_token", return_value="not-a-real-token"), \
             patch.object(cache, "execute_kusto", side_effect=[SCHEMA, [row(), row()]]), \
             self.assertRaises(cache.TelemetryError):
            cache.fetch(MAPPING, RUNS, "https://example.kusto.windows.net", "Example", START, END, 1)

    def test_fetch_does_not_swallow_query_errors(self):
        with patch.object(cache, "azure_token", return_value="not-a-real-token"), \
             patch.object(cache, "execute_kusto", side_effect=cache.TelemetryError("query failed")), \
             self.assertRaisesRegex(cache.TelemetryError, "query failed"):
            cache.fetch(MAPPING, RUNS, "https://example.kusto.windows.net", "Example", START, END)

    def test_invalid_fetch_mapping_fails_before_authentication(self):
        with patch.object(cache, "azure_token") as authenticate, self.assertRaises(cache.TelemetryError):
            cache.fetch([], RUNS, "https://example.kusto.windows.net", "Example", START, END)
        authenticate.assert_not_called()

    def test_timestamp_conversion_overflow_is_explicit(self):
        with self.assertRaises(cache.TelemetryError):
            cache.timestamp("0001-01-01T00:00:00+14:00")

    def test_kusto_row_must_be_array(self):
        payload = kusto([{"x": 1}])
        payload["Tables"][0]["Rows"] = ["x"]
        with self.assertRaises(cache.TelemetryError):
            cache.export_rows(payload)


class RequestsFileTests(unittest.TestCase):
    def record(self, **overrides):
        return {
            "variant": "native-segment-classifier", "api_version": "2025-11-01",
            "phase": "same-document-repeat", "iteration": 1,
            "started_at": "2026-01-01T00:10:00Z",
            "completed_at": "2026-01-01T00:11:00Z",
            "operation_id": "operation-1",
            "response_headers": {"Apim-Request-Id": "request-1", "X-MS-Request-ID": "request-2"},
            **overrides,
        }

    def test_adapts_record_labels_ids_and_default_window(self):
        runs, start, end = cache.adapt_requests([self.record()])
        self.assertEqual(start, "2026-01-01T00:05:00+00:00")
        self.assertEqual(end, "2026-01-01T00:16:00+00:00")
        self.assertEqual(runs[0]["run_id"], "request-000001")
        self.assertEqual(runs[0]["request_index"], 0)
        self.assertEqual(runs[0]["request_id"], "request-1")
        self.assertEqual(runs[0]["correlation_ids"], ["request-2"])
        parsed = cache.load_runs(runs)["request-000001"]
        self.assertEqual(parsed["ids"], ["operation-1", "request-1", "request-2"])
        self.assertEqual(parsed["phase"], "same-document-repeat")
        self.assertEqual(parsed["iteration"], 1)

    def test_operation_only_and_header_only(self):
        runs, _, _ = cache.adapt_requests([self.record(response_headers={})], 0)
        self.assertEqual(runs[0]["operation_id"], "operation-1")
        runs, _, _ = cache.adapt_requests([self.record(operation_id=None)], 0)
        self.assertEqual(runs[0]["request_id"], "request-1")

    def test_ignores_content_usage_and_shared_client_correlation_headers(self):
        headers = {"Authorization": "SECRET", "x-ms-client-request-id": "shared",
                   "x-ms-correlation-request-id": "shared"}
        records = [
            self.record(response_headers=headers, sample="SECRET", result_file="SECRET",
                        usage={"cached_tokens": 123456}, infos={"LLMStats": "SECRET"}),
            self.record(operation_id="operation-2", response_headers=headers),
        ]
        runs, _, _ = cache.adapt_requests(records)
        text = json.dumps(runs)
        self.assertNotIn("SECRET", text)
        self.assertNotIn("123456", text)
        self.assertNotIn("shared", text)
        self.assertEqual(len(runs), 2)
        self.assertEqual(runs[1]["request_index"], 1)

    def test_missing_incomplete_reversed_and_invalid_records_fail(self):
        for record in (
            self.record(completed_at=None),
            self.record(started_at="2026-01-01T00:12:00Z"),
            self.record(operation_id=None, response_headers={}),
            self.record(response_headers={"apim-request-id": "https://example.test/?sig=SECRET"}),
            self.record(response_headers=[]),
            self.record(iteration=True),
            self.record(response_headers={"APIM-REQUEST-ID": "one", "apim-request-id": "two"}),
        ):
            with self.subTest(record=record), self.assertRaises(cache.TelemetryError):
                cache.adapt_requests([record])
        with self.assertRaises(cache.TelemetryError):
            cache.adapt_requests([])
        with self.assertRaises(cache.TelemetryError):
            cache.adapt_requests([self.record()], 3601)

    def test_shared_submission_ids_fail_instead_of_cross_joining(self):
        records = [self.record(), self.record(operation_id="operation-2")]
        with self.assertRaises(cache.TelemetryError):
            cache.adapt_requests(records)
        with self.assertRaises(cache.TelemetryError):
            cache.load_runs([{"run_id": "x", "correlation_ids": ["alias-only"]}])

    def test_generated_ids_and_labels_survive_summary(self):
        runs, _, _ = cache.adapt_requests([self.record()])
        result = cache.summarize([row(run_id="request-000001")], runs)
        self.assertEqual(result["runs"][0]["phase"], "same-document-repeat")
        self.assertEqual(result["runs"][0]["request_index"], 0)
        self.assertEqual(result["runs"][0]["variant"], "native-segment-classifier")

    def test_fetch_cli_infers_window_without_writing_files(self):
        with patch.object(cache, "read_json", side_effect=[[self.record()], MAPPING]), \
             patch.object(cache, "fetch", return_value=[row(run_id="request-000001")]) as fetch, \
             patch.object(cache, "write_json") as write, patch("sys.stdout", new_callable=io.StringIO):
            status = cache.main([
                "fetch", "--requests-file", "requests.json", "--mapping", "mapping.json",
                "--cluster", "https://example.kusto.windows.net", "--database", "Example",
                "--output", "output.json",
            ])
        self.assertEqual(status, 0)
        self.assertEqual(fetch.call_args.args[4], "2026-01-01T00:05:00+00:00")
        self.assertEqual(fetch.call_args.args[5], "2026-01-01T00:16:00+00:00")
        write.assert_called_once()

    def test_cli_rejects_one_bound_and_legacy_manifest_without_bounds(self):
        for args, data in (
            (["--requests-file", "requests.json", "--start", START], [self.record()]),
            (["--runs", "runs.json"], RUNS),
        ):
            with self.subTest(args=args), patch.object(cache, "read_json", return_value=data), \
                 patch.object(cache, "fetch") as fetch, patch("sys.stderr", new_callable=io.StringIO):
                status = cache.main([
                    "fetch", *args, "--mapping", "mapping.json",
                    "--cluster", "https://example.kusto.windows.net", "--database", "Example",
                    "--output", "output.json",
                ])
            self.assertEqual(status, 1)
            fetch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
