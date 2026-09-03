"""Tests for preview-only analyzer configuration validation."""

import sys
from pathlib import Path

import pytest

VALIDATOR_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VALIDATOR_DIR))

from cu_analyzer_validator import validate_cu_analyzer


def _schema(workflow):
    return {
        "baseAnalyzerId": "prebuilt-document",
        "config": {"workflow": workflow},
        "fieldSchema": {
            "fields": {
                "Summary": {
                    "type": "string",
                    "method": "generate",
                    "description": "Generate a concise summary grounded in the document text.",
                }
            }
        },
    }


def test_agentic_workflow_is_valid_for_preview_api():
    result = validate_cu_analyzer(
        _schema("Agentic"),
        api_version="2026-06-01-preview",
    )

    assert result.is_valid
    assert not result.warnings


@pytest.mark.parametrize("workflow", ["agentic", "High", True, None])
def test_agentic_workflow_rejects_malformed_values(workflow):
    result = validate_cu_analyzer(
        _schema(workflow),
        api_version="2026-06-01-preview",
    )

    assert not result.is_valid
    assert any(error.path == "config.workflow" for error in result.errors)


def test_agentic_workflow_requires_explicit_preview_api():
    result = validate_cu_analyzer(_schema("Agentic"))

    assert not result.is_valid
    assert any(
        "preview API" in error.message for error in result.errors
        if error.path == "config.workflow"
    )
