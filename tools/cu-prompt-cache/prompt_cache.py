#!/usr/bin/env python3
"""Correlate exported LLM spans with CU runs without collecting prompt content."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


MAX_INT = 2**63 - 1
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,127}\Z")
OPAQUE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}\Z")
ATTR_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_.-]{0,127}\Z")
TOKEN_FIELDS = ("prompt_tokens", "completion_tokens", "cached_input_tokens")
SOURCES = {"provider_reported", "normalized_zero_default"}
COLUMNS = (
    "timestamp", "request_id", "operation_id", "client_request_id",
    "span_name", "trace_id", "call_id", "attributes",
)
FIELDS = ("model", "status", *TOKEN_FIELDS, "workflow")


class TelemetryError(ValueError):
    """Invalid or incomplete telemetry, correlation, configuration, or query."""


def read_json(path: str | Path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise TelemetryError("Cannot read valid JSON input") from exc


def write_json(path: str | Path, value: Any) -> None:
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def checked_name(value: Any, kind: str = "identifier") -> str:
    pattern = {"identifier": IDENTIFIER, "id": OPAQUE_ID, "attribute": ATTR_KEY}[kind]
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise TelemetryError(f"Invalid {kind}; use a plain name, not a URL or expression")
    return value


def timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise TelemetryError("Timestamp must be an ISO-8601 string with a timezone")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TelemetryError("Invalid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise TelemetryError("Timestamp must include a timezone")
    try:
        return parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError) as exc:
        raise TelemetryError("Timestamp is outside the supported UTC range") from exc


def token(value: Any, name: str, nullable: bool = False) -> int | None:
    if value is None and nullable:
        return None
    if isinstance(value, str) and re.fullmatch(r"[0-9]{1,19}", value):
        value = int(value)
    if type(value) is not int or not 0 <= value <= MAX_INT:
        raise TelemetryError(f"{name} must be a nonnegative signed-64-bit integer")
    return value


def total(values):
    return token(sum(values), "aggregate token count")


def load_runs(data: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(data, list) or not data or len(data) > 100:
        raise TelemetryError("Runs must be a nonempty JSON array of at most 100 records")
    runs, owners = {}, {}
    for item in data:
        if not isinstance(item, dict):
            raise TelemetryError("Each run must be an object")
        run_id = checked_name(item.get("run_id"), "id")
        if run_id in runs:
            raise TelemetryError("Duplicate run_id")
        if not item.get("request_id") and not item.get("operation_id"):
            raise TelemetryError("Each run needs request_id or operation_id")
        extra_ids = item.get("correlation_ids", [])
        if not isinstance(extra_ids, list) or len(extra_ids) > 8:
            raise TelemetryError("correlation_ids must be an array of at most eight IDs")
        ids = []
        for value in (item.get("request_id"), item.get("operation_id"), *extra_ids):
            if value:
                identity = checked_name(value, "id")
                if identity in owners and owners[identity] != run_id:
                    raise TelemetryError("A correlation ID belongs to multiple runs")
                owners[identity] = run_id
                ids.append(identity)
        if not ids:
            raise TelemetryError("Each run needs request_id or operation_id")
        runs[run_id] = {
            "run_id": run_id,
            "ids": sorted(set(ids)),
            **{key: checked_name(item[key], "id")
               for key in ("api_version", "variant", "phase") if item.get(key)},
        }
        for field in ("request_index", "iteration"):
            if field in item:
                runs[run_id][field] = token(item[field], field)
    return runs


def adapt_requests(data: Any, padding_seconds: int = 300) -> tuple[list[dict], str, str]:
    """Adapt completed runner records, ignoring document, payload, and usage fields."""
    if not isinstance(data, list) or not data or len(data) > 100:
        raise TelemetryError("Requests file must contain 1-100 completed request records")
    if type(padding_seconds) is not int or not 0 <= padding_seconds <= 3600:
        raise TelemetryError("Window padding must be between 0 and 3600 seconds")
    runs, starts, ends = [], [], []
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise TelemetryError("Each request record must be an object")
        if not item.get("started_at") or not item.get("completed_at"):
            raise TelemetryError("Requests file contains an incomplete record; wait for completion")
        start, end = timestamp(item["started_at"]), timestamp(item["completed_at"])
        if end < start:
            raise TelemetryError("Request completed_at precedes started_at")
        starts.append(start)
        ends.append(end)
        headers = item.get("response_headers", {})
        if headers is None:
            headers = {}
        if not isinstance(headers, dict):
            raise TelemetryError("response_headers must be an object")
        request_headers = {}
        for key, value in headers.items():
            if isinstance(key, str) and key.lower() in {"apim-request-id", "x-ms-request-id"} and value:
                name = key.lower()
                identity = checked_name(value, "id")
                if name in request_headers and request_headers[name] != identity:
                    raise TelemetryError("Conflicting case-insensitive request headers")
                request_headers[name] = identity
        header_ids = list(dict.fromkeys(
            request_headers[key] for key in ("apim-request-id", "x-ms-request-id")
            if key in request_headers
        ))
        run = {
            "run_id": item.get("run_id") or f"request-{index + 1:06d}",
            "request_index": index,
            **{key: item[key] for key in ("api_version", "variant", "phase", "iteration") if key in item},
        }
        if item.get("operation_id"):
            run["operation_id"] = checked_name(item["operation_id"], "id")
        if header_ids:
            run["request_id"] = header_ids[0]
            run["correlation_ids"] = header_ids[1:]
        if not run.get("operation_id") and not run.get("request_id"):
            raise TelemetryError("Request record lacks operation_id and submit request-ID headers")
        runs.append(run)
    load_runs(runs)
    try:
        start = min(starts) - timedelta(seconds=padding_seconds)
        end = max(ends) + timedelta(seconds=padding_seconds)
    except OverflowError as exc:
        raise TelemetryError("Padded request window is outside the supported UTC range") from exc
    return runs, start.isoformat(), end.isoformat()


def export_rows(payload: Any) -> list[dict[str, Any]]:
    """Read the primary table of a Kusto v1 response, checking partial failures."""
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        raise TelemetryError("Expected an array or Kusto v1 Tables response")
    if any(payload.get(key) for key in ("error", "Errors", "Exceptions", "OneApiErrors")):
        raise TelemetryError("Kusto returned a query error")
    if payload.get("HasErrors"):
        raise TelemetryError("Kusto reported partial query failure")
    tables = payload.get("Tables")
    if not isinstance(tables, list) or not tables:
        raise TelemetryError("Missing Kusto result tables")
    decoded = []
    for table in tables:
        try:
            if not isinstance(table, dict):
                raise TelemetryError("Malformed Kusto table")
            names = [column["ColumnName"] for column in table["Columns"]]
            if len(names) != len(set(names)):
                raise TelemetryError("Duplicate result column names")
            rows = []
            for row in table["Rows"]:
                if not isinstance(row, list) or len(row) != len(names):
                    raise TelemetryError("Kusto row does not match columns")
                rows.append(dict(zip(names, row)))
            decoded.append((table.get("TableName"), rows))
            if "Severity" in names:
                for row in rows:
                    severity = row.get("Severity")
                    if severity is not None and int(severity) <= 2:
                        raise TelemetryError("Kusto returned a partial query failure")
                    if row.get("SeverityName") in {"Error", "Fatal"}:
                        raise TelemetryError("Kusto returned a query failure")
                    if row.get("StatusCode") not in (None, 0, "0"):
                        raise TelemetryError("Kusto returned an unsuccessful query status")
        except (KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, TelemetryError):
                raise
            raise TelemetryError("Malformed Kusto response") from exc
    # Kusto v1 puts the query result first; subsequent tables contain statistics.
    if decoded[0][0] not in (None, "Table_0", "PrimaryResult"):
        raise TelemetryError("Unrecognized primary Kusto table")
    return decoded[0][1]


def normalize_rows(payload: Any, runs: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    rows = export_rows(payload)
    if not rows:
        raise TelemetryError("No LLM calls returned; empty results are not a cache miss")
    unique, duplicates, found = {}, 0, set()
    for raw in rows:
        if not isinstance(raw, dict):
            raise TelemetryError("Each telemetry row must be an object")
        run_id = checked_name(raw.get("run_id"), "id")
        if run_id not in runs:
            raise TelemetryError("Telemetry contains an unexpected run_id")
        request_id = checked_name(raw.get("request_id"), "id")
        call_id = checked_name(raw.get("call_id"), "id")
        if call_id.endswith(":"):
            raise TelemetryError("Call identity is missing its span ID")
        status = raw.get("status")
        if status not in {"success", "failed", "retry", "unknown"}:
            raise TelemetryError("Call status must be success, failed, retry, or unknown")
        model = raw.get("model") or None
        if model is not None:
            checked_name(model, "id")
        if status == "success" and model is None:
            raise TelemetryError("Successful call is missing model identity")
        source = raw.get("cache_metric_source")
        if source not in SOURCES:
            raise TelemetryError("Declare provider_reported or normalized_zero_default provenance")
        for field in TOKEN_FIELDS:
            if field not in raw:
                raise TelemetryError(f"Missing {field}; use explicit null for unavailable metrics")
        prompt = token(raw["prompt_tokens"], "prompt_tokens", status != "success")
        completion = token(raw["completion_tokens"], "completion_tokens", status != "success")
        cached = token(raw["cached_input_tokens"], "cached_input_tokens", True)
        if (prompt is None) != (completion is None):
            raise TelemetryError("Prompt/completion counts must both be available or both null")
        if cached is not None and (prompt is None or cached > prompt):
            raise TelemetryError("Cached input exceeds total prompt or lacks total prompt")
        if cached is None:
            state = "unknown"
        elif source == "normalized_zero_default" and cached == 0:
            state = "normalized_zero"
        else:
            state = "known"
        known_cached = cached if state == "known" else None
        call = {
            "run_id": run_id, "request_id": request_id, "call_id": call_id,
            "timestamp": timestamp(raw.get("timestamp")).isoformat(),
            "model": model, "status": status,
            "prompt_tokens": prompt, "completion_tokens": completion,
            "reported_cached_input_tokens": cached,
            "cached_input_tokens": known_cached, "cache_metric_state": state,
            "cache_metric_source": source,
            "cache_ratio": known_cached / prompt if known_cached is not None and prompt else None,
        }
        if raw.get("workflow"):
            call["workflow"] = checked_name(raw["workflow"], "id")
        if call_id in unique:
            if unique[call_id] != call:
                raise TelemetryError("Conflicting duplicate call_id; cannot safely deduplicate")
            duplicates += 1
        else:
            unique[call_id] = call
        found.add(run_id)
    if found != set(runs):
        missing = ", ".join(sorted(set(runs) - found))
        raise TelemetryError(
            "One or more expected runs have no correlated LLM calls: "
            f"{missing}. Check ingestion lag, time bounds, and correlation; missing telemetry is not zero usage."
        )
    return list(unique.values()), duplicates


def load_prices(data: Any) -> dict[str, dict[str, Decimal]]:
    if not isinstance(data, dict) or not data:
        raise TelemetryError("Prices must be an object keyed by exact model identity")
    prices = {}
    for model, rates in data.items():
        checked_name(model, "id")
        if not isinstance(rates, dict):
            raise TelemetryError("Each model needs explicit input, cached_input, and output prices")
        converted = {}
        for field in ("input_per_million", "cached_input_per_million", "output_per_million"):
            value = rates.get(field)
            if isinstance(value, bool) or value is None:
                raise TelemetryError("Missing or invalid model price")
            try:
                number = Decimal(str(value))
            except InvalidOperation as exc:
                raise TelemetryError("Invalid model price") from exc
            if not number.is_finite() or not 0 <= number <= Decimal("1e12"):
                raise TelemetryError("Model prices must be finite, nonnegative, and at most 1e12")
            converted[field] = number
        if converted["cached_input_per_million"] > converted["input_per_million"]:
            raise TelemetryError("Cached-input price must not exceed normal input price")
        prices[model] = converted
    return prices


def cost_summary(calls: list[dict[str, Any]], prices: dict[str, dict[str, Decimal]]) -> dict[str, Any]:
    baseline = Decimal(0)
    discount = Decimal(0)
    usage_complete = all(call["prompt_tokens"] is not None for call in calls)
    cache_complete = all(call["cached_input_tokens"] is not None for call in calls)
    for call in calls:
        if call["prompt_tokens"] is None:
            continue
        if call["model"] not in prices:
            raise TelemetryError("No explicit prices for an observed model")
        rates = prices[call["model"]]
        baseline += (
            call["prompt_tokens"] * rates["input_per_million"]
            + call["completion_tokens"] * rates["output_per_million"]
        ) / Decimal(1_000_000)
        if call["cached_input_tokens"] is not None:
            discount += call["cached_input_tokens"] * (
                rates["input_per_million"] - rates["cached_input_per_million"]
            ) / Decimal(1_000_000)
    return {
        "basis": "explicit_model_token_prices_not_invoice",
        "known_usage_uncached_baseline": str(baseline),
        "uncached_baseline": str(baseline) if usage_complete else None,
        "known_cached_discount": str(discount),
        "cache_adjusted": str(baseline - discount) if usage_complete and cache_complete else None,
        "customer_metered_savings_verified": False,
    }


def aggregate(calls: list[dict[str, Any]], prices=None) -> dict[str, Any]:
    known_usage = [call for call in calls if call["prompt_tokens"] is not None]
    known_cache = [call for call in calls if call["cached_input_tokens"] is not None]
    prompt = total(call["prompt_tokens"] for call in known_usage)
    completion = total(call["completion_tokens"] for call in known_usage)
    cache = total(call["cached_input_tokens"] for call in known_cache)
    covered_prompt = total(call["prompt_tokens"] for call in known_cache)
    usage_complete = len(known_usage) == len(calls)
    cache_complete = len(known_cache) == len(calls)
    result = {
        "call_count": len(calls),
        "successful_calls": sum(call["status"] == "success" for call in calls),
        "usage_complete": usage_complete,
        "cache_metrics_complete": cache_complete,
        "known_prompt_tokens": prompt,
        "known_completion_tokens": completion,
        "prompt_tokens": prompt if usage_complete else None,
        "completion_tokens": completion if usage_complete else None,
        "known_cached_input_tokens": cache,
        "cached_input_tokens": cache if cache_complete else None,
        "cache_metric_present_calls": sum(call["reported_cached_input_tokens"] is not None for call in calls),
        "cache_metric_known_calls": len(known_cache),
        "normalized_zero_calls": sum(call["cache_metric_state"] == "normalized_zero" for call in calls),
        "unknown_cache_calls": len(calls) - len(known_cache),
        "known_cache_prompt_tokens": covered_prompt,
        "cache_metric_prompt_coverage": covered_prompt / prompt if usage_complete and prompt else None,
        "cache_ratio": cache / prompt if cache_complete and usage_complete and prompt else None,
        "cache_ratio_lower_bound": cache / prompt if usage_complete and prompt else None,
        "cache_ratio_upper_bound": (cache + prompt - covered_prompt) / prompt if usage_complete and prompt else None,
        "known_cache_ratio": cache / covered_prompt if covered_prompt else None,
    }
    if prices is not None:
        result["cost_estimate"] = cost_summary(calls, prices)
    return result


def summarize(payload: Any, run_data: Any, price_data: Any = None) -> dict[str, Any]:
    runs = load_runs(run_data)
    calls, duplicates = normalize_rows(payload, runs)
    prices = load_prices(price_data) if price_data is not None else None
    request_groups, run_groups, model_groups = defaultdict(list), defaultdict(list), defaultdict(list)
    for call in calls:
        request_groups[(call["run_id"], call["request_id"])].append(call)
        run_groups[call["run_id"]].append(call)
        model_groups[call["model"]].append(call)
    return {
        "format_version": 1,
        "scope": "observed_correlated_llm_spans_only",
        "warnings": [
            "Export completeness, provider-internal retries, and actual billing are not inferred.",
            "A missing metric is not zero; normalized zero may mean a missing provider metric.",
            "Model-token estimates exclude page, contextualization, and other CU charges.",
        ],
        "duplicate_rows_removed": duplicates,
        "total": aggregate(calls, prices),
        "models": [{"model": model, **aggregate(group, prices)}
                   for model, group in model_groups.items()],
        "runs": [{**{k: v for k, v in runs[run_id].items() if k != "ids"}, **aggregate(group, prices)}
                 for run_id, group in run_groups.items()],
        "requests": [{"run_id": run_id, "request_id": request_id, **aggregate(group, prices)}
                     for (run_id, request_id), group in request_groups.items()],
        "calls": sorted(calls, key=lambda call: (call["run_id"], call["timestamp"], call["call_id"])),
    }


def table_names(mapping: Any) -> list[str]:
    if not isinstance(mapping, dict):
        raise TelemetryError("Mapping must be an object")
    additional = mapping.get("additional_tables", [])
    if not isinstance(additional, list) or len(additional) > 4:
        raise TelemetryError("At most four additional telemetry tables are supported")
    names = [checked_name(mapping.get("table")), *[checked_name(name) for name in additional]]
    if len(names) != len(set(names)):
        raise TelemetryError("Duplicate telemetry table")
    return names


def validate_mapping(mapping: Any, schema: Any) -> None:
    tables = table_names(mapping)
    if mapping.get("cache_metric_source") not in SOURCES:
        raise TelemetryError("Mapping must declare cache metric provenance")
    schemas = schema.get("schemas") if isinstance(schema, dict) else None
    if schemas is None:
        if len(tables) != 1:
            raise TelemetryError("Multiple tables require a schemas object keyed by table name")
        schemas = {tables[0]: schema}
    if not isinstance(schemas, dict):
        raise TelemetryError("schemas must be an object keyed by table name")
    for table in tables:
        if table not in schemas:
            raise TelemetryError("Missing schema for a configured telemetry table")
        rows = export_rows(schemas[table])
        types = {}
        for row in rows:
            if not isinstance(row, dict) or "ColumnName" not in row or "ColumnType" not in row:
                raise TelemetryError("Schema must be an actual getschema export")
            name = row["ColumnName"]
            if name in types:
                raise TelemetryError("Duplicate schema column")
            types[name] = row["ColumnType"]
        for role in COLUMNS:
            name = checked_name(mapping.get(role))
            expected = {"datetime"} if role == "timestamp" else {"string"}
            if role == "attributes":
                expected.add("dynamic")
            if types.get(name) not in expected:
                raise TelemetryError(f"Schema does not support mapped {role} column/type")
    fields = mapping.get("fields")
    if not isinstance(fields, dict):
        raise TelemetryError("Mapping must define fields")
    for role in FIELDS:
        checked_name(fields.get(role), "attribute")
    names = mapping.get("span_names")
    if not isinstance(names, list) or not names or len(names) > 10:
        raise TelemetryError("Mapping needs 1-10 observed LLM span names")
    for name in names:
        checked_name(name, "id")


def generate_query(mapping: dict, schema: Any, run_data: Any, start: str, end: str, max_rows: int = 10000) -> str:
    validate_mapping(mapping, schema)
    runs = load_runs(run_data)
    start_time, end_time = timestamp(start), timestamp(end)
    if not start_time < end_time or end_time - start_time > timedelta(days=1):
        raise TelemetryError("Query window must be positive and no longer than 24 hours")
    if type(max_rows) is not int or not 1 <= max_rows <= 100000:
        raise TelemetryError("max_rows must be between 1 and 100000")
    q = json.dumps
    time = mapping["timestamp"]
    request = mapping["request_id"]
    identity_columns = [mapping[key] for key in ("request_id", "operation_id", "client_request_id")]
    values = ",\n    ".join(
        f"{q(run_id)}, {q(identity)}" for run_id, run in runs.items() for identity in run["ids"]
    )
    filters = " or ".join(f"{column} in (ids)" for column in identity_columns)
    span_names = ", ".join(q(name) for name in mapping["span_names"])
    fields = mapping["fields"]
    def attribute(name: str) -> str:
        return f"a[{q(fields[name])}]"

    source_columns = ", ".join(dict.fromkeys(mapping[role] for role in COLUMNS))
    branches = ",\n        ".join(
        f"({table} | where {time} >= start and {time} < end | project {source_columns})"
        for table in table_names(mapping)
    )
    return f"""// Metadata only. Generated from an explicitly supplied, schema-checked mapping.
let start = datetime({start_time.isoformat()});
let end = datetime({end_time.isoformat()});
let logs = () {{
    union isfuzzy=false
        {branches}
}};
let requested = datatable(run_id:string, external_id:string) [
    {values}
];
let ids = requested | project external_id;
let anchors = materialize(
    logs()
    | where {filters}
    | project request_id={request}, aliases=pack_array({", ".join(identity_columns)})
    | where isnotempty(request_id)
    | mv-expand external_id=aliases to typeof(string)
    | join kind=inner (requested) on external_id
    | distinct request_id, run_id
);
logs()
| where {request} in (anchors | project request_id)
| where {mapping["span_name"]} in ({span_names})
| extend a=parse_json({mapping["attributes"]})
| project timestamp={time}, request_id={request},
    call_id=strcat({mapping["trace_id"]}, ":", {mapping["call_id"]}),
    model=tostring({attribute("model")}),
    status=iff(isempty(tostring({attribute("status")})), "unknown", tostring({attribute("status")})),
    prompt_tokens={attribute("prompt_tokens")},
    completion_tokens={attribute("completion_tokens")},
    cached_input_tokens={attribute("cached_input_tokens")},
    cache_metric_source={q(mapping["cache_metric_source"])},
    workflow=tostring({attribute("workflow")})
| join kind=inner (anchors) on request_id
| project-away request_id1
| take {max_rows + 1}
"""


def cluster_url(value: str) -> str:
    try:
        parsed = urllib.parse.urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise TelemetryError("Invalid Kusto cluster URL") from exc
    if (parsed.scheme != "https" or not parsed.hostname
            or not parsed.hostname.endswith(".kusto.windows.net")
            or parsed.username or parsed.password or port
            or parsed.query or parsed.fragment or parsed.path not in ("", "/")):
        raise TelemetryError("Use an HTTPS Azure Kusto cluster root, without credentials or query")
    return f"https://{parsed.hostname}"


def azure_token(cluster: str) -> str:
    az = shutil.which("az")
    if not az:
        raise TelemetryError("Azure CLI is missing; use offline exported telemetry")
    result = subprocess.run(
        [az, "account", "get-access-token", "--resource", cluster, "--output", "json", "--only-show-errors"],
        capture_output=True, text=True, timeout=90,
    )
    if result.returncode:
        raise TelemetryError("Existing Azure authentication failed; no login or permission change attempted")
    try:
        value = json.loads(result.stdout)["accessToken"]
    except (ValueError, KeyError) as exc:
        raise TelemetryError("Azure CLI returned no usable access token") from exc
    if not isinstance(value, str) or not value:
        raise TelemetryError("Azure CLI returned an empty access token")
    return value


def execute_kusto(cluster: str, database: str, query: str, access_token: str) -> list[dict[str, Any]]:
    request = urllib.request.Request(
        cluster + "/v1/rest/query",
        data=json.dumps({"db": database, "csl": query}).encode(),
        headers={"Authorization": "Bearer " + access_token, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            raw = response.read(32 * 1024 * 1024 + 1)
        if len(raw) > 32 * 1024 * 1024:
            raise TelemetryError("Query response exceeds 32 MiB; narrow the window/IDs")
        payload = json.loads(raw)
    except urllib.error.HTTPError as exc:
        raise TelemetryError(f"Kusto HTTP {exc.code}; no retry or access workaround attempted") from None
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise TelemetryError("Kusto transport or JSON response failed") from None
    return export_rows(payload)


def fetch(
    mapping: dict, run_data: Any, cluster: str, database: str,
    start: str, end: str, max_rows: int = 10000,
) -> list[dict[str, Any]]:
    endpoint = cluster_url(cluster)
    checked_name(database)
    # Validate caller-controlled query identifiers before even requesting a token.
    tables = table_names(mapping)
    load_runs(run_data)
    access_token = azure_token(endpoint)
    schema = {"schemas": {
        table: execute_kusto(endpoint, database, f"{table} | getschema", access_token)
        for table in tables
    }}
    query = generate_query(mapping, schema, run_data, start, end, max_rows)
    rows = execute_kusto(endpoint, database, query, access_token)
    if len(rows) > max_rows:
        raise TelemetryError("Row limit exceeded; export may be truncated. Narrow the query")
    summarize(rows, run_data)
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    summary = commands.add_parser("summarize", help="Validate and summarize exported metadata")
    summary.add_argument("--input", required=True)
    summary.add_argument("--prices")
    summary.add_argument("--output", required=True)
    inputs = summary.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--runs")
    inputs.add_argument("--requests-file")
    for name in ("query", "fetch"):
        command = commands.add_parser(name, help=f"{name.title()} a bounded metadata-only Kusto query")
        command.add_argument("--mapping", required=True)
        inputs = command.add_mutually_exclusive_group(required=True)
        inputs.add_argument("--runs")
        inputs.add_argument("--requests-file")
        command.add_argument("--start")
        command.add_argument("--end")
        command.add_argument("--window-padding-seconds", type=int, default=300)
        command.add_argument("--max-rows", type=int, default=10000)
        command.add_argument("--output", required=True)
        if name == "query":
            command.add_argument("--schema", required=True)
        else:
            command.add_argument("--cluster", required=True)
            command.add_argument("--database", required=True)
    args = parser.parse_args(argv)
    try:
        inferred_start = inferred_end = None
        if args.requests_file:
            runs, inferred_start, inferred_end = adapt_requests(
                read_json(args.requests_file), getattr(args, "window_padding_seconds", 300),
            )
        else:
            runs = read_json(args.runs)
        if args.command == "summarize":
            result = summarize(read_json(args.input), runs, read_json(args.prices) if args.prices else None)
            write_json(args.output, result)
        else:
            if bool(args.start) != bool(args.end):
                raise TelemetryError("Provide both --start and --end, or neither")
            start, end = args.start or inferred_start, args.end or inferred_end
            if start is None or end is None:
                raise TelemetryError("--runs requires explicit --start and --end")
            mapping = read_json(args.mapping)
            if args.command == "query":
                query = generate_query(mapping, read_json(args.schema), runs, start, end, args.max_rows)
                Path(args.output).write_text(query, encoding="utf-8")
            else:
                rows = fetch(mapping, runs, args.cluster, args.database, start, end, args.max_rows)
                write_json(args.output, rows)
        print("Validated output written.")
        return 0
    except (TelemetryError, OSError, subprocess.TimeoutExpired) as exc:
        message = str(exc) if isinstance(exc, TelemetryError) else "File, process, or timeout error"
        print(f"Error: {message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
