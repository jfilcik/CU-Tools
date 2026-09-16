"""Plan migrations from local exports and optionally write a new review bundle."""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path
from typing import Sequence

from cu_migrate.knowledge import migrate_knowledge_sources
from cu_migrate.models import (
    FindingSeverity,
    MigrationFinding,
    MigrationResult,
    MigrationRun,
    RunMode,
    SourceAnalyzer,
    ValidationStatus,
)
from cu_migrate.reports import create_command, write_reports
from cu_migrate.rules import run_rules
from cu_migrate.transform import transform_analyzer
from cu_migrate.validator import validate


def _failure(source: SourceAnalyzer, category: str, message: str) -> MigrationFinding:
    return MigrationFinding(
        severity=FindingSeverity.NOT_SUPPORTED,
        category=category,
        message=message,
        analyzer_id=source.analyzer_id,
        recommended_action="Correct the local input and rerun into a new output directory",
    )


def migrate_one(source: SourceAnalyzer) -> MigrationResult:
    """Transform and validate a definition, retaining blockers from every stage."""
    if not source.definition_available:
        return MigrationResult(
            source=source,
            findings=[_failure(
                source, "missing_definition",
                "Only list metadata was supplied. Export the full definition using "
                "'cu analyzer show NAME' (JSON stdout) before planning this analyzer",
            )],
            validation_status=ValidationStatus.FAIL,
        )
    findings = run_rules(source)
    proposed, transform_findings = transform_analyzer(source)
    findings.extend(transform_findings)
    knowledge_sources, knowledge_findings = migrate_knowledge_sources(source)
    findings.extend(knowledge_findings)
    proposed.knowledge_sources = knowledge_sources
    if knowledge_sources:
        proposed.ga_payload["knowledgeSources"] = knowledge_sources
    _, validation_findings = validate(proposed)
    findings.extend(validation_findings)
    if any(f.severity == FindingSeverity.NOT_SUPPORTED for f in findings):
        status = ValidationStatus.FAIL
    elif any(f.severity == FindingSeverity.NEEDS_REVIEW for f in findings):
        status = ValidationStatus.WARN
    else:
        status = ValidationStatus.PASS
    proposed.validation_status = status
    return MigrationResult(source=source, proposed=proposed, findings=findings, validation_status=status)


def execute(
    sources: Sequence[SourceAnalyzer],
    analyzer_ids: list[str] | None = None,
    mode: RunMode = RunMode.DRY_RUN,
    output_dir: Path | None = None,
) -> MigrationRun:
    """Plan single, selected, or all local custom analyzers. Never deploy."""
    mode = RunMode(mode)
    if mode == RunMode.EXPORT and output_dir is None:
        raise ValueError("--output is required for export mode")
    if mode == RunMode.DRY_RUN and output_dir is not None:
        raise ValueError("--output is only valid in export mode; dry_run writes no files")
    if output_dir is not None and Path(output_dir).exists():
        raise ValueError(f"Output already exists; choose a new directory: {output_dir}")
    by_id = {source.analyzer_id: source for source in sources}
    if len(by_id) != len(sources):
        raise ValueError("Duplicate analyzer IDs supplied")
    if analyzer_ids is not None:
        if not analyzer_ids or len(set(analyzer_ids)) != len(analyzer_ids):
            raise ValueError("Selected analyzer IDs must be non-empty and unique")
        unknown = set(analyzer_ids) - by_id.keys()
        if unknown:
            raise ValueError(f"Unknown locally supplied analyzer ID(s): {', '.join(sorted(unknown))}")
        if any(aid.startswith("prebuilt-") for aid in analyzer_ids):
            raise ValueError("Built-in prebuilt analyzers cannot be migrated; select local custom definitions")
        selected = [by_id[aid] for aid in analyzer_ids]
        scope = "single" if len(selected) == 1 else "selected"
    else:
        selected = [source for source in sources if not source.analyzer_id.startswith("prebuilt-")]
        scope = "all"
    if not selected:
        raise ValueError("No custom analyzer definitions supplied")
    run = MigrationRun(
        run_id=uuid.uuid4().hex[:12],
        mode=mode,
        scope=scope,
        selected_analyzers=[source.analyzer_id for source in selected],
    )
    for source in selected:
        try:
            result = migrate_one(source)
        except (ValueError, TypeError, AttributeError) as exc:
            result = MigrationResult(
                source=source,
                findings=[_failure(source, "invalid_definition", f"Cannot transform definition: {exc}")],
                validation_status=ValidationStatus.FAIL,
            )
        run.results.append(result)

    targets: dict[str, list[MigrationResult]] = {}
    source_ids = {source.analyzer_id.casefold() for source in sources}
    for result in run.results:
        if result.proposed:
            targets.setdefault(result.proposed.analyzer_id.casefold(), []).append(result)
    for target, results in targets.items():
        if len(results) > 1 or target in source_ids:
            for result in results:
                result.findings.append(_failure(
                    result.source, "target_collision",
                    "Proposed ID collides with another proposal or a supplied source ID; choose distinct source/version names",
                ))
                result.validation_status = ValidationStatus.FAIL
                result.proposed.validation_status = ValidationStatus.FAIL
    if output_dir is not None:
        _write_artifacts(run, Path(output_dir).resolve())
    return run


def _write_artifacts(run: MigrationRun, output_dir: Path) -> None:
    """Write exclusively to a new directory; the final manifest marks completion."""
    exports: dict[str, tuple[bytes, str]] = {}
    for result in run.results:
        source = result.source
        if source.source_path and source.source_path not in exports:
            content = Path(source.source_path).read_bytes()
            digest = hashlib.sha256(content).hexdigest()
            if digest != source.source_sha256:
                raise ValueError(f"Source export changed after loading: {source.source_path}")
            exports[source.source_path] = (content, digest)
    output_dir.mkdir(parents=True, exist_ok=False)
    for name in ("sources", "backups", "proposed", "blocked"):
        (output_dir / name).mkdir()

    def write_json(path: Path, value: object) -> None:
        with path.open("x", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, ensure_ascii=False, allow_nan=False)
            handle.write("\n")

    evidence = []
    for index, (path, (content, digest)) in enumerate(exports.items(), 1):
        backup = f"sources/{index:04d}.json"
        with (output_dir / backup).open("xb") as handle:
            handle.write(content)
        evidence.append({"input_path": path, "sha256": digest, "backup": backup})

    plans = []
    for index, result in enumerate(run.results, 1):
        backup = f"backups/{index:04d}.json"
        write_json(output_dir / backup, result.source.raw_definition)
        proposal_path = None
        command = None
        if result.proposed:
            if result.validation_status == ValidationStatus.FAIL:
                # Number blocked payloads so even colliding target IDs retain evidence.
                proposal_path = f"blocked/{index:04d}.json"
            else:
                proposal_path = f"proposed/{result.proposed.analyzer_id}.json"
                command = create_command(result.proposed.analyzer_id)
            write_json(output_dir / proposal_path, result.proposed.ga_payload)
        plans.append({
            "source_id": result.source.analyzer_id,
            "proposed_id": result.proposed.analyzer_id if result.proposed else None,
            "validation_status": result.validation_status.value,
            "source_backup": backup,
            "payload": proposal_path,
            "create_command": command,
            "deployed": False,
        })
    write_json(output_dir / "migration_run.json", run.model_dump(mode="json"))
    write_reports(run, output_dir)
    write_json(output_dir / "manifest.json", {
        "run_id": run.run_id,
        "mode": run.mode.value,
        "scope": run.scope,
        "timestamp": run.timestamp.isoformat(),
        "api_version": "2025-11-01",
        "deployed": False,
        "success": run.success_count,
        "warnings": run.warning_count,
        "failures": run.failure_count,
        "source_exports": evidence,
        "analyzers": plans,
    })
