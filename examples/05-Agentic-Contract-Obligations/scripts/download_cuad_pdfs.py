"""Download the original CUAD PDFs for the deterministic evaluation selection."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_MANIFEST = PROJECT_DIR / "dataset" / "cuad_pdf_manifest.json"
DEFAULT_SELECTION_MANIFEST = PROJECT_DIR / "dataset" / "selection_manifest.json"
DEFAULT_OUTPUT = PROJECT_DIR / "samples" / "downloaded-pdf"
HF_API_BASE = "https://huggingface.co/api/datasets"
HF_RESOLVE_BASE = "https://huggingface.co/datasets"
USER_AGENT = "CU-Tools-CUAD-PDF-downloader/1.0"


def _read_json_url(url: str) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


def _normalized_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def match_pdf_path(original_document_id: str, pdf_paths: list[str]) -> str:
    """Resolve a CUAD title to exactly one original PDF path."""
    expected = _normalized_name(original_document_id)
    exact = [
        path
        for path in pdf_paths
        if _normalized_name(Path(path).stem) == expected
    ]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        raise ValueError(
            f"Multiple exact PDF matches for {original_document_id!r}: {exact}"
        )

    # One CUAD title omits a secondary agreement label present in its PDF name.
    prefixed = [
        path
        for path in pdf_paths
        if _normalized_name(Path(path).stem).startswith(expected)
    ]
    if len(prefixed) == 1:
        return prefixed[0]
    raise ValueError(
        f"Expected one PDF match for {original_document_id!r}, found {prefixed}"
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download_pdf(url: str, destination: Path, force: bool) -> None:
    if destination.exists() and not force:
        if destination.read_bytes()[:5] != b"%PDF-":
            raise ValueError(f"Existing file is not a PDF: {destination}")
        return

    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    temporary = destination.with_suffix(".pdf.part")
    temporary.unlink(missing_ok=True)
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            with temporary.open("wb") as stream:
                while chunk := response.read(1024 * 1024):
                    stream.write(chunk)
        if temporary.read_bytes()[:5] != b"%PDF-":
            raise ValueError(f"Downloaded content is not a PDF: {url}")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def download_selection(
    source_manifest_path: Path,
    selection_manifest_path: Path,
    output_dir: Path,
    split: str = "held_out",
    force: bool = False,
) -> dict[str, Any]:
    source = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    selection = json.loads(selection_manifest_path.read_text(encoding="utf-8"))
    repository_id = "theatticusproject/cuad"
    revision = source["revision"]
    pdf_root = source["pdf_root"]
    tree_url = (
        f"{HF_API_BASE}/{repository_id}/tree/{revision}/"
        f"{urllib.parse.quote(pdf_root, safe='/')}?recursive=true&"
        "expand=false&limit=1000"
    )
    tree = _read_json_url(tree_url)
    pdf_paths = sorted(
        item["path"]
        for item in tree
        if item.get("type") == "file"
        and str(item.get("path", "")).lower().endswith(".pdf")
    )
    if len(pdf_paths) != int(source["expected_pdf_count"]):
        raise ValueError(
            f"Expected {source['expected_pdf_count']} PDFs at {revision}, "
            f"found {len(pdf_paths)}"
        )

    documents = [
        document
        for document in selection["documents"]
        if split == "all" or document["split"] == split
    ]
    output_dir.mkdir(parents=True, exist_ok=True)
    downloaded = []
    for document in documents:
        source_path = match_pdf_path(
            document["original_document_id"],
            pdf_paths,
        )
        encoded_path = urllib.parse.quote(source_path, safe="/")
        source_url = (
            f"{HF_RESOLVE_BASE}/{repository_id}/resolve/"
            f"{revision}/{encoded_path}?download=true"
        )
        destination = output_dir / f"{document['doc_id']}.pdf"
        _download_pdf(source_url, destination, force)
        downloaded.append(
            {
                "doc_id": document["doc_id"],
                "split": document["split"],
                "original_document_id": document["original_document_id"],
                "source_path": source_path,
                "source_revision": revision,
                "source_url": source_url,
                "size_bytes": destination.stat().st_size,
                "sha256": _sha256_file(destination),
            }
        )

    result = {
        "dataset": source["dataset"],
        "repository": source["repository"],
        "revision": revision,
        "license": source["license"],
        "split": split,
        "document_count": len(downloaded),
        "documents": downloaded,
    }
    (output_dir / "download_manifest.json").write_text(
        json.dumps(result, indent=2) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-manifest",
        type=Path,
        default=DEFAULT_SOURCE_MANIFEST,
    )
    parser.add_argument(
        "--selection-manifest",
        type=Path,
        default=DEFAULT_SELECTION_MANIFEST,
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--split",
        choices=("development", "held_out", "all"),
        default="held_out",
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    result = download_selection(
        args.source_manifest.resolve(),
        args.selection_manifest.resolve(),
        args.output.resolve(),
        split=args.split,
        force=args.force,
    )
    print(
        f"Verified {result['document_count']} {result['split']} PDFs at "
        f"{args.output.resolve()}"
    )


if __name__ == "__main__":
    main()
