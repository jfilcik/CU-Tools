"""Tests for the Preview→GA transform engine."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cu_migrate.models import FindingSeverity, SourceAnalyzer, ValidationStatus
from cu_migrate.transform import transform_analyzer

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


class TestTransformSimpleDocument:
    def test_maps_scenario_to_base_analyzer(self):
        source = _make_source("simple_document")
        proposed, findings = transform_analyzer(source)
        assert proposed.base_analyzer_id == "prebuilt-document"

    def test_generates_ga_id(self):
        source = _make_source("simple_document")
        proposed, _ = transform_analyzer(source)
        assert proposed.analyzer_id == "my_doc_analyzer_ga_v1"

    def test_adds_models_block(self):
        source = _make_source("simple_document")
        proposed, _ = transform_analyzer(source)
        assert "completion" in proposed.models
        assert "embedding" in proposed.models

    def test_preserves_field_schema(self):
        source = _make_source("simple_document")
        proposed, _ = transform_analyzer(source)
        assert proposed.field_schema == source.field_schema

    def test_ga_payload_has_required_keys(self):
        source = _make_source("simple_document")
        proposed, _ = transform_analyzer(source)
        assert "baseAnalyzerId" in proposed.ga_payload
        assert "models" in proposed.ga_payload


class TestTransformUnknownScenario:
    def test_flags_unknown_scenario(self):
        source = _make_source("unknown_scenario")
        proposed, findings = transform_analyzer(source)
        review_findings = [f for f in findings if f.severity == FindingSeverity.NOT_SUPPORTED and f.category == "base_analyzer"]
        assert len(review_findings) >= 1

    def test_unknown_scenario_has_no_success_shaped_fallback(self):
        source = _make_source("unknown_scenario")
        proposed, _ = transform_analyzer(source)
        assert proposed.base_analyzer_id == ""
        assert "baseAnalyzerId" not in proposed.ga_payload
        assert proposed.validation_status == ValidationStatus.FAIL


class TestTransformProMode:
    def test_strips_deprecated_properties(self):
        source = _make_source("with_pro_mode")
        proposed, findings = transform_analyzer(source)
        assert "proMode" not in proposed.config
        assert "analysisMode" not in proposed.config
        deprecated_findings = [f for f in findings if f.category == "deprecated_property"]
        assert len(deprecated_findings) >= 1
