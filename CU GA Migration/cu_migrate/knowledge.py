"""Knowledge source migration (Phase 4).

Detects preview ``trainingData``, converts to GA ``knowledgeSources``,
reuses existing blob storage locations, and preserves field mappings.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from cu_migrate.models import (
    FindingSeverity,
    MigrationFinding,
    SourceAnalyzer,
)


def migrate_knowledge_sources(
    source: SourceAnalyzer,
) -> tuple[list[dict[str, Any]], list[MigrationFinding]]:
    """Convert preview trainingData → GA knowledgeSources.

    Returns (knowledge_sources_list, findings).
    """
    findings: list[MigrationFinding] = []
    knowledge_sources: list[dict[str, Any]] = deepcopy(source.definition.get("knowledgeSources", []))

    td = source.training_data
    if td is None or td == []:
        return knowledge_sources, findings

    # Training data may be a single dict or a list
    datasets: list[dict[str, Any]] = td if isinstance(td, list) else [td]

    for idx, ds in enumerate(datasets):
        ks: dict[str, Any] = {}
        blob_source = ds.get("azureBlobSource", {})
        if not isinstance(blob_source, dict):
            findings.append(MigrationFinding(
                severity=FindingSeverity.NOT_SUPPORTED,
                category="knowledge_source",
                message=f"Dataset {idx} azureBlobSource must be an object",
                analyzer_id=source.analyzer_id,
                recommended_action="Correct the local trainingData export before replanning",
            ))
            continue

        # Reuse blob storage location
        blob_url = ds.get("blobContainerUrl") or ds.get("storageUrl") or blob_source.get("containerUrl")
        if blob_url:
            ks["kind"] = "azureBlob"
            ks["azureBlobSource"] = {"containerUrl": blob_url}
            prefix = ds.get("prefix") or blob_source.get("prefix")
            if prefix:
                ks["azureBlobSource"]["prefix"] = prefix
            findings.append(MigrationFinding(
                severity=FindingSeverity.AUTO_FIXED,
                category="knowledge_source",
                message=f"Reused blob storage location for dataset {idx}",
                analyzer_id=source.analyzer_id,
                auto_fix_applied=True,
            ))
        else:
            findings.append(MigrationFinding(
                severity=FindingSeverity.NOT_SUPPORTED,
                category="knowledge_source",
                message=f"Dataset {idx} has no recognizable blob URL — manual mapping needed",
                analyzer_id=source.analyzer_id,
                recommended_action="Provide a valid azureBlobSource.containerUrl",
            ))
            continue

        # Preserve field mappings
        field_mappings = ds.get("fieldMappings") or ds.get("fields")
        if field_mappings:
            ks["fieldMappings"] = deepcopy(field_mappings)
            if isinstance(field_mappings, (list, dict)):
                findings.append(MigrationFinding(
                    severity=FindingSeverity.AUTO_FIXED,
                    category="knowledge_source_fields",
                    message=f"Preserved {len(field_mappings)} field mapping(s) for dataset {idx}",
                    analyzer_id=source.analyzer_id,
                    auto_fix_applied=True,
                ))
        else:
            findings.append(MigrationFinding(
                severity=FindingSeverity.NEEDS_REVIEW,
                category="knowledge_source_fields",
                message=f"No field mappings found for dataset {idx}",
                analyzer_id=source.analyzer_id,
                recommended_action="Review whether field mappings are needed for this knowledge source",
            ))

        knowledge_sources.append(ks)

    converted = len(knowledge_sources) - len(source.definition.get("knowledgeSources", []))
    if converted:
        findings.append(MigrationFinding(
            severity=FindingSeverity.AUTO_FIXED,
            category="knowledge_source",
            message=f"Converted {converted} trainingData entry(ies) → knowledgeSources",
            analyzer_id=source.analyzer_id,
            auto_fix_applied=True,
        ))

    return knowledge_sources, findings
