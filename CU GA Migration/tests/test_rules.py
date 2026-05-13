"""Tests for the compatibility rules engine."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cu_migrate.models import FindingSeverity, SourceAnalyzer
from cu_migrate.rules import run_rules

FIXTURES = Path(__file__).parent / "fixtures" / "sample_analyzers.json"


def _load_fixture(key: str) -> dict:
    data = json.loads(FIXTURES.read_text(encoding="utf-8"))
    return data[key]


def _make_source(fixture_key: str) -> SourceAnalyzer:
    raw = _load_fixture(fixture_key)
    props = raw.get("properties", raw)
    return SourceAnalyzer(
        analyzer_id=raw["analyzerId"],
        description=props.get("description"),
        scenario=props.get("scenario"),
        config={k: v for k, v in props.items() if k not in (
            "scenario", "description", "fieldSchema", "trainingData", "tags", "status",
        )},
        field_schema=props.get("fieldSchema", {}),
        training_data=props.get("trainingData"),
        tags=props.get("tags", {}),
        raw_definition=raw,
    )


class TestProModeRules:
    def test_flags_pro_mode_as_not_supported(self):
        source = _make_source("with_pro_mode")
        findings = run_rules(source)
        pro_findings = [f for f in findings if f.category == "pro_mode"]
        assert len(pro_findings) == 1
        assert pro_findings[0].severity == FindingSeverity.NOT_SUPPORTED

    def test_flags_analysis_mode_removal(self):
        source = _make_source("with_pro_mode")
        findings = run_rules(source)
        mode_findings = [f for f in findings if f.category in ("pro_mode", "analysis_mode")]
        assert len(mode_findings) >= 1


class TestFaceAPIRules:
    def test_flags_face_analysis(self):
        source = _make_source("with_face_api")
        findings = run_rules(source)
        face_findings = [f for f in findings if f.category == "face_api"]
        assert len(face_findings) == 1
        assert face_findings[0].severity == FindingSeverity.NOT_SUPPORTED

    def test_flags_person_directory(self):
        source = _make_source("with_face_api")
        findings = run_rules(source)
        pd_findings = [f for f in findings if f.category == "person_directory"]
        assert len(pd_findings) == 1
        assert pd_findings[0].severity == FindingSeverity.NOT_SUPPORTED


class TestTrainingDataRules:
    def test_flags_training_data_for_review(self):
        source = _make_source("with_training_data")
        findings = run_rules(source)
        td_findings = [f for f in findings if f.category == "training_data"]
        assert len(td_findings) == 1
        assert td_findings[0].severity == FindingSeverity.NEEDS_REVIEW


class TestSimpleDocumentRules:
    def test_no_blocking_findings(self):
        source = _make_source("simple_document")
        findings = run_rules(source)
        not_supported = [f for f in findings if f.severity == FindingSeverity.NOT_SUPPORTED]
        assert len(not_supported) == 0
