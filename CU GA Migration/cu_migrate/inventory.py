"""Inventory layer — discover and classify analyzers in a CU resource.

Connects to a resource, pulls analyzer metadata, and marks each with
a migration-readiness status: ready / review_needed / blocked.
"""

from __future__ import annotations

from cu_migrate.client import CUClient
from cu_migrate.models import (
    AnalyzerInventoryItem,
    DEPRECATED_PREVIEW_PROPERTIES,
    MigrationReadiness,
    SCENARIO_TO_BASE_ANALYZER,
)


def _classify_readiness(raw: dict) -> MigrationReadiness:
    """Heuristic readiness classification for a single analyzer."""
    # Blocked if using features removed from GA
    for prop in ("proMode", "faceAnalysis", "personDirectory"):
        val = raw.get(prop)
        if val is not None and val is not False:
            return MigrationReadiness.BLOCKED

    # Check if scenario maps cleanly to a GA base analyzer
    scenario = raw.get("scenario") or raw.get("baseAnalyzerId") or ""
    if scenario.lower() not in {k.lower() for k in SCENARIO_TO_BASE_ANALYZER}:
        if scenario:
            return MigrationReadiness.REVIEW_NEEDED

    # If there is training data, mark for review (needs knowledge source migration)
    if raw.get("trainingData") or raw.get("knowledgeSources"):
        return MigrationReadiness.REVIEW_NEEDED

    return MigrationReadiness.READY


def build_inventory(client: CUClient, include_prebuilt: bool = False) -> list[AnalyzerInventoryItem]:
    """Fetch all analyzers and return lightweight inventory items.

    Args:
        include_prebuilt: If False (default), skip ``prebuilt-*`` analyzers since
            they are provided by the API and already GA-ready.
    """
    raw_list = client.list_analyzers()
    items: list[AnalyzerInventoryItem] = []
    for raw in raw_list:
        aid = raw.get("analyzerId", "unknown")
        if not include_prebuilt and aid.startswith("prebuilt-"):
            continue
        item = AnalyzerInventoryItem(
            analyzer_id=raw.get("analyzerId", "unknown"),
            base_analyzer_type=raw.get("baseAnalyzerId") or raw.get("scenario"),
            status=raw.get("status"),
            created_date=raw.get("createdAt") or raw.get("createdDateTime"),
            modified_date=raw.get("lastModifiedAt") or raw.get("lastModifiedDateTime"),
            tags=raw.get("tags", {}),
            migration_readiness=_classify_readiness(raw),
        )
        items.append(item)
    return items
