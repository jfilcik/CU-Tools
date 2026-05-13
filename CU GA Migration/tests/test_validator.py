"""Tests for the validation layer."""

from __future__ import annotations

import pytest

from cu_migrate.models import FindingSeverity, ProposedGAAnalyzer, ValidationStatus
from cu_migrate.validator import validate


class TestValidation:
    def test_valid_analyzer_passes(self):
        proposed = ProposedGAAnalyzer(
            analyzer_id="test-analyzer-ga",
            source_analyzer_id="test-analyzer",
            base_analyzer_id="prebuilt-document",
            models={"completion": {"deploymentName": "gpt-4.1"}, "embedding": {"deploymentName": "text-embedding-3-large"}},
            ga_payload={
                "baseAnalyzerId": "prebuilt-document",
                "models": {"completion": {"deploymentName": "gpt-4.1"}, "embedding": {"deploymentName": "text-embedding-3-large"}},
            },
        )
        status, findings = validate(proposed)
        assert status == ValidationStatus.PASS

    def test_missing_models_warns(self):
        proposed = ProposedGAAnalyzer(
            analyzer_id="test-analyzer-ga",
            source_analyzer_id="test-analyzer",
            base_analyzer_id="prebuilt-document",
            models={},
            ga_payload={"baseAnalyzerId": "prebuilt-document"},
        )
        status, findings = validate(proposed)
        assert status == ValidationStatus.WARN
        model_findings = [f for f in findings if f.category == "models"]
        assert len(model_findings) >= 1

    def test_unknown_base_analyzer_warns(self):
        proposed = ProposedGAAnalyzer(
            analyzer_id="test-analyzer-ga",
            source_analyzer_id="test-analyzer",
            base_analyzer_id="prebuilt-unknownThing",
            models={"completion": {}, "embedding": {}},
            ga_payload={"baseAnalyzerId": "prebuilt-unknownThing", "models": {}},
        )
        status, findings = validate(proposed)
        base_findings = [f for f in findings if f.category == "base_analyzer"]
        assert len(base_findings) == 1

    def test_missing_payload_keys_warns(self):
        proposed = ProposedGAAnalyzer(
            analyzer_id="test-analyzer-ga",
            source_analyzer_id="test-analyzer",
            base_analyzer_id="prebuilt-document",
            models={"completion": {}, "embedding": {}},
            ga_payload={},
        )
        status, findings = validate(proposed)
        payload_findings = [f for f in findings if f.category == "payload"]
        assert len(payload_findings) >= 2

    def test_bad_knowledge_source_warns(self):
        proposed = ProposedGAAnalyzer(
            analyzer_id="test-analyzer-ga",
            source_analyzer_id="test-analyzer",
            base_analyzer_id="prebuilt-document",
            models={"completion": {}, "embedding": {}},
            knowledge_sources=[{"kind": "azureBlob", "azureBlobSource": {}}],
            ga_payload={"baseAnalyzerId": "prebuilt-document", "models": {}},
        )
        status, findings = validate(proposed)
        ks_findings = [f for f in findings if f.category == "knowledge_source"]
        assert len(ks_findings) >= 1
