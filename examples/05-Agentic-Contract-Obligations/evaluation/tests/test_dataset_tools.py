"""Tests for CUAD safety, deterministic selection, and CU normalization."""

from __future__ import annotations

import importlib.util
import json
import zipfile
from pathlib import Path

import pytest

PROJECT_DIR = Path(__file__).resolve().parents[2]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


download = _load("download_cuad", PROJECT_DIR / "scripts" / "download_cuad.py")
download_pdfs = _load(
    "download_cuad_pdfs",
    PROJECT_DIR / "scripts" / "download_cuad_pdfs.py",
)
prepare = _load("prepare_cuad", PROJECT_DIR / "scripts" / "prepare_cuad_eval.py")
normalizer = _load(
    "normalize_cu",
    PROJECT_DIR
    / "evaluation"
    / "preprocessors"
    / "contract_obligations"
    / "normalize_cu_results.py",
)
viewer = _load(
    "build_grounding_viewer",
    PROJECT_DIR / "scripts" / "build_grounding_viewer.py",
)
clause_benchmark = _load(
    "prepare_clause_span_benchmark",
    PROJECT_DIR / "scripts" / "prepare_clause_span_benchmark.py",
)
clause_report = _load(
    "generate_clause_span_report",
    PROJECT_DIR / "evaluation" / "generate_clause_span_report.py",
)


def test_safe_extract_rejects_path_traversal(tmp_path):
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as stream:
        stream.writestr("../escape.json", "{}")
    with pytest.raises(ValueError):
        download.safe_extract(archive, tmp_path / "out", {"CUADv1.json"})


def test_safe_extract_rejects_windows_drive_path(tmp_path):
    archive = tmp_path / "unsafe-drive.zip"
    with zipfile.ZipFile(archive, "w") as stream:
        stream.writestr("C:/escape.json", "{}")
    with pytest.raises(ValueError):
        download.safe_extract(archive, tmp_path / "out", {"C:/escape.json"})


def test_selection_is_reproducible():
    mapping = {"Audit Rights": "Audit/Access"}
    records = []
    for index in range(4):
        records.append(
            {
                "title": f"contract-{index}",
                "paragraphs": [
                    {
                        "context": f"Agreement {index}: audit allowed.",
                        "qas": [
                            {
                                "question": 'Highlight parts related to "Audit Rights"',
                                "answers": [{"text": "audit allowed", "answer_start": 13}],
                            }
                        ],
                    }
                ],
            }
        )
    first = prepare.select_records(records, mapping, 3, "seed")
    second = prepare.select_records(records, mapping, 3, "seed")
    assert [item[0]["title"] for item in first] == [
        item[0]["title"] for item in second
    ]


def test_pdf_match_prefers_normalized_exact_title():
    paths = [
        "CUAD_v1/full_contract_pdf/Part_I/Example Agreement.pdf",
        "CUAD_v1/full_contract_pdf/Part_I/Example Agreement Appendix.pdf",
    ]
    assert (
        download_pdfs.match_pdf_path("Example Agreement", paths)
        == paths[0]
    )


def test_pdf_match_allows_one_source_title_suffix():
    paths = [
        "CUAD_v1/full_contract_pdf/Part_I/Example Agreement_Option Agreement.pdf"
    ]
    assert (
        download_pdfs.match_pdf_path("Example Agreement", paths)
        == paths[0]
    )


def test_pdf_match_rejects_ambiguous_source_title():
    paths = [
        "CUAD_v1/full_contract_pdf/Part_I/Example Agreement_First.pdf",
        "CUAD_v1/full_contract_pdf/Part_I/Example Agreement_Second.pdf",
    ]
    with pytest.raises(ValueError, match="Expected one PDF match"):
        download_pdfs.match_pdf_path("Example Agreement", paths)


def test_native_cu_fields_are_unwrapped():
    raw = {
        "result": {
            "contents": [
                {
                    "fields": {
                        "Parties": {
                            "valueArray": [
                                {
                                    "valueObject": {
                                        "PartyId": {"valueString": "P1"},
                                    }
                                }
                            ]
                        },
                        "Obligations": {"valueArray": []},
                    }
                }
            ]
        }
    }
    result = normalizer.canonicalize_result(raw, "doc-1")
    assert result["doc_id"] == "doc-1"
    assert result["parties"] == [{"PartyId": "P1"}]
    assert result["obligations"] == []


def test_grounding_viewer_parses_source_polygon():
    parsed = viewer.parse_source("D(3,1.0,2.0,3.0,2.0,3.0,2.5,1.0,2.5)")

    assert parsed == (3, [1.0, 2.0, 3.0, 2.0, 3.0, 2.5, 1.0, 2.5])


def test_grounding_viewer_locates_quote_across_word_boxes():
    pages = [
        {
            "words": [
                {
                    "content": "Tenant",
                    "source": "D(2,1.0,1.0,1.5,1.0,1.5,1.2,1.0,1.2)",
                },
                {
                    "content": "must",
                    "source": "D(2,1.6,1.0,2.0,1.0,2.0,1.2,1.6,1.2)",
                },
                {
                    "content": "pay.",
                    "source": "D(2,2.1,1.0,2.5,1.0,2.5,1.2,2.1,1.2)",
                },
            ]
        }
    ]
    words, positions = viewer.build_word_index(pages)

    rectangles = viewer.locate_quote("Tenant must pay.", words, positions)

    assert rectangles == [
        {"page": 2, "x": 1.0, "y": 1.0, "width": 1.5, "height": 0.2}
    ]


def test_grounding_viewer_removes_stale_assets(tmp_path):
    stale_file = tmp_path / "assets" / "private-contract" / "source.pdf"
    stale_file.parent.mkdir(parents=True)
    stale_file.write_bytes(b"private")

    viewer.prepare_output_dir(tmp_path)

    assert not stale_file.exists()
    assert tmp_path.exists()


def test_clause_span_selection_is_deterministic_and_held_out():
    gold = {
        "a": {"clauses": [{"category": "One"}]},
        "b": {"clauses": [{"category": "Two"}]},
        "c": {"clauses": [{"category": "One"}, {"category": "Two"}]},
    }
    documents = [
        {"doc_id": "a", "split": "held_out"},
        {"doc_id": "b", "split": "development"},
        {"doc_id": "c", "split": "held_out"},
    ]

    first = clause_benchmark.select_documents(documents, gold, 2)
    second = clause_benchmark.select_documents(documents, gold, 2)

    assert first == second
    assert {item["doc_id"] for item in first} == {"a", "c"}


def test_clause_span_matching_is_category_aware():
    predicted = ["Tenant shall maintain insurance."]
    expected = ["Tenant shall maintain insurance coverage."]

    matches = clause_report.match_spans(predicted, expected, 0.55)

    assert len(matches) == 1
    assert matches[0][2] >= 0.55


def test_atomic_coverage_requires_verified_annotations(tmp_path):
    manifest = tmp_path / "selection.json"
    manifest.write_text(
        json.dumps({"atomic_annotation_doc_ids": ["doc-1", "doc-2"]}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="missing"):
        _load(
            "build_evallens",
            PROJECT_DIR / "scripts" / "build_evallens_dataset.py",
        ).validate_atomic_coverage(
            manifest,
            {"doc-1": {"doc_id": "doc-1", "review_status": "verified"}},
        )
