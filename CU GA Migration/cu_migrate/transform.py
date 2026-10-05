"""Preview → GA transform engine (Phase 3).

Automates the obvious schema work:
- Map preview scenario → GA baseAnalyzerId
- Remove deprecated preview-only properties
- Add ``models`` block
- Generate a proposed GA analyzer ID
- Build a structured transform log
"""

from __future__ import annotations

import hashlib
import re
from copy import deepcopy
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

# Model IDs; resource-wide deployment mappings are managed by the official CLI.
DEFAULT_MODELS: dict[str, Any] = {
    "completion": "gpt-4.1",
    "embedding": "text-embedding-3-large",
}


def _resolve_base_analyzer_id(source: SourceAnalyzer) -> tuple[str | None, list[MigrationFinding]]:
    """Map a preview scenario to a GA baseAnalyzerId."""
    findings: list[MigrationFinding] = []
    scenario = source.scenario or source.definition.get("scenario", "")

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
            severity=FindingSeverity.NOT_SUPPORTED,
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
    suffix = "_ga_v1"
    base = re.sub(r"[^a-zA-Z0-9_]", "_", source_id)
    if len(base) + len(suffix) > 64:
        digest = hashlib.sha256(source_id.encode("utf-8")).hexdigest()[:8]
        base = f"{base[:64 - len(suffix) - 9]}_{digest}"
    return f"{base}{suffix}"


def transform_analyzer(source: SourceAnalyzer) -> tuple[ProposedGAAnalyzer, list[MigrationFinding]]:
    """Transform a preview SourceAnalyzer into a ProposedGAAnalyzer."""
    all_findings: list[MigrationFinding] = []

    # 1. Resolve base analyzer ID
    base_id, findings = _resolve_base_analyzer_id(source)
    all_findings.extend(findings)

    # 2. Strip deprecated properties from config
    cleaned_config, findings = _strip_deprecated(source.config, source.analyzer_id)
    all_findings.extend(findings)

    cleaned_raw, raw_findings = _strip_deprecated(source.definition, source.analyzer_id)
    all_findings.extend(raw_findings)

    # 3. Build models block
    models = deepcopy(source.definition.get("models", DEFAULT_MODELS))
    if "models" not in source.definition:
        all_findings.append(MigrationFinding(
            severity=FindingSeverity.NEEDS_REVIEW,
            category="models",
            message="Added default model IDs; no resource deployment mappings were checked or changed",
            analyzer_id=source.analyzer_id,
            recommended_action="Review model choices and inspect resource defaults using the official cu CLI",
        ))
    for role, model in models.items():
        if isinstance(model, dict) and set(model) == {"deploymentName"}:
            models[role] = model["deploymentName"]
            all_findings.append(MigrationFinding(
                severity=FindingSeverity.NEEDS_REVIEW,
                category="models",
                message=f"Converted legacy models.{role}.deploymentName to a string",
                analyzer_id=source.analyzer_id,
                recommended_action="Verify this value is a model ID and configure its deployment mapping with the official cu CLI",
            ))

    # 4. Generate GA ID
    ga_id = _generate_ga_id(source.analyzer_id)

    # 5. Build GA payload
    read_only = {
        "analyzerId", "id", "name", "status", "createdAt", "createdDateTime",
        "lastModifiedAt", "lastModifiedDateTime", "warnings", "supportedModels",
        "trainingData", "config",
    }
    ga_payload = {key: deepcopy(value) for key, value in cleaned_raw.items() if key not in read_only}
    ga_payload.update({
        "description": source.description or f"Migrated from {source.analyzer_id}",
        "models": models,
    })
    if base_id:
        ga_payload["baseAnalyzerId"] = base_id
    else:
        ga_payload.pop("baseAnalyzerId", None)
    if source.field_schema:
        ga_payload["fieldSchema"] = deepcopy(source.field_schema)
    if cleaned_config:
        ga_payload["config"] = deepcopy(cleaned_config)
    categories = cleaned_config.get("contentCategories", {})
    if isinstance(categories, dict) and any(
        isinstance(category, dict) and category.get("analyzerId") for category in categories.values()
    ):
        all_findings.append(MigrationFinding(
            severity=FindingSeverity.NEEDS_REVIEW,
            category="routing",
            message="Classifier analyzerId references are preserved, not redirected to proposed replacements",
            analyzer_id=source.analyzer_id,
            recommended_action="Create and test inner replacements first, then review routing IDs before creating the classifier",
        ))

    # Determine validation status
    v_status = ValidationStatus.PASS
    if any(f.severity == FindingSeverity.NOT_SUPPORTED for f in all_findings):
        v_status = ValidationStatus.FAIL
    elif any(f.severity == FindingSeverity.NEEDS_REVIEW for f in all_findings):
        v_status = ValidationStatus.WARN

    proposed = ProposedGAAnalyzer(
        analyzer_id=ga_id,
        source_analyzer_id=source.analyzer_id,
        base_analyzer_id=base_id or "",
        models=models,
        config=cleaned_config,
        field_schema=source.field_schema,
        ga_payload=ga_payload,
        validation_status=v_status,
    )
    return proposed, all_findings
