"""Offline GA shape validation; malformed proposals must block creation."""

from __future__ import annotations

from copy import deepcopy

import pytest

from cu_migrate.models import ProposedGAAnalyzer, ValidationStatus
from cu_migrate.validator import validate


def proposal(**changes):
    models = {"completion": "gpt-4.1", "embedding": "text-embedding-3-large"}
    values = {
        "analyzer_id": "invoice_ga_v1",
        "source_analyzer_id": "invoice",
        "base_analyzer_id": "prebuilt-document",
        "models": models,
        "ga_payload": {"baseAnalyzerId": "prebuilt-document", "models": deepcopy(models)},
    }
    values.update(changes)
    return ProposedGAAnalyzer(**values)


def test_valid_analyzer_passes():
    assert validate(proposal())[0] == ValidationStatus.PASS


@pytest.mark.parametrize("identifier", ["", "a-b", "a.b", "a b", "../outside", "a" * 65, "id\n", "é"])
def test_invalid_id_fails(identifier):
    status, findings = validate(proposal(analyzer_id=identifier))
    assert status == ValidationStatus.FAIL
    assert any(f.category == "analyzer_id" for f in findings)


@pytest.mark.parametrize("identifier", ["a", "_", "a" * 64])
def test_valid_ids(identifier):
    assert validate(proposal(analyzer_id=identifier))[0] == ValidationStatus.PASS


def test_source_id_cannot_be_reused():
    assert validate(proposal(analyzer_id="invoice"))[0] == ValidationStatus.FAIL


@pytest.mark.parametrize("models", [{}, {"embedding": "embed"}, {"completion": {}}, {"completion": ""}])
def test_missing_or_invalid_models_fail(models):
    value = proposal(models=models)
    value.ga_payload["models"] = models
    status, findings = validate(value)
    assert status == ValidationStatus.FAIL
    assert any(f.category == "models" for f in findings)


def test_missing_payload_keys_fail():
    status, findings = validate(proposal(ga_payload={}))
    assert status == ValidationStatus.FAIL
    assert len([f for f in findings if f.category == "payload"]) == 2


def test_unknown_explicit_base_requires_review():
    value = proposal(base_analyzer_id="custom_base")
    value.ga_payload["baseAnalyzerId"] = "custom_base"
    assert validate(value)[0] == ValidationStatus.WARN


@pytest.mark.parametrize("schema", [{}, [], {"fields": []}, {"fields": {"Total": {}}},
                                     {"fields": {"Total": {"type": "array"}}},
                                     {"fields": {"Total": {"type": "object", "properties": []}}},
                                     {"fields": {"Total": {"type": "number", "method": "unknown"}}}])
def test_bad_field_schema_fails(schema):
    value = proposal()
    value.ga_payload["fieldSchema"] = schema
    status, findings = validate(value)
    assert status == ValidationStatus.FAIL
    assert any(f.category == "field_schema" for f in findings)


@pytest.mark.parametrize("knowledge", [
    {"kind": "azureBlob", "azureBlobSource": {}},
    {"kind": "azureBlob", "azureBlobSource": "invalid"},
    {"kind": "azureBlob", "azureBlobSource": {"containerUrl": "relative"}},
    {"kind": "azureBlob", "azureBlobSource": {"containerUrl": 123}},
])
def test_bad_knowledge_source_fails(knowledge):
    status, findings = validate(proposal(knowledge_sources=[knowledge]))
    assert status == ValidationStatus.FAIL
    assert any(f.category == "knowledge_source" for f in findings)
