"""Data models for the CU migration tool.

Covers the migration contract defined in Phase 0:
- Scopes: single / selected / all analyzers
- Run modes: dry-run / export / apply
- Finding classes: auto-fixed / needs-review / not-supported
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class RunMode(str, Enum):
    DRY_RUN = "dry_run"
    EXPORT = "export"
    APPLY = "apply"


class MigrationReadiness(str, Enum):
    READY = "ready"
    REVIEW_NEEDED = "review_needed"
    BLOCKED = "blocked"


class FindingSeverity(str, Enum):
    AUTO_FIXED = "auto_fixed"
    NEEDS_REVIEW = "needs_review"
    NOT_SUPPORTED = "not_supported"


class ValidationStatus(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


# ---------------------------------------------------------------------------
# GA constants
# ---------------------------------------------------------------------------

SUPPORTED_BASE_ANALYZER_IDS: list[str] = [
    "prebuilt-read",
    "prebuilt-layout",
    "prebuilt-document",
    "prebuilt-customDocument",
    "prebuilt-invoice",
    "prebuilt-receipt",
    "prebuilt-tax.us.w2",
    "prebuilt-idDocument",
    "prebuilt-businessCard",
    "prebuilt-healthInsuranceCard.us",
]

# Map legacy preview scenario names → GA baseAnalyzerId
SCENARIO_TO_BASE_ANALYZER: dict[str, str] = {
    "document": "prebuilt-document",
    "prebuilt-document": "prebuilt-document",
    "layout": "prebuilt-layout",
    "prebuilt-layout": "prebuilt-layout",
    "read": "prebuilt-read",
    "prebuilt-read": "prebuilt-read",
    "invoice": "prebuilt-invoice",
    "prebuilt-invoice": "prebuilt-invoice",
    "receipt": "prebuilt-receipt",
    "prebuilt-receipt": "prebuilt-receipt",
    "idDocument": "prebuilt-idDocument",
    "prebuilt-idDocument": "prebuilt-idDocument",
    "businessCard": "prebuilt-businessCard",
    "prebuilt-businessCard": "prebuilt-businessCard",
    "tax.us.w2": "prebuilt-tax.us.w2",
    "prebuilt-tax.us.w2": "prebuilt-tax.us.w2",
    "healthInsuranceCard.us": "prebuilt-healthInsuranceCard.us",
    "prebuilt-healthInsuranceCard.us": "prebuilt-healthInsuranceCard.us",
    "customDocument": "prebuilt-customDocument",
    "prebuilt-customDocument": "prebuilt-customDocument",
}

# Properties that exist only in Preview and must be stripped
DEPRECATED_PREVIEW_PROPERTIES: set[str] = {
    "scenario",
    "analysisMode",
    "proMode",
    "faceAnalysis",
    "personDirectory",
}


# ---------------------------------------------------------------------------
# Core models
# ---------------------------------------------------------------------------

class Resource(BaseModel):
    """One Azure Content Understanding resource."""
    name: str
    endpoint: str
    auth_mode: str = "entra_id"  # entra_id | subscription_key


class AnalyzerInventoryItem(BaseModel):
    """Lightweight record for listing and filtering."""
    analyzer_id: str
    base_analyzer_type: str | None = None
    status: str | None = None
    created_date: datetime | None = None
    modified_date: datetime | None = None
    tags: dict[str, str] = Field(default_factory=dict)
    migration_readiness: MigrationReadiness = MigrationReadiness.REVIEW_NEEDED


class SourceAnalyzer(BaseModel):
    """Raw Preview analyzer definition."""
    analyzer_id: str
    description: str | None = None
    scenario: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    field_schema: dict[str, Any] = Field(default_factory=dict)
    training_data: dict[str, Any] | None = None
    tags: dict[str, str] = Field(default_factory=dict)
    raw_definition: dict[str, Any] = Field(default_factory=dict)


class ProposedGAAnalyzer(BaseModel):
    """Transformed GA analyzer definition."""
    analyzer_id: str
    source_analyzer_id: str
    base_analyzer_id: str
    models: dict[str, Any] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)
    field_schema: dict[str, Any] = Field(default_factory=dict)
    knowledge_sources: list[dict[str, Any]] = Field(default_factory=list)
    validation_status: ValidationStatus = ValidationStatus.WARN
    ga_payload: dict[str, Any] = Field(default_factory=dict)


class MigrationFinding(BaseModel):
    """One issue or warning produced during migration."""
    severity: FindingSeverity
    category: str
    message: str
    analyzer_id: str
    auto_fix_applied: bool = False
    recommended_action: str = ""


class MigrationResult(BaseModel):
    """Result for a single analyzer migration."""
    source: SourceAnalyzer
    proposed: ProposedGAAnalyzer | None = None
    findings: list[MigrationFinding] = Field(default_factory=list)
    validation_status: ValidationStatus = ValidationStatus.WARN


class MigrationRun(BaseModel):
    """One execution of the migration tool."""
    run_id: str
    mode: RunMode
    scope: str  # single / selected / all
    selected_analyzers: list[str] = Field(default_factory=list)
    results: list[MigrationResult] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @property
    def success_count(self) -> int:
        return sum(1 for r in self.results if r.validation_status == ValidationStatus.PASS)

    @property
    def warning_count(self) -> int:
        return sum(1 for r in self.results if r.validation_status == ValidationStatus.WARN)

    @property
    def failure_count(self) -> int:
        return sum(1 for r in self.results if r.validation_status == ValidationStatus.FAIL)
