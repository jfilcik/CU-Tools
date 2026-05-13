"""Compatibility rules engine (Phase 5).

Catches risky changes that require human review:
- AnalysisMode / Pro mode removal
- Face API and person directory removal
- analyzeBinary migration for inline uploads
- Missing model deployments
- Unresolved training data
- Content classifier / video segmentation remapping
"""

from __future__ import annotations

from typing import Any

from cu_migrate.models import (
    FindingSeverity,
    MigrationFinding,
    SourceAnalyzer,
)


def _check_pro_mode(source: SourceAnalyzer) -> list[MigrationFinding]:
    props = {**source.config, **source.raw_definition}
    findings: list[MigrationFinding] = []
    if props.get("proMode") or props.get("analysisMode", "").lower() == "pro":
        findings.append(MigrationFinding(
            severity=FindingSeverity.NOT_SUPPORTED,
            category="pro_mode",
            message="Pro mode / AnalysisMode 'pro' is not available in GA",
            analyzer_id=source.analyzer_id,
            recommended_action="Remove Pro mode reliance; use standard analysis with GA models",
        ))
    if props.get("analysisMode") and props.get("analysisMode", "").lower() != "pro":
        findings.append(MigrationFinding(
            severity=FindingSeverity.AUTO_FIXED,
            category="analysis_mode",
            message=f"Removed deprecated analysisMode '{props['analysisMode']}'",
            analyzer_id=source.analyzer_id,
            auto_fix_applied=True,
        ))
    return findings


def _check_face_api(source: SourceAnalyzer) -> list[MigrationFinding]:
    props = {**source.config, **source.raw_definition}
    findings: list[MigrationFinding] = []
    if props.get("faceAnalysis"):
        findings.append(MigrationFinding(
            severity=FindingSeverity.NOT_SUPPORTED,
            category="face_api",
            message="Face API analysis is not supported in GA",
            analyzer_id=source.analyzer_id,
            recommended_action="Remove faceAnalysis; use Azure AI Face service directly if needed",
        ))
    if props.get("personDirectory"):
        findings.append(MigrationFinding(
            severity=FindingSeverity.NOT_SUPPORTED,
            category="person_directory",
            message="Person directory is not supported in GA",
            analyzer_id=source.analyzer_id,
            recommended_action="Remove personDirectory; use Azure AI Face service directly if needed",
        ))
    return findings


def _check_inline_upload(source: SourceAnalyzer) -> list[MigrationFinding]:
    """Flag analyzers that may rely on inline binary upload in analyze calls."""
    props = {**source.config, **source.raw_definition}
    findings: list[MigrationFinding] = []
    # Heuristic: if the source definition mentions inline content or base64
    raw_str = str(props).lower()
    if "base64" in raw_str or "inlinecontent" in raw_str or "inline" in raw_str:
        findings.append(MigrationFinding(
            severity=FindingSeverity.NEEDS_REVIEW,
            category="inline_upload",
            message="Inline binary upload must move to analyzeBinary endpoint in GA",
            analyzer_id=source.analyzer_id,
            recommended_action="Update app code to use analyzeBinary for file uploads instead of inline content in analyze",
        ))
    return findings


def _check_training_data(source: SourceAnalyzer) -> list[MigrationFinding]:
    findings: list[MigrationFinding] = []
    if source.training_data:
        findings.append(MigrationFinding(
            severity=FindingSeverity.NEEDS_REVIEW,
            category="training_data",
            message="Preview trainingData must be converted to GA knowledgeSources",
            analyzer_id=source.analyzer_id,
            recommended_action="Run knowledge source migration and validate storage references",
        ))
    return findings


def _check_model_deployments(source: SourceAnalyzer) -> list[MigrationFinding]:
    """Warn that GA requires model deployments to be configured."""
    return [MigrationFinding(
        severity=FindingSeverity.NEEDS_REVIEW,
        category="model_deployment",
        message="GA requires completion and embedding model deployments on the resource",
        analyzer_id=source.analyzer_id,
        recommended_action="Verify gpt-4.1 and text-embedding-3-large deployments exist in your resource",
    )]


def _check_video_segmentation(source: SourceAnalyzer) -> list[MigrationFinding]:
    props = {**source.config, **source.raw_definition}
    findings: list[MigrationFinding] = []
    raw_str = str(props).lower()
    if "videosegmentation" in raw_str or "contentsegment" in raw_str:
        findings.append(MigrationFinding(
            severity=FindingSeverity.NEEDS_REVIEW,
            category="video_segmentation",
            message="Video segmentation / content classifier behavior may differ in GA",
            analyzer_id=source.analyzer_id,
            recommended_action="Review GA documentation for video/segmentation handling changes",
        ))
    return findings


def run_rules(source: SourceAnalyzer) -> list[MigrationFinding]:
    """Run all compatibility rules against a source analyzer."""
    findings: list[MigrationFinding] = []
    findings.extend(_check_pro_mode(source))
    findings.extend(_check_face_api(source))
    findings.extend(_check_inline_upload(source))
    findings.extend(_check_training_data(source))
    findings.extend(_check_model_deployments(source))
    findings.extend(_check_video_segmentation(source))
    return findings
