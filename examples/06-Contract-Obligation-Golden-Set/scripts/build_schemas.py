"""Build paired Standard and Agentic schemas from the proven obligation template."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parents[1]
SOURCE_SCHEMA = (
    PROJECT_DIR.parent
    / "05-Agentic-Contract-Obligations"
    / "schemas"
    / "contract_obligations_agentic_v1.json"
)
SCHEMA_DIR = PROJECT_DIR / "schemas"
STANDARD_SCHEMA = SCHEMA_DIR / "contract_obligations_standard_v1.json"
AGENTIC_SCHEMA = SCHEMA_DIR / "contract_obligations_agentic_v1.json"


def build_schema_pair(source: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    agentic = copy.deepcopy(source)
    standard = copy.deepcopy(source)

    agentic["description"] = (
        "Agentic benchmark variant. " + source["description"]
    )
    agentic["models"] = {"completion": "gpt-5.2"}
    agentic.setdefault("config", {})["workflow"] = "Agentic"

    standard["description"] = (
        "Standard benchmark variant. " + source["description"]
    )
    standard["models"] = {"completion": "gpt-4.1"}
    standard.setdefault("config", {}).pop("workflow", None)

    if standard["fieldSchema"] != agentic["fieldSchema"]:
        raise AssertionError("Benchmark schemas must have identical field schemas")
    return standard, agentic


def write_schemas() -> tuple[Path, Path]:
    source = json.loads(SOURCE_SCHEMA.read_text(encoding="utf-8"))
    standard, agentic = build_schema_pair(source)
    SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
    STANDARD_SCHEMA.write_text(
        json.dumps(standard, indent=2) + "\n",
        encoding="utf-8",
    )
    AGENTIC_SCHEMA.write_text(
        json.dumps(agentic, indent=2) + "\n",
        encoding="utf-8",
    )
    return STANDARD_SCHEMA, AGENTIC_SCHEMA


if __name__ == "__main__":
    paths = write_schemas()
    print("Wrote paired schemas:")
    for path in paths:
        print(f"- {path}")
