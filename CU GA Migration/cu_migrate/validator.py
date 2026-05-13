"""Validation layer (Phase 6).

Validates the transformed GA analyzer payload before apply:
- Required top-level fields
- models presence
- knowledgeSources references
- Analyzer ID naming rules
- Overall pass / warn / fail
"""

from __future__ import annotations

import re

from cu_migrate.models import (
    FindingSeverity,
    MigrationFinding,
    ProposedGAAnalyzer,
    SUPPORTED_BASE_ANALYZER_IDS,
    ValidationStatus,
)

_ID_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,253}[a-zA-Z0-9]$")


def validate(proposed: ProposedGAAnalyzer) -> tuple[ValidationStatus, list[MigrationFinding]]:
    """Validate a proposed GA analyzer and return (status, findings)."""
    findings: list[MigrationFinding] = []
    aid = proposed.source_analyzer_id

    # 1. Analyzer ID format
    if not _ID_PATTERN.match(proposed.analyzer_id):
        findings.append(MigrationFinding(
            severity=FindingSeverity.NEEDS_REVIEW,
            category="analyzer_id",
            message=f"Proposed ID '{proposed.analyzer_id}' may not meet naming rules",
            analyzer_id=aid,
            recommended_action="Use alphanumeric characters, dots, hyphens, underscores; 2-255 chars",
        ))

    # 2. baseAnalyzerId is supported
    if proposed.base_analyzer_id not in SUPPORTED_BASE_ANALYZER_IDS:
        findings.append(MigrationFinding(
            severity=FindingSeverity.NEEDS_REVIEW,
            category="base_analyzer",
            message=f"baseAnalyzerId '{proposed.base_analyzer_id}' not in known GA list",
            analyzer_id=aid,
            recommended_action="Verify this baseAnalyzerId is valid for GA",
        ))

    # 3. models block
    if not proposed.models:
        findings.append(MigrationFinding(
            severity=FindingSeverity.NEEDS_REVIEW,
            category="models",
            message="Missing models block — GA requires completion and embedding models",
            analyzer_id=aid,
            recommended_action="Add models.completion and models.embedding to the payload",
        ))
    else:
        if "completion" not in proposed.models:
            findings.append(MigrationFinding(
                severity=FindingSeverity.NEEDS_REVIEW,
                category="models",
                message="Missing models.completion deployment",
                analyzer_id=aid,
                recommended_action="Add models.completion with a valid deployment name",
            ))
        if "embedding" not in proposed.models:
            findings.append(MigrationFinding(
                severity=FindingSeverity.NEEDS_REVIEW,
                category="models",
                message="Missing models.embedding deployment",
                analyzer_id=aid,
                recommended_action="Add models.embedding with a valid deployment name",
            ))

    # 4. knowledgeSources references — warn if present but incomplete
    for idx, ks in enumerate(proposed.knowledge_sources):
        blob_src = ks.get("azureBlobSource", {})
        if not blob_src.get("containerUrl"):
            findings.append(MigrationFinding(
                severity=FindingSeverity.NEEDS_REVIEW,
                category="knowledge_source",
                message=f"Knowledge source {idx} missing containerUrl",
                analyzer_id=aid,
                recommended_action="Provide a valid blob container URL",
            ))

    # 5. GA payload has required top-level keys
    payload = proposed.ga_payload
    for key in ("baseAnalyzerId", "models"):
        if key not in payload:
            findings.append(MigrationFinding(
                severity=FindingSeverity.NEEDS_REVIEW,
                category="payload",
                message=f"GA payload missing required key '{key}'",
                analyzer_id=aid,
                recommended_action=f"Add '{key}' to the GA payload",
            ))

    # Determine overall status
    if any(f.severity == FindingSeverity.NOT_SUPPORTED for f in findings):
        status = ValidationStatus.FAIL
    elif any(f.severity == FindingSeverity.NEEDS_REVIEW for f in findings):
        status = ValidationStatus.WARN
    else:
        status = ValidationStatus.PASS

    return status, findings
