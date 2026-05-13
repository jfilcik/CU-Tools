"""Preview → GA transform engine (Phase 3).

Automates the obvious schema work:
- Map preview scenario → GA baseAnalyzerId
- Remove deprecated preview-only properties
- Add ``models`` block
- Generate a proposed GA analyzer ID
- Build a structured transform log
"""

from __future__ import annotations

import re
from typing import Any

from cu_migrate.models import (
    DEPRECATED_PREVIEW_PROPERTIES,
    MigrationFinding,
    FindingSeverity,
    ProposedGAAnalyzer,
    SCENARIO_TO_BASE_ANALYZER,
    SourceAnalyzer,
    ValidationStatus,
)

# Default model deployments expected by GA
DEFAULT_MODELS: dict[str, Any] = {
    "completion": {"deploymentName": "gpt-4.1"},
    "embedding": {"deploymentName": "text-embedding-3-large"},
}


def _resolve_base_analyzer_id(source: SourceAnalyzer) -> tuple[str | None, list[MigrationFinding]]:
    """Map a preview scenario to a GA baseAnalyzerId."""
    findings: list[MigrationFinding] = []
    scenario = source.scenario or source.raw_definition.get("scenario", "")

    base_id = SCENARIO_TO_BASE_ANALYZER.get(scenario)
    if base_id is None:
        # Try case-insensitive lookup
        lower_map = {k.lower(): v for k, v in SCENARIO_TO_BASE_ANALYZER.items()}
        base_id = lower_map.get(scenario.lower())

    if base_id:
        findings.append(MigrationFinding(
            severity=FindingSeverity.AUTO_FIXED,
            category="base_analyzer",
            message=f"Mapped scenario '{scenario}' → baseAnalyzerId '{base_id}'",
            analyzer_id=source.analyzer_id,
            auto_fix_applied=True,
        ))
    else:
        findings.append(MigrationFinding(
            severity=FindingSeverity.NEEDS_REVIEW,
            category="base_analyzer",
            message=f"Could not map scenario '{scenario}' to a GA baseAnalyzerId",
            analyzer_id=source.analyzer_id,
            recommended_action="Manually set baseAnalyzerId in the GA payload",
        ))
    return base_id, findings


def _strip_deprecated(definition: dict[str, Any], analyzer_id: str) -> tuple[dict[str, Any], list[MigrationFinding]]:
    """Remove deprecated preview-only properties."""
    cleaned = dict(definition)
    findings: list[MigrationFinding] = []
    for prop in DEPRECATED_PREVIEW_PROPERTIES:
        if prop in cleaned:
            findings.append(MigrationFinding(
                severity=FindingSeverity.AUTO_FIXED,
                category="deprecated_property",
                message=f"Removed deprecated property '{prop}'",
                analyzer_id=analyzer_id,
                auto_fix_applied=True,
            ))
            del cleaned[prop]
    return cleaned, findings


def _generate_ga_id(source_id: str) -> str:
    """Produce a GA-friendly analyzer ID from the source ID."""
    base = re.sub(r"[^a-zA-Z0-9_-]", "-", source_id)
    if not base.endswith("-ga"):
        base = f"{base}-ga"
    return base


def transform_analyzer(source: SourceAnalyzer) -> tuple[ProposedGAAnalyzer, list[MigrationFinding]]:
    """Transform a preview SourceAnalyzer into a ProposedGAAnalyzer."""
    all_findings: list[MigrationFinding] = []

    # 1. Resolve base analyzer ID
    base_id, findings = _resolve_base_analyzer_id(source)
    all_findings.extend(findings)

    # 2. Strip deprecated properties from config
    cleaned_config, findings = _strip_deprecated(source.config, source.analyzer_id)
    all_findings.extend(findings)

    # Also strip from raw definition for the payload
    cleaned_raw, raw_findings = _strip_deprecated(dict(source.raw_definition), source.analyzer_id)
    # Don't double-count raw findings

    # 3. Build models block
    models = dict(DEFAULT_MODELS)
    all_findings.append(MigrationFinding(
        severity=FindingSeverity.NEEDS_REVIEW,
        category="models",
        message="Added default models block — verify deployment names match your resource",
        analyzer_id=source.analyzer_id,
        recommended_action="Confirm 'gpt-4.1' and 'text-embedding-3-large' deployments exist",
    ))

    # 4. Generate GA ID
    ga_id = _generate_ga_id(source.analyzer_id)

    # 5. Build GA payload
    ga_payload: dict[str, Any] = {
        "baseAnalyzerId": base_id or "prebuilt-document",
        "description": source.description or f"Migrated from {source.analyzer_id}",
        "models": models,
    }
    if source.field_schema:
        ga_payload["fieldSchema"] = source.field_schema
    if cleaned_config:
        ga_payload["config"] = cleaned_config

    # Determine validation status
    v_status = ValidationStatus.PASS
    if any(f.severity == FindingSeverity.NOT_SUPPORTED for f in all_findings):
        v_status = ValidationStatus.FAIL
    elif any(f.severity == FindingSeverity.NEEDS_REVIEW for f in all_findings):
        v_status = ValidationStatus.WARN

    proposed = ProposedGAAnalyzer(
        analyzer_id=ga_id,
        source_analyzer_id=source.analyzer_id,
        base_analyzer_id=base_id or "prebuilt-document",
        models=models,
        config=cleaned_config,
        field_schema=source.field_schema,
        ga_payload=ga_payload,
        validation_status=v_status,
    )
    return proposed, all_findings
