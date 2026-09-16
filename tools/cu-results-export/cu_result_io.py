"""Offline readers for native ``cu --json`` results and saved CU-Tools envelopes.

No CLI/SDK imports, service calls, or raw-file writes belong in this module.
"""

import json
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple, Union


class ResultFormatError(ValueError):
    """An explicitly supplied or discovered analysis result is invalid."""


_METADATA_NAMES = {
    "metadata.json", "manifest.json", "experiment.json", "run.json", "report.json",
    "batch-report.json", "native-report.json", "summary.json", "comparison.json", "schema.json",
}
_METADATA_SUFFIXES = (
    ".summary.json", ".diagnosis.json", ".comparison.json", ".schema.json",
    ".report.json", ".manifest.json",
)
_STATES = {"succeeded", "failed", "canceled", "cancelled", "running", "notstarted"}


def result_payload(result: Dict[str, Any]) -> Dict[str, Any]:
    """Return the analysis object, unwrapping a native LRO or saved envelope once."""
    payload = result.get("result", result)
    return payload if isinstance(payload, dict) else {}


def result_status(result: Dict[str, Any]) -> Optional[str]:
    """Return only a recorded operation status; never infer success from fields."""
    metadata = result.get("_metadata", {})
    for value in (
        result.get("status"), result_payload(result).get("status"),
        metadata.get("status") if isinstance(metadata, dict) else None,
    ):
        if isinstance(value, str):
            return value
    if result.get("error") or result_payload(result).get("error"):
        return "failed"
    return None


def _metadata_payload(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    if data.get("schema") == "cu-cli/analyze-report/v1":
        return True
    fields = data.get("fields")
    if isinstance(fields, dict) and fields and all(
        isinstance(node, dict)
        and ("description" in node or "method" in node)
        and not any(key.startswith("value") for key in node)
        for node in fields.values()
    ):
        return True
    return any(key in data for key in (
        "fieldSchema", "baseAnalyzerId", "$schema", "batch_summary",
        "per_document_breakdown", "fill_rates", "comparisons",
    )) or ("results" in data and "counts" in data)


def normalize_result(data: Any) -> Dict[str, Any]:
    """Validate a direct/native-LRO/saved result without losing raw fields.

    Returns ``{"result": <native payload>, "_metadata": {...}, ...}``.
    Existing envelopes and metadata are retained. Empty/failed operation
    envelopes remain empty/failed, not synthesized successful analyses.
    """
    if not isinstance(data, dict) or _metadata_payload(data):
        raise ResultFormatError("Expected an analysis result, not report/schema metadata")
    if "result" in data and data["result"] is not None and not isinstance(data["result"], dict):
        raise ResultFormatError("'result' must be an object or null")
    payload = result_payload(data)
    status = result_status(data)
    if not (
        "contents" in payload or "fields" in payload or "result" in data
        or status is not None and status.lower() in _STATES
    ):
        raise ResultFormatError("Expected 'contents', 'fields', or an operation result")
    if "contents" in payload:
        contents = payload["contents"]
        if not isinstance(contents, list) or any(not isinstance(c, dict) for c in contents):
            raise ResultFormatError("'contents' must be an array of objects")
        for content in contents:
            if "fields" in content and not isinstance(content["fields"], dict):
                raise ResultFormatError("Content 'fields' must be an object")
    if "fields" in payload and not isinstance(payload["fields"], dict):
        raise ResultFormatError("'fields' must be an object")
    metadata = data.get("_metadata", {})
    if not isinstance(metadata, dict):
        raise ResultFormatError("'_metadata' must be an object")
    normalized = dict(data) if "result" in data else {"result": dict(data)}
    normalized["_metadata"] = dict(metadata)
    return normalized


def load_results(input_path: Union[str, Path]) -> List[Dict[str, Any]]:
    """Load a JSON file or recursively discover results once, in sorted order.

    Explicit metadata/non-result files are errors. During directory discovery,
    known metadata and unrecognized valid JSON are ignored, but malformed JSON
    and invalid result-shaped files raise ``ResultFormatError`` with their path.
    ``*.result.json`` is always treated as an intended result, even when invalid.

    Metadata adds ``result_file`` (path relative to the input directory) and a
    default ``source_file`` (the same path without ``.result.json``). Existing
    source/document metadata is preserved. No status, timing, run or iteration
    metadata is invented. Raw input files are never changed.
    """
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"Result input not found: {path}")
    directory = path.is_dir()
    if not directory and path.suffix.lower() != ".json":
        raise ResultFormatError(f"{path}: expected a JSON result file")
    files = sorted(path.rglob("*.json")) if directory else [path]
    results = []
    seen = set()
    for file_path in files:
        resolved = file_path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        name = file_path.name.lower()
        native_name = name.endswith(".result.json")
        if not native_name and (
            name in _METADATA_NAMES or name.endswith(_METADATA_SUFFIXES)
        ):
            if directory:
                continue
            raise ResultFormatError(f"{file_path}: expected an analysis result, not metadata")
        try:
            with file_path.open(encoding="utf-8-sig") as handle:
                data = json.load(handle)
            if directory and not native_name:
                if _metadata_payload(data):
                    continue
                if not isinstance(data, dict) or not any(
                    key in data for key in ("contents", "fields", "result", "status", "error")
                ):
                    continue
            result = normalize_result(data)
        except (ValueError, UnicodeError) as exc:
            raise ResultFormatError(f"{file_path}: {exc}") from exc
        relative = str(file_path.relative_to(path)) if directory else file_path.name
        metadata = result["_metadata"]
        metadata["result_file"] = relative
        source = relative[:-len(".result.json")] if native_name else relative
        metadata.setdefault("source_file", source)
        results.append(result)
    return results


def content_entries(result: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
    """Return category/fields pairs, including empty and failed entries.

    At least one entry per supplied result preserves incomplete-result
    denominators. A recorded non-success status never contributes field values.
    """
    status = result_status(result)
    if status is not None and status.lower() != "succeeded":
        return [("", {})]
    payload = result_payload(result)
    entries = []
    if "fields" in payload:
        entries.append(("", payload["fields"]))
    for content in payload.get("contents", []):
        entries.append((content.get("category") or "", content.get("fields", {})))
    return entries or [("", {})]


def field_value(field: Any) -> Any:
    """Unwrap a CU typed/legacy field, preserving explicit zero/false/null."""
    if not isinstance(field, dict):
        return field
    for key in ("value", "values"):
        if key in field:
            return field[key]
    for key, value in field.items():
        if key.startswith("value") and len(key) > 5 and key[5].isupper():
            return value
    if isinstance(field.get("type"), str) and set(field) <= {"type", "confidence", "source", "spans"}:
        return None
    return field


def decoded_value(field: Any) -> Any:
    """Recursively decode typed object/array values for spreadsheet cells."""
    value = field_value(field)
    if isinstance(value, dict):
        return {key: decoded_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [decoded_value(item) for item in value]
    return value


def is_filled(value: Any) -> bool:
    """A zero or false value is filled; null/empty collections are not."""
    return value is not None and value != "" and value != [] and value != {}


def field_nodes(fields: Dict[str, Any], prefix: str = "") -> Iterator[Tuple[str, Any]]:
    """Yield CU field nodes, descending through objects and indexed arrays."""
    for name, node in fields.items():
        full_name = f"{prefix}{name}"
        yield full_name, node
        value = field_value(node)
        if isinstance(value, dict):
            yield from field_nodes(value, f"{full_name}.")
        elif isinstance(value, list):
            for index, item in enumerate(value):
                yield from field_nodes({f"[{index}]": item}, full_name)


def result_usage(result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Read only structured ``usage`` on the envelope or native result."""
    for container in (result, result_payload(result)):
        if "usage" in container:
            usage = container["usage"]
            if usage is not None and not isinstance(usage, dict):
                raise ResultFormatError("'usage' must be an object or null")
            if usage is not None:
                return usage
    return None
