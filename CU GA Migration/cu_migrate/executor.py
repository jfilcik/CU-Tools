"""Execution engine (Phase 7).

Supports three modes:
- dry_run: inspect only, zero writes
- export: write JSON + Markdown artifacts to disk
- apply: create new GA analyzers via API
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from cu_migrate.client import CUClient
from cu_migrate.knowledge import migrate_knowledge_sources
from cu_migrate.models import (
    MigrationFinding,
    MigrationResult,
    MigrationRun,
    RunMode,
    SourceAnalyzer,
    ValidationStatus,
)
from cu_migrate.rules import run_rules
from cu_migrate.transform import transform_analyzer
from cu_migrate.validator import validate


_META_KEYS = {
    "analyzerId", "baseAnalyzerId", "description", "fieldSchema",
    "trainingData", "knowledgeSources", "tags", "status",
    "createdAt", "createdDateTime", "lastModifiedAt", "lastModifiedDateTime",
    "scenario", "warnings", "processingLocation", "supportedModels",
    "models", "config",
}


def _build_source(analyzer_id: str, raw: dict[str, Any]) -> SourceAnalyzer:
    """Convert a raw API response into a SourceAnalyzer model."""
    return SourceAnalyzer(
        analyzer_id=analyzer_id,
        description=raw.get("description"),
        scenario=raw.get("scenario") or raw.get("baseAnalyzerId"),
        config=raw.get("config", {}),
        field_schema=raw.get("fieldSchema", {}),
        training_data=raw.get("trainingData"),
        tags=raw.get("tags", {}),
        raw_definition=raw,
    )


def migrate_one(source: SourceAnalyzer) -> MigrationResult:
    """Run the full migration pipeline for a single analyzer (no API writes)."""
    all_findings: list[MigrationFinding] = []

    # 1. Compatibility rules
    all_findings.extend(run_rules(source))

    # 2. Transform
    proposed, transform_findings = transform_analyzer(source)
    all_findings.extend(transform_findings)

    # 3. Knowledge sources
    ks_list, ks_findings = migrate_knowledge_sources(source)
    all_findings.extend(ks_findings)
    if ks_list:
        proposed.knowledge_sources = ks_list
        proposed.ga_payload["knowledgeSources"] = ks_list

    # 4. Validate
    v_status, v_findings = validate(proposed)
    all_findings.extend(v_findings)
    proposed.validation_status = v_status

    return MigrationResult(
        source=source,
        proposed=proposed,
        findings=all_findings,
        validation_status=v_status,
    )


def execute(
    client: CUClient,
    analyzer_ids: list[str] | None,
    mode: RunMode,
    output_dir: Path | None = None,
) -> MigrationRun:
    """Run the migration for one, many, or all analyzers.

    Args:
        client: Connected CU REST client.
        analyzer_ids: Specific IDs to migrate, or None for all.
        mode: dry_run / export / apply.
        output_dir: Where to write export artifacts (used by export & apply modes).
    """
    # Resolve scope
    if analyzer_ids:
        raw_defs = {aid: client.get_analyzer(aid) for aid in analyzer_ids}
        scope = "selected" if len(analyzer_ids) > 1 else "single"
    else:
        all_raw = client.list_analyzers()
        raw_defs = {
            a.get("analyzerId", "unknown"): a
            for a in all_raw
            if not a.get("analyzerId", "").startswith("prebuilt-")
        }
        scope = "all"
        analyzer_ids = list(raw_defs.keys())

    run = MigrationRun(
        run_id=uuid.uuid4().hex[:12],
        mode=mode,
        scope=scope,
        selected_analyzers=analyzer_ids,
    )

    for aid, raw in raw_defs.items():
        source = _build_source(aid, raw)
        result = migrate_one(source)

        # Apply mode — create new analyzer via API
        if mode == RunMode.APPLY and result.proposed and result.validation_status != ValidationStatus.FAIL:
            try:
                client.create_analyzer(result.proposed.analyzer_id, result.proposed.ga_payload)
                result.findings.append(MigrationFinding(
                    severity=FindingSeverity.AUTO_FIXED,
                    category="apply",
                    message=f"Created GA analyzer '{result.proposed.analyzer_id}'",
                    analyzer_id=aid,
                    auto_fix_applied=True,
                ))
            except Exception as exc:
                result.findings.append(MigrationFinding(
                    severity=FindingSeverity.NOT_SUPPORTED,
                    category="apply_error",
                    message=f"Failed to create GA analyzer: {exc}",
                    analyzer_id=aid,
                    recommended_action="Check API error and retry",
                ))
                result.validation_status = ValidationStatus.FAIL

        run.results.append(result)

    # Export artifacts
    if mode in (RunMode.EXPORT, RunMode.APPLY) and output_dir:
        _write_artifacts(run, output_dir)

    return run


def _write_artifacts(run: MigrationRun, output_dir: Path) -> None:
    """Write JSON payloads and a manifest to disk."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Per-analyzer exports
    for result in run.results:
        if result.proposed:
            p = output_dir / f"{result.proposed.analyzer_id}.json"
            p.write_text(json.dumps(result.proposed.ga_payload, indent=2), encoding="utf-8")

        # Source backup
        backup = output_dir / f"{result.source.analyzer_id}_source_backup.json"
        backup.write_text(json.dumps(result.source.raw_definition, indent=2), encoding="utf-8")

    # Manifest
    manifest = {
        "run_id": run.run_id,
        "mode": run.mode.value,
        "scope": run.scope,
        "timestamp": run.timestamp.isoformat(),
        "analyzers": run.selected_analyzers,
        "success": run.success_count,
        "warnings": run.warning_count,
        "failures": run.failure_count,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
