"""Offline shape checks, not service validation or a guarantee of parity."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit

from cu_migrate.models import (
    FindingSeverity,
    MigrationFinding,
    ProposedGAAnalyzer,
    SUPPORTED_BASE_ANALYZER_IDS,
    ValidationStatus,
)

_ID_PATTERN = re.compile(r"[a-zA-Z0-9_]{1,64}")
_FIELD_TYPES = {"string", "number", "integer", "boolean", "date", "time", "array", "object"}


def validate(proposed: ProposedGAAnalyzer) -> tuple[ValidationStatus, list[MigrationFinding]]:
    """Reject structurally invalid proposals; flag unknown service capabilities."""
    findings: list[MigrationFinding] = []

    def finding(category: str, message: str, review: bool = False) -> None:
        findings.append(MigrationFinding(
            severity=FindingSeverity.NEEDS_REVIEW if review else FindingSeverity.NOT_SUPPORTED,
            category=category,
            message=message,
            analyzer_id=proposed.source_analyzer_id,
            recommended_action="Correct the proposal, then validate it with the official cu CLI before creation",
        ))

    if not _ID_PATTERN.fullmatch(proposed.analyzer_id):
        finding("analyzer_id", "Proposed ID must use only letters, digits and underscores (1-64 characters)")
    if proposed.analyzer_id.casefold() == proposed.source_analyzer_id.casefold():
        finding("analyzer_id", "The replacement must have a new versioned ID, not the source ID")
    if not proposed.base_analyzer_id:
        finding("base_analyzer", "No GA baseAnalyzerId could be resolved")
    elif proposed.base_analyzer_id not in SUPPORTED_BASE_ANALYZER_IDS:
        finding("base_analyzer", f"baseAnalyzerId '{proposed.base_analyzer_id}' is not in the known GA list", review=True)

    payload = proposed.ga_payload
    for key in ("baseAnalyzerId", "models"):
        if key not in payload:
            finding("payload", f"GA payload missing required key '{key}'")
    if not proposed.models or "completion" not in proposed.models:
        finding("models", "Missing models.completion model ID")
    for role, model in proposed.models.items():
        if not isinstance(model, str) or not model.strip():
            finding("models", f"models.{role} must be a non-empty model ID string")
    if payload.get("models") != proposed.models:
        finding("models", "Payload models differ from the proposed model choices")
    if payload.get("baseAnalyzerId") != proposed.base_analyzer_id:
        finding("base_analyzer", "Payload baseAnalyzerId differs from the proposed base")

    def check_fields(fields: Any, path: str) -> None:
        if not isinstance(fields, dict):
            finding("field_schema", f"{path} must be an object")
            return
        for name, field in fields.items():
            check_field(field, f"{path}.{name}")

    def check_field(field: Any, path: str) -> None:
        if not isinstance(field, dict):
            finding("field_schema", f"{path} must be an object")
            return
        field_type = field.get("type")
        if not isinstance(field_type, str) or field_type not in _FIELD_TYPES:
            finding("field_schema", f"{path} has a missing or unsupported field type")
        if field_type == "array":
            check_field(field.get("items"), f"{path}.items")
        if field_type == "object":
            check_fields(field.get("properties"), f"{path}.properties")
        if "method" in field and field["method"] not in ("extract", "generate", "classify"):
            finding("field_schema", f"{path}.method must be extract, generate or classify")

    if "fieldSchema" in payload:
        schema = payload["fieldSchema"]
        if not isinstance(schema, dict) or "fields" not in schema:
            finding("field_schema", "fieldSchema must contain a fields object")
        else:
            check_fields(schema["fields"], "fieldSchema.fields")

    for idx, ks in enumerate(proposed.knowledge_sources):
        blob = ks.get("azureBlobSource")
        if not isinstance(blob, dict):
            finding("knowledge_source", f"Knowledge source {idx} missing an azureBlobSource object")
            continue
        url = blob.get("containerUrl")
        try:
            parsed = urlsplit(url) if isinstance(url, str) else None
            valid_url = parsed is not None and parsed.scheme == "https" and bool(parsed.netloc)
        except ValueError:
            valid_url = False
        if not valid_url:
            finding("knowledge_source", f"Knowledge source {idx} requires an absolute HTTPS containerUrl")
        if "fieldMappings" in ks and not isinstance(ks["fieldMappings"], (dict, list)):
            finding("knowledge_source", f"Knowledge source {idx} fieldMappings must be an object or array")
    if proposed.knowledge_sources:
        finding("knowledge_source_access", "Storage access and field mapping semantics have not been checked offline", review=True)

    if any(f.severity == FindingSeverity.NOT_SUPPORTED for f in findings):
        status = ValidationStatus.FAIL
    elif any(f.severity == FindingSeverity.NEEDS_REVIEW for f in findings):
        status = ValidationStatus.WARN
    else:
        status = ValidationStatus.PASS
    return status, findings
