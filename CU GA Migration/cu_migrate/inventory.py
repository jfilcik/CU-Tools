"""Load and inventory explicit local analyzer exports; no service access."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Sequence

from cu_migrate.models import (
    AnalyzerInventoryItem,
    FindingSeverity,
    MigrationReadiness,
    SCENARIO_TO_BASE_ANALYZER,
    SourceAnalyzer,
)
from cu_migrate.rules import run_rules


def _json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _invalid_constant(value: str) -> None:
    raise ValueError(f"Non-finite JSON value is not supported: {value}")


def _records(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        records = data
    elif isinstance(data, dict):
        if data.get("nextLink") or data.get("@odata.nextLink"):
            raise ValueError("Export is incomplete (nextLink present); supply all pages exported with the official cu CLI")
        wrappers = [key for key in ("value", "analyzers", "items") if key in data]
        if len(wrappers) > 1:
            raise ValueError("Ambiguous analyzer list wrapper")
        records = data[wrappers[0]] if wrappers else [data]
    else:
        raise ValueError("Expected an analyzer object or an array of analyzer objects")
    if not isinstance(records, list) or not records:
        raise ValueError("Analyzer export must contain a non-empty array or definition")
    if any(not isinstance(record, dict) or not record for record in records):
        raise ValueError("Every analyzer entry must be a non-empty JSON object")
    return records


def _source(raw: dict[str, Any], path: Path, digest: str, source_id: str | None) -> SourceAnalyzer:
    body = raw.get("properties", raw)
    if not isinstance(body, dict):
        raise ValueError("'properties' must be an object")
    identities = [
        obj[key]
        for obj in (raw, body)
        for key in ("analyzerId", "id", "name")
        if key in obj
    ]
    if source_id is not None:
        identities.append(source_id)
    if not identities or any(not isinstance(aid, str) or not aid.strip() for aid in identities):
        raise ValueError("Analyzer ID is missing or invalid; use --source-id for one ID-less definition")
    if len(set(identities)) != 1:
        raise ValueError("Conflicting analyzer IDs in the export or --source-id")
    aid = identities[0]
    if aid != aid.strip():
        raise ValueError("Analyzer IDs cannot have leading or trailing whitespace")
    for key in ("config", "fieldSchema", "models", "tags"):
        if key in body and not isinstance(body[key], dict):
            raise ValueError(f"Analyzer {aid!r}: '{key}' must be an object")
    for key in ("scenario", "baseAnalyzerId", "analysisMode"):
        if key in body and (not isinstance(body[key], str) or not body[key].strip()):
            raise ValueError(f"Analyzer {aid!r}: '{key}' must be a non-empty string")
    config = body.get("config", {})
    if "analysisMode" in config and not isinstance(config["analysisMode"], str):
        raise ValueError(f"Analyzer {aid!r}: config.analysisMode must be a string")
    td = body.get("trainingData")
    if td is not None and (
        not isinstance(td, (dict, list))
        or isinstance(td, list) and any(not isinstance(item, dict) for item in td)
    ):
        raise ValueError(f"Analyzer {aid!r}: trainingData must be an object or array of objects")
    ks = body.get("knowledgeSources", [])
    if not isinstance(ks, list) or any(not isinstance(item, dict) for item in ks):
        raise ValueError(f"Analyzer {aid!r}: knowledgeSources must be an array of objects")
    return SourceAnalyzer(
        analyzer_id=aid,
        description=body.get("description"),
        scenario=body.get("baseAnalyzerId") or body.get("scenario"),
        config=config,
        field_schema=body.get("fieldSchema", {}),
        training_data=td,
        tags=body.get("tags", {}),
        raw_definition=raw,
        source_path=str(path),
        source_sha256=digest,
        definition_available=bool(body.get("baseAnalyzerId") or body.get("scenario")),
    )


def load_sources(paths: Sequence[Path], source_id: str | None = None) -> list[SourceAnalyzer]:
    """Read files or immediate *.json directory children, rejecting ambiguous input.

    Accept a definition, an array, or value/analyzers/items list wrappers.
    --source-id supplies the identity only for one standalone definition file.
    """
    if not paths:
        raise ValueError("Supply at least one local analyzer export with --input")
    if source_id is not None and (len(paths) != 1 or not Path(paths[0]).is_file()):
        raise ValueError("--source-id requires exactly one definition file, not a directory")
    files: list[Path] = []
    for value in paths:
        path = Path(value).resolve()
        if path.is_dir():
            children = sorted(p for p in path.glob("*.json") if p.is_file())
            if not children:
                raise ValueError(f"No JSON exports found in directory: {path}")
            files.extend(children)
        elif path.is_file():
            files.append(path)
        else:
            raise ValueError(f"Input does not exist or is not a file/directory: {path}")
    sources: list[SourceAnalyzer] = []
    seen: set[str] = set()
    for path in files:
        try:
            content = path.read_bytes()
            data = json.loads(
                content, object_pairs_hook=_json_object, parse_constant=_invalid_constant,
            )
            records = _records(data)
            if source_id is not None and (not isinstance(data, dict) or records != [data]):
                raise ValueError("--source-id is only supported for one standalone analyzer object")
            digest = hashlib.sha256(content).hexdigest()
            for record in records:
                source = _source(record, path, digest, source_id)
                if source.analyzer_id in seen:
                    raise ValueError(f"Duplicate analyzer ID: {source.analyzer_id!r}; supply each definition once")
                seen.add(source.analyzer_id)
                sources.append(source)
        except (OSError, ValueError) as exc:
            raise ValueError(f"Cannot load {path}: {exc}") from exc
    return sources


def build_inventory(
    sources: Sequence[SourceAnalyzer], include_prebuilt: bool = False,
) -> list[AnalyzerInventoryItem]:
    """Classify locally supplied definitions; list-only metadata needs review."""
    items: list[AnalyzerInventoryItem] = []
    for source in sources:
        if not include_prebuilt and source.analyzer_id.startswith("prebuilt-"):
            continue
        raw = source.definition
        if any(f.severity == FindingSeverity.NOT_SUPPORTED for f in run_rules(source)):
            readiness = MigrationReadiness.BLOCKED
        elif (
            not source.definition_available
            or (source.scenario or "").lower() not in {k.lower() for k in SCENARIO_TO_BASE_ANALYZER}
            or source.training_data
            or raw.get("knowledgeSources")
        ):
            readiness = MigrationReadiness.REVIEW_NEEDED
        else:
            readiness = MigrationReadiness.READY
        items.append(AnalyzerInventoryItem(
            analyzer_id=source.analyzer_id,
            base_analyzer_type=source.scenario,
            status=raw.get("status"),
            created_date=raw.get("createdAt") or raw.get("createdDateTime"),
            modified_date=raw.get("lastModifiedAt") or raw.get("lastModifiedDateTime"),
            tags=source.tags,
            migration_readiness=readiness,
            definition_available=source.definition_available,
        ))
    if not items:
        raise ValueError("No custom analyzers supplied; use --include-prebuilt to inventory built-ins")
    return items
