"""Normalize native Content Understanding output for contract evaluators."""

from __future__ import annotations

import json
from typing import Any, Optional, Tuple

try:
    from evallens.preprocessors import BasePreprocessor, preprocessor
except ImportError:
    BasePreprocessor = object

    def preprocessor(**_kwargs):
        return lambda cls: cls


VALUE_KEYS = (
    "valueString",
    "valueNumber",
    "valueInteger",
    "valueBoolean",
    "valueDate",
    "valueTime",
    "valueCurrency",
    "valueAddress",
    "valueCountryRegion",
)


def unwrap_field(node: Any) -> Any:
    if not isinstance(node, dict):
        return node
    if "valueArray" in node:
        return [unwrap_field(item) for item in node["valueArray"]]
    if "valueObject" in node:
        return {
            name: unwrap_field(value)
            for name, value in node["valueObject"].items()
        }
    for key in VALUE_KEYS:
        if key in node:
            return node[key]
    if "value" in node:
        return node["value"]
    return {
        name: unwrap_field(value)
        for name, value in node.items()
        if name not in {"type", "confidence", "source", "spans", "boundingRegions"}
    }


def canonicalize_result(raw: dict[str, Any], doc_id: str = "") -> dict[str, Any]:
    result = raw.get("result", raw)
    contents = result.get("contents", []) if isinstance(result, dict) else []
    content = contents[0] if contents else result
    fields = content.get("fields", {}) if isinstance(content, dict) else {}
    values = {name: unwrap_field(value) for name, value in fields.items()}
    metadata = raw.get("_metadata", {})
    return {
        "doc_id": doc_id or metadata.get("document", ""),
        "parties": values.get("Parties", []),
        "obligations": values.get("Obligations", []),
        "contract_metadata": values.get("ContractMetadata", {}),
        "run_metadata": metadata,
    }


@preprocessor(
    name="normalize_cu_results",
    description="Normalize native CU field nodes into contract prediction records",
)
class NormalizeCUResults(BasePreprocessor):
    def process(
        self,
        predictions: str,
        ground_truth: Optional[str] = None,
    ) -> Tuple[str, Optional[str]]:
        output = []
        for line in predictions.splitlines():
            if not line.strip():
                continue
            raw = json.loads(line)
            output.append(
                json.dumps(
                    canonicalize_result(raw, raw.get("doc_id", "")),
                    ensure_ascii=False,
                )
            )
        return ("\n".join(output) + "\n" if output else "", ground_truth)
