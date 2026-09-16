"""Offline coverage for dependency-ordered analyzer schema plans."""

import hashlib
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

import pytest

MODULE = Path(__file__).resolve().parents[1] / "schema_plan.py"
spec = importlib.util.spec_from_file_location("schema_plan", MODULE)
assert spec and spec.loader
planner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(planner)


def schema(base="prebuilt-document"):
    return {
        "description": "Extract invoice fields from the supplied document text.",
        "baseAnalyzerId": base,
        "fieldSchema": {"fields": {
            "InvoiceNumber": {
                "type": "string", "method": "extract",
                "description": "The invoice identifier next to Invoice Number or Invoice No.",
            }
        }},
    }


def write_schema(tmp_path, name, payload):
    path = tmp_path / f"{name}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_routes_are_patched_without_changing_originals(tmp_path):
    inner = write_schema(tmp_path, "invoice", schema())
    outer_payload = {
        "baseAnalyzerId": "prebuilt-document",
        "config": {
            "enableSegment": True,
            "contentCategories": {
                "invoice": {
                    "description": "A document with an invoice heading and line items.",
                    "analyzerId": "invoice",
                },
                "other": {"description": "A document without invoice-related text."},
            },
        },
    }
    outer = write_schema(tmp_path, "packet", outer_payload)
    original = outer.read_bytes()
    output = tmp_path / "plan"
    with patch("socket.socket", side_effect=AssertionError("Network is forbidden")):
        plan = planner.build_plan(
            {"packet": outer, "invoice": inner}, id_prefix="trial01", output=output,
        )
    assert plan["creation_order"] == ["trial01_invoice", "trial01_packet"]
    assert plan["root_analyzers"] == ["trial01_packet"]
    assert plan["service_checked"] is False
    assert outer.read_bytes() == original
    snapshot = json.loads((output / "trial01_packet.json").read_text())
    categories = snapshot["config"]["contentCategories"]
    assert categories["invoice"]["analyzerId"] == "trial01_invoice"
    assert "analyzerId" not in categories["other"]
    assert plan["commands"]["create"][0][:5] == [
        "cu", "analyzer", "create", "--name", "trial01_invoice",
    ]
    assert plan["commands"]["delete"][0][4] == "trial01_packet"
    assert "--yes" not in plan["commands"]["delete"][0]
    for item in plan["analyzers"]:
        assert hashlib.sha256((output / item["schema"]).read_bytes()).hexdigest() == item["sha256"]


def test_base_dependencies_are_ordered_and_remapped(tmp_path):
    base = write_schema(tmp_path, "base", schema())
    child = write_schema(tmp_path, "child", schema("base"))
    plan = planner.build_plan(
        {"child": child, "base": base}, id_prefix="v2", output=tmp_path / "out",
    )
    assert plan["creation_order"] == ["v2_base", "v2_child"]
    payload = json.loads((tmp_path / "out" / "v2_child.json").read_text())
    assert payload["baseAnalyzerId"] == "v2_base"


def test_cycles_fail_without_output(tmp_path):
    a = write_schema(tmp_path, "a", schema("b"))
    b = write_schema(tmp_path, "b", schema("a"))
    with pytest.raises(ValueError, match="Circular"):
        planner.build_plan({"a": a, "b": b}, id_prefix="cycle", output=tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_external_dependency_must_be_explicit(tmp_path):
    path = write_schema(tmp_path, "child", schema("existing_base"))
    with pytest.raises(ValueError, match="unresolved"):
        planner.build_plan({"child": path}, id_prefix="v2", output=tmp_path / "out")
    plan = planner.build_plan(
        {"child": path}, id_prefix="v2", output=tmp_path / "out",
        external={"existing_base"},
    )
    assert "existing_base" in plan["external_analyzers"]


def test_existing_output_is_never_overwritten(tmp_path):
    path = write_schema(tmp_path, "a", schema())
    output = tmp_path / "existing"
    output.mkdir()
    marker = output / "keep.txt"
    marker.write_text("keep")
    with pytest.raises(ValueError, match="already exists"):
        planner.build_plan({"a": path}, id_prefix="v2", output=output)
    assert marker.read_text() == "keep"


@pytest.mark.parametrize("prefix", ["../outside", "with-hyphen", "x" * 64, ""])
def test_invalid_generated_ids_fail_before_writes(tmp_path, prefix):
    path = write_schema(tmp_path, "a", schema())
    with pytest.raises(ValueError):
        planner.build_plan({"a": path}, id_prefix=prefix, output=tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_alias_collision_is_rejected_on_all_platforms(tmp_path):
    path = write_schema(tmp_path, "a", schema())
    with pytest.raises(ValueError, match="Duplicate"):
        planner.parse_schemas([f"Invoice={path}", f"invoice={path}"])


def test_invalid_schema_and_json_fail_before_writes(tmp_path):
    path = write_schema(tmp_path, "a", {"config": []})
    with pytest.raises(ValueError):
        planner.build_plan({"a": path}, id_prefix="v2", output=tmp_path / "out")
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError):
        planner.build_plan({"a": path}, id_prefix="v2", output=tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_preview_contract_and_profile_are_explicit(tmp_path):
    payload = schema()
    payload["config"] = {"workflow": "Agentic"}
    path = write_schema(tmp_path, "agentic", payload)
    with pytest.raises(ValueError, match="preview API"):
        planner.build_plan({"agentic": path}, id_prefix="v2", output=tmp_path / "out")
    plan = planner.build_plan(
        {"agentic": path}, id_prefix="v2", output=tmp_path / "out",
        api_version="2026-06-01-preview", profile="dev",
    )
    assert plan["commands"]["create"][0][-4:] == [
        "--api-version", "2026-06-01-preview", "--profile", "dev",
    ]


def test_cli_reports_errors_without_claiming_execution(tmp_path, capsys):
    rc = planner.main([
        "--schema", f"a={tmp_path / 'missing.json'}",
        "--id-prefix", "v2", "--output", str(tmp_path / "out"),
    ])
    assert rc == 1
    assert "Error:" in capsys.readouterr().err
