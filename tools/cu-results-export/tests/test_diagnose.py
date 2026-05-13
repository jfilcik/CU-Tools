"""
Tests for export.py --diagnose functionality:
  - extract_confidence_from_fields
  - extract_all_confidences
  - diagnose_fields
  - _discover_cu_fields
  - _compute_cu_fill_rates
"""
import json
import sys
from pathlib import Path

import pytest

TOOLS_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(TOOLS_ROOT / "cu-results-export"))

from export import (
    _compute_cu_fill_rates,
    _discover_cu_fields,
    _median,
    _stdev,
    diagnose_fields,
    extract_all_confidences,
    extract_confidence_from_fields,
)


# ===========================================================================
# extract_confidence_from_fields
# ===========================================================================

class TestExtractConfidence:

    def test_scalar_fields(self):
        fields = {
            "Name": {"type": "string", "valueString": "Alice", "confidence": 0.95},
            "Total": {"type": "number", "valueNumber": 100, "confidence": 0.8},
        }
        result = extract_confidence_from_fields(fields)
        assert result == {"Name": 0.95, "Total": 0.8}

    def test_nested_object(self):
        fields = {
            "TotalAmount": {
                "type": "object",
                "valueObject": {
                    "Net": {"type": "number", "valueNumber": 80, "confidence": 0.9},
                    "Tax": {"type": "number", "valueNumber": 20, "confidence": 0.85},
                },
                "confidence": 0.88,
            }
        }
        result = extract_confidence_from_fields(fields)
        assert "TotalAmount.Net" in result
        assert "TotalAmount.Tax" in result
        assert result["TotalAmount.Net"] == 0.9

    def test_missing_confidence(self):
        fields = {
            "Name": {"type": "string", "valueString": "Alice"},
        }
        result = extract_confidence_from_fields(fields)
        assert result == {}

    def test_array_field(self):
        fields = {
            "Items": {"type": "array", "valueArray": [{"a": 1}], "confidence": 0.9},
        }
        result = extract_confidence_from_fields(fields)
        assert result == {"Items": 0.9}

    def test_empty_fields(self):
        assert extract_confidence_from_fields({}) == {}

    def test_non_dict_values_skipped(self):
        fields = {"raw": "just a string", "num": 42}
        assert extract_confidence_from_fields(fields) == {}


# ===========================================================================
# extract_all_confidences
# ===========================================================================

class TestExtractAllConfidences:

    def test_simple_result(self):
        results = [{
            "result": {"fields": {
                "A": {"valueString": "x", "confidence": 0.9},
                "B": {"valueNumber": 1, "confidence": 0.7},
            }}
        }]
        confs = extract_all_confidences(results)
        assert len(confs) == 1
        assert confs[0] == {"A": 0.9, "B": 0.7}

    def test_classify_and_route(self):
        results = [{
            "result": {"contents": [
                {"category": "invoice", "fields": {"Num": {"valueString": "1", "confidence": 0.95}}},
                {"category": "receipt", "fields": {"Amt": {"valueNumber": 50, "confidence": 0.8}}},
            ]}
        }]
        confs = extract_all_confidences(results)
        assert len(confs) == 2
        assert confs[0] == {"invoice.Num": 0.95}
        assert confs[1] == {"receipt.Amt": 0.8}

    def test_no_fields(self):
        results = [{"result": {}}]
        assert extract_all_confidences(results) == []


# ===========================================================================
# _discover_cu_fields
# ===========================================================================

class TestDiscoverCuFields:

    def test_simple_fields(self):
        fields = {
            "Name": {"type": "string", "valueString": "Alice", "confidence": 0.9},
            "Age": {"type": "number", "valueNumber": 30},
        }
        names = _discover_cu_fields(fields)
        assert sorted(names) == ["Age", "Name"]

    def test_nested_object(self):
        fields = {
            "Total": {
                "type": "object",
                "valueObject": {
                    "Net": {"type": "number", "valueNumber": 80},
                    "Tax": {"type": "number", "valueNumber": 20},
                },
            }
        }
        names = _discover_cu_fields(fields)
        assert "Total" in names
        assert "Total.Net" in names
        assert "Total.Tax" in names


# ===========================================================================
# diagnose_fields
# ===========================================================================

class TestDiagnoseFields:

    def _make_results(self, field_confidences_list):
        """Helper: create results from list of {field: confidence} dicts."""
        results = []
        for conf_map in field_confidences_list:
            fields = {}
            for name, conf in conf_map.items():
                fields[name] = {"type": "string", "valueString": "x", "confidence": conf}
            results.append({"result": {"fields": fields}})
        return results

    def test_healthy_fields(self):
        results = self._make_results([
            {"A": 0.95, "B": 0.9},
            {"A": 0.92, "B": 0.88},
            {"A": 0.97, "B": 0.91},
        ])
        diagnostics = diagnose_fields(results, ["A", "B"], {"A": 100.0, "B": 100.0})
        for d in diagnostics:
            assert d["severity"] == "ok"
            assert d["suggestions"] == []

    def test_low_confidence_flagged(self):
        results = self._make_results([
            {"A": 0.5, "B": 0.9},
            {"A": 0.6, "B": 0.85},
        ])
        diagnostics = diagnose_fields(results, ["A", "B"], {"A": 100.0, "B": 100.0})
        a_diag = next(d for d in diagnostics if d["field"] == "A")
        assert a_diag["severity"] == "warning"
        assert any("confidence" in s.lower() for s in a_diag["suggestions"])

    def test_low_fill_rate_flagged(self):
        results = [
            {"result": {"fields": {"A": {"type": "string", "valueString": "x", "confidence": 0.9}, "B": {"type": "string", "valueString": "y", "confidence": 0.9}}}},
            {"result": {"fields": {"B": {"type": "string", "valueString": "y", "confidence": 0.9}}}},
            {"result": {"fields": {"B": {"type": "string", "valueString": "y", "confidence": 0.9}}}},
        ]
        diagnostics = diagnose_fields(results, ["A", "B"], {"A": 33.3, "B": 100.0})
        a_diag = next(d for d in diagnostics if d["field"] == "A")
        assert a_diag["severity"] == "critical"

    def test_sorted_by_severity(self):
        results = self._make_results([
            {"Critical": 0.3, "Warning": 0.65, "OK": 0.95},
        ])
        diagnostics = diagnose_fields(
            results, ["Critical", "Warning", "OK"],
            {"Critical": 100.0, "Warning": 100.0, "OK": 100.0}
        )
        assert diagnostics[0]["field"] == "Critical"
        assert diagnostics[0]["severity"] == "critical"


# ===========================================================================
# Utility functions
# ===========================================================================

class TestUtilities:

    def test_median_odd(self):
        assert _median([1, 2, 3]) == 2

    def test_median_even(self):
        assert _median([1, 2, 3, 4]) == 2.5

    def test_median_single(self):
        assert _median([5]) == 5

    def test_median_empty(self):
        assert _median([]) == 0.0

    def test_stdev_normal(self):
        result = _stdev([1.0, 2.0, 3.0, 4.0, 5.0])
        assert result is not None
        assert abs(result - 1.5811) < 0.001

    def test_stdev_too_few(self):
        assert _stdev([1.0]) is None
        assert _stdev([]) is None
