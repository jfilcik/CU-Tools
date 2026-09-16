import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TOOLS = Path(__file__).resolve().parents[2]
reading = load_module("reading_order", TOOLS / "cu-reading-order-viz" / "visualize_reading_order.py")
segments = load_module("segment_view", TOOLS / "cu-segment-visualizer" / "visualize_segments.py")


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.mark.parametrize("wrapped", [False, True])
def test_reading_all_native_or_legacy_contents(tmp_path, wrapped):
    data = {"contents": [
        {"pages": [{"pageNumber": page, "width": 8.5, "height": 11}],
         "paragraphs": [{"content": f"Page {page}", "source": f"D({page},1,1,2,1,2,2,1,2)"}]}
        for page in [1, 2]
    ]}
    path = write_json(tmp_path / "doc.pdf.result.json", {"result": data} if wrapped else data)
    assert reading.detect_format(path) == "cu"
    pages, paragraphs = reading.extract_paragraphs(path)
    assert set(pages) == {1, 2}
    assert paragraphs[2][0]["idx"] == 1
    assert paragraphs[1][0]["content"] == "Page 1"


def test_reading_di_stays_supported(tmp_path):
    path = write_json(tmp_path / "di.json", {"analyzeResult": {
        "pages": [{"pageNumber": 1, "width": 8.5, "height": 11}],
        "paragraphs": [{"content": "Hello", "boundingRegions": [
            {"pageNumber": 1, "polygon": [1, 1, 2, 1, 2, 2, 1, 2]}
        ]}],
    }})
    assert reading.detect_format(path) == "di"
    assert reading.extract_paragraphs(path)[1][1][0]["content"] == "Hello"


@pytest.mark.parametrize("data", [{}, [], {"contents": {}}, {"contents": [None]}])
def test_invalid_layout_fails(tmp_path, data):
    path = write_json(tmp_path / "bad.result.json", data)
    with pytest.raises(ValueError):
        reading.extract_paragraphs(path)


def test_native_batch_preserves_nested_duplicate_names(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(reading, "create_visualization_pdf", lambda *args, **kwargs: calls.append(args))
    for folder in ["a", "b"]:
        pdf = tmp_path / "inputs" / folder / "doc.pdf"
        pdf.parent.mkdir(parents=True)
        pdf.write_bytes(b"stub")
        write_json(tmp_path / "results" / folder / "doc.pdf.result.json", {"contents": []})
    reading.process_batch(tmp_path / "inputs", tmp_path / "results", tmp_path / "out")
    assert len(calls) == 2
    assert {call[2].relative_to(tmp_path / "out").as_posix() for call in calls} == {
        "a/doc_reading_order.pdf", "b/doc_reading_order.pdf"
    }


def test_ambiguous_layout_rejected(tmp_path, monkeypatch):
    (tmp_path / "doc.pdf").write_bytes(b"stub")
    write_json(tmp_path / "results" / "doc.pdf.result.json", {"contents": []})
    write_json(tmp_path / "results" / "doc.json", {"contents": []})
    with pytest.raises(ValueError, match="Ambiguous"):
        reading.process_batch(tmp_path, tmp_path / "results", tmp_path / "out")


@pytest.mark.parametrize("wrapped", [False, True])
def test_native_classification_segments(wrapped):
    data = {"contents": [
        {"category": "invoice", "startPageNumber": 1, "endPageNumber": 2},
        {"category": "receipt", "startPageNumber": 3, "endPageNumber": 3},
    ]}
    result = segments.load_segments({"result": data} if wrapped else data)
    assert len(result) == 2
    assert segments.build_page_map(result)[3]["category"] == "receipt"


def test_legacy_nested_segments():
    expected = {"category": "invoice", "segmentId": "1", "startPageNumber": 1, "endPageNumber": 1}
    assert segments.load_segments({"result": {"contents": [{"segments": [expected]}]}}) == [expected]


@pytest.mark.parametrize("data", [
    {}, {"contents": []}, {"contents": [{"segments": {}}]},
    {"contents": [{"category": "invoice"}]},
    {"contents": [{"segments": [{"startPageNumber": True, "endPageNumber": 2}]}]},
])
def test_missing_or_invalid_segments_fail(data):
    with pytest.raises(ValueError):
        segments.load_segments(data)


def test_render_native_layout_and_segments(tmp_path):
    pdf = tmp_path / "source.pdf"
    with reading.fitz.open() as document:
        page = document.new_page(width=612, height=792)
        page.insert_text((72, 72), "Synthetic invoice")
        document.save(pdf)
    result = write_json(tmp_path / "source.pdf.result.json", {"contents": [{
        "category": "invoice", "startPageNumber": 1, "endPageNumber": 1,
        "pages": [{"pageNumber": 1, "width": 8.5, "height": 11}],
        "paragraphs": [{"content": "Synthetic invoice", "source": "D(1,1,1,2,1,2,2,1,2)"}],
    }]})
    layout_pdf = tmp_path / "layout.pdf"
    reading.create_visualization_pdf(pdf, result, layout_pdf)
    segment_pdf = tmp_path / "segments.pdf"
    segments.annotate_pdf(str(pdf), str(result), str(segment_pdf))
    with reading.fitz.open(layout_pdf) as rendered:
        assert rendered.page_count == 1
    with reading.fitz.open(segment_pdf) as rendered:
        assert rendered.page_count >= 2
        assert "invoice" in rendered[0].get_text()


@pytest.mark.parametrize("tool", ["cu-reading-order-viz", "cu-segment-visualizer"])
def test_cli_redirected_output_is_utf8(tmp_path, tool):
    pdf = tmp_path / "source.pdf"
    with reading.fitz.open() as document:
        document.new_page()
        document.save(pdf)
    result = write_json(tmp_path / "source.pdf.result.json", {"contents": [{
        "category": "invoice", "startPageNumber": 1, "endPageNumber": 1,
        "pages": [{"pageNumber": 1, "width": 8.5, "height": 11}],
        "paragraphs": [],
    }]})
    if tool == "cu-reading-order-viz":
        arguments = [str(TOOLS / tool / "visualize_reading_order.py"), "--pdf", str(pdf),
                     "--layout", str(result), "--output", str(tmp_path / "out")]
    else:
        arguments = [str(TOOLS / tool / "visualize_segments.py"), "--pdf", str(pdf),
                     "--results", str(result), "--output", str(tmp_path / "annotated.pdf")]
    run = subprocess.run(
        [sys.executable, *arguments], env={**os.environ, "PYTHONIOENCODING": "cp1252"},
        stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8",
        check=False,
    )
    assert run.returncode == 0, run.stderr
