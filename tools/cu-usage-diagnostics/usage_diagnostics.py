#!/usr/bin/env python3
"""Summarize AzureOpenAIRequestUsage diagnostic logs from Azure Storage."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from azure.core.exceptions import AzureError, ClientAuthenticationError, ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient


CONTAINER_NAME = "insights-logs-azureopenairequestusage"
MAX_DOWNLOAD_BYTES = 32 * 1024 * 1024


class UsageDiagnosticsError(ValueError):
    """Validation, parsing, or Azure access failure."""


@dataclass(frozen=True)
class DiagnosticRecord:
    """Normalized token usage record from one JSONL line."""

    enqueue_time: datetime
    correlation_id: str | None
    model_deployment_name: str | None
    model_name: str | None
    model_version: str | None
    prompt_tokens: int
    cached_tokens: int
    generated_tokens: int
    source_blob: str

    @property
    def model_key(self) -> str:
        deployment = self.model_deployment_name or "(unknown-deployment)"
        name = self.model_name or "(unknown-model)"
        version = self.model_version or "(unknown-version)"
        return f"{deployment} | {name} | {version}"


def parse_timestamp(value: Any, *, name: str, assume_utc_if_naive: bool = False) -> datetime:
    if not isinstance(value, str):
        raise UsageDiagnosticsError(f"{name} must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise UsageDiagnosticsError(f"Invalid {name}: {value!r}") from exc
    if parsed.tzinfo is None:
        if not assume_utc_if_naive:
            raise UsageDiagnosticsError(f"{name} must include a timezone")
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def parse_positive_int_csv(value: str | None) -> list[int] | None:
    if value is None:
        return None
    parts = [part.strip() for part in value.split(",")]
    if not parts or any(not part for part in parts):
        raise UsageDiagnosticsError("--request-call-counts must be a comma-separated list of integers")
    counts = []
    for part in parts:
        try:
            count = int(part)
        except ValueError as exc:
            raise UsageDiagnosticsError(f"Invalid request call count: {part!r}") from exc
        if count <= 0:
            raise UsageDiagnosticsError("Request call counts must all be positive integers")
        counts.append(count)
    return counts


def hour_floor(moment: datetime) -> datetime:
    return moment.replace(minute=0, second=0, microsecond=0)


def iter_hours(start: datetime, end: datetime) -> Iterable[datetime]:
    current = hour_floor(start)
    while current < end:
        yield current
        current += timedelta(hours=1)


def normalize_resource_id(resource_id: str) -> str:
    value = resource_id.strip()
    if not value.startswith("/subscriptions/"):
        raise UsageDiagnosticsError("resource_id must start with /subscriptions/")
    return value


def blob_name_for_hour(resource_id: str, hour: datetime) -> str:
    normalized = normalize_resource_id(resource_id).upper()
    return (
        f"resourceId={normalized}/"
        f"y={hour.year:04d}/m={hour.month:02d}/d={hour.day:02d}/"
        f"h={hour.hour:02d}/m=00/PT1H.json"
    )


def parse_token_array(value: Any, *, field_name: str, context: str) -> int:
    if not isinstance(value, list):
        raise UsageDiagnosticsError(f"{context}: {field_name} must be an array")
    total = 0
    for item in value:
        if isinstance(item, str):
            if not item.isdigit():
                raise UsageDiagnosticsError(f"{context}: {field_name} contains a non-integer string")
            item = int(item)
        if type(item) is not int or item < 0:
            raise UsageDiagnosticsError(f"{context}: {field_name} must contain nonnegative integers")
        total += item
    return total


def parse_diagnostic_line(line: str, *, source_blob: str, line_number: int) -> DiagnosticRecord:
    context = f"{source_blob} line {line_number}"
    try:
        payload = json.loads(line)
    except ValueError as exc:
        raise UsageDiagnosticsError(f"{context}: invalid JSON") from exc
    if not isinstance(payload, dict):
        raise UsageDiagnosticsError(f"{context}: expected an object")
    try:
        enqueue_time = parse_timestamp(
            payload["EnqueueTime"], name="EnqueueTime", assume_utc_if_naive=True
        )
    except KeyError as exc:
        raise UsageDiagnosticsError(f"{context}: missing EnqueueTime") from exc
    properties = payload.get("properties")
    if isinstance(properties, str):
        try:
            properties = json.loads(properties)
        except ValueError as exc:
            raise UsageDiagnosticsError(f"{context}: properties is not valid nested JSON") from exc
    if not isinstance(properties, dict):
        raise UsageDiagnosticsError(f"{context}: properties must decode to an object")
    prompt_tokens = parse_token_array(properties.get("promptTokens"), field_name="promptTokens", context=context)
    cached_tokens = parse_token_array(properties.get("cachedTokens"), field_name="cachedTokens", context=context)
    generated_tokens = parse_token_array(
        properties.get("generatedTokens"), field_name="generatedTokens", context=context
    )
    if cached_tokens > prompt_tokens:
        raise UsageDiagnosticsError(f"{context}: cachedTokens cannot exceed promptTokens")
    correlation_id = payload.get("correlationId")
    if correlation_id is not None and not isinstance(correlation_id, str):
        raise UsageDiagnosticsError(f"{context}: correlationId must be a string when present")
    return DiagnosticRecord(
        enqueue_time=enqueue_time,
        correlation_id=correlation_id,
        model_deployment_name=string_or_none(properties.get("modelDeploymentName")),
        model_name=string_or_none(properties.get("modelName")),
        model_version=string_or_none(properties.get("modelVersion")),
        prompt_tokens=prompt_tokens,
        cached_tokens=cached_tokens,
        generated_tokens=generated_tokens,
        source_blob=source_blob,
    )


def string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise UsageDiagnosticsError("Expected a string model field when present")
    return value


def parse_blob_text(blob_name: str, blob_text: str, *, start: datetime, end: datetime) -> list[DiagnosticRecord]:
    records = []
    for index, raw_line in enumerate(blob_text.splitlines(), start=1):
        if not raw_line.strip():
            continue
        record = parse_diagnostic_line(raw_line, source_blob=blob_name, line_number=index)
        if start <= record.enqueue_time < end:
            records.append(record)
    return records


def aggregate_records(records: Iterable[DiagnosticRecord]) -> dict[str, Any]:
    items = list(records)
    prompt_total = sum(item.prompt_tokens for item in items)
    cached_total = sum(item.cached_tokens for item in items)
    generated_total = sum(item.generated_tokens for item in items)
    return {
        "record_count": len(items),
        "prompt_tokens": prompt_total,
        "cached_tokens": cached_total,
        "generated_tokens": generated_total,
        "cache_hit_ratio": round(cached_total / prompt_total, 6) if prompt_total else None,
    }


def summarize_by_model(records: Iterable[DiagnosticRecord]) -> list[dict[str, Any]]:
    grouped: dict[str, list[DiagnosticRecord]] = defaultdict(list)
    for record in records:
        grouped[record.model_key].append(record)
    summaries = []
    for key, items in sorted(grouped.items()):
        sample = items[0]
        summaries.append({
            "model_key": key,
            "modelDeploymentName": sample.model_deployment_name,
            "modelName": sample.model_name,
            "modelVersion": sample.model_version,
            **aggregate_records(items),
        })
    return summaries


def correlate_requests(records: list[DiagnosticRecord], request_call_counts: list[int]) -> tuple[list[dict[str, Any]], list[str], list[DiagnosticRecord]]:
    sorted_records = sorted(
        records,
        key=lambda item: (item.enqueue_time, item.correlation_id or "", item.model_key, item.source_blob),
    )
    expected_total = sum(request_call_counts)
    available = len(sorted_records)
    if expected_total > available:
        raise UsageDiagnosticsError(
            f"Requested {expected_total} correlated model calls but only {available} diagnostic records are available"
        )
    warnings = []
    if expected_total != available:
        warnings.append(
            f"Requested {expected_total} correlated model calls but {available} records were available; "
            f"{available - expected_total} record(s) remain unassigned"
        )
    groups = []
    offset = 0
    for request_index, count in enumerate(request_call_counts, start=1):
        chunk = sorted_records[offset:offset + count]
        offset += count
        groups.append({
            "request_index": request_index,
            "expected_call_count": count,
            "first_enqueue_time": chunk[0].enqueue_time.isoformat() if chunk else None,
            "last_enqueue_time": chunk[-1].enqueue_time.isoformat() if chunk else None,
            **aggregate_records(chunk),
            "models": summarize_by_model(chunk),
        })
    return groups, warnings, sorted_records[offset:]


def create_blob_service_client(storage_account: str) -> BlobServiceClient:
    try:
        credential = DefaultAzureCredential(exclude_interactive_browser_credential=True)
        return BlobServiceClient(
            account_url=f"https://{storage_account}.blob.core.windows.net",
            credential=credential,
        )
    except Exception as exc:  # pragma: no cover - constructor errors are environment-specific
        raise UsageDiagnosticsError(f"Failed to initialize Azure credentials: {exc}") from exc


def fetch_records(resource_id: str, storage_account: str, start: datetime, end: datetime) -> tuple[list[DiagnosticRecord], dict[str, Any]]:
    client = create_blob_service_client(storage_account)
    blobs_scanned = 0
    blobs_downloaded = 0
    missing_blobs = []
    records: list[DiagnosticRecord] = []
    for hour in iter_hours(start, end):
        blob_name = blob_name_for_hour(resource_id, hour)
        blobs_scanned += 1
        try:
            blob_client = client.get_blob_client(container=CONTAINER_NAME, blob=blob_name)
            raw = blob_client.download_blob(max_concurrency=1).readall()
            if len(raw) > MAX_DOWNLOAD_BYTES:
                raise UsageDiagnosticsError(f"{blob_name} exceeds {MAX_DOWNLOAD_BYTES} bytes; narrow the time window")
            blobs_downloaded += 1
            records.extend(parse_blob_text(blob_name, raw.decode("utf-8-sig"), start=start, end=end))
        except ResourceNotFoundError:
            missing_blobs.append(blob_name)
        except ClientAuthenticationError as exc:
            raise UsageDiagnosticsError(
                "Azure authentication failed while reading diagnostic blobs. "
                "Run 'az login' or refresh Azure CLI auth, then retry."
            ) from exc
        except AzureError as exc:
            raise UsageDiagnosticsError(f"Azure Storage access failed for {blob_name}: {exc}") from exc
        except UnicodeDecodeError as exc:
            raise UsageDiagnosticsError(f"{blob_name} is not valid UTF-8 JSONL") from exc
    if blobs_downloaded == 0:
        raise UsageDiagnosticsError(
            "No AzureOpenAIRequestUsage blobs were found for the requested resource and time window"
        )
    metadata = {
        "container": CONTAINER_NAME,
        "hours_scanned": blobs_scanned,
        "blobs_downloaded": blobs_downloaded,
        "missing_blob_count": len(missing_blobs),
        "missing_blobs": missing_blobs,
    }
    return records, metadata


def build_summary(resource_id: str, storage_account: str, start: datetime, end: datetime, records: list[DiagnosticRecord], fetch_meta: dict[str, Any]) -> dict[str, Any]:
    return {
        "resource_id": resource_id,
        "storage_account": storage_account,
        "start": start.isoformat(),
        "end": end.isoformat(),
        **fetch_meta,
        "window_totals": aggregate_records(records),
        "models": summarize_by_model(records),
    }


def build_correlation_summary(
    resource_id: str,
    storage_account: str,
    start: datetime,
    end: datetime,
    records: list[DiagnosticRecord],
    fetch_meta: dict[str, Any],
    request_call_counts: list[int],
) -> dict[str, Any]:
    requests, warnings, unassigned = correlate_requests(records, request_call_counts)
    result = {
        "resource_id": resource_id,
        "storage_account": storage_account,
        "start": start.isoformat(),
        "end": end.isoformat(),
        **fetch_meta,
        "request_call_counts": request_call_counts,
        "window_totals": aggregate_records(records),
        "requests": requests,
    }
    if warnings:
        result["warnings"] = warnings
    if unassigned:
        result["unassigned"] = {
            **aggregate_records(unassigned),
            "models": summarize_by_model(unassigned),
        }
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch AzureOpenAIRequestUsage diagnostic blobs from Azure Storage, then emit either a raw "
            "per-model token summary or a sequential per-request correlation summary."
        )
    )
    parser.add_argument("--resource-id", required=True, help="Azure resource ID for the Foundry/Cognitive Services account")
    parser.add_argument("--storage-account", required=True, help="Storage account name holding exported diagnostic logs")
    parser.add_argument("--start", required=True, help="Inclusive ISO-8601 start time, e.g. 2026-09-10T20:00:00Z")
    parser.add_argument("--end", required=True, help="Exclusive ISO-8601 end time, e.g. 2026-09-10T21:00:00Z")
    parser.add_argument(
        "--request-call-counts",
        help=(
            "Comma-separated expected model-call counts for sequential CU requests, e.g. 4,4,6,6. "
            "When omitted, the tool prints only the raw aggregate summary."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(argv)
        resource_id = normalize_resource_id(args.resource_id)
        start = parse_timestamp(args.start, name="start")
        end = parse_timestamp(args.end, name="end")
        if end <= start:
            raise UsageDiagnosticsError("--end must be later than --start")
        request_call_counts = parse_positive_int_csv(args.request_call_counts)
        records, fetch_meta = fetch_records(resource_id, args.storage_account, start, end)
        if request_call_counts:
            result = build_correlation_summary(
                resource_id, args.storage_account, start, end, records, fetch_meta, request_call_counts
            )
            for warning in result.get("warnings", []):
                print(f"Warning: {warning}", file=sys.stderr)
        else:
            result = build_summary(resource_id, args.storage_account, start, end, records, fetch_meta)
        print(json.dumps(result, indent=2))
        return 0
    except UsageDiagnosticsError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
