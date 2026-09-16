"""Materialize the curated ten-contract golden-set inputs from a pinned CUAD copy."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = (
    PROJECT_DIR.parent
    / "05-Agentic-Contract-Obligations"
    / "dataset"
    / "raw"
    / "CUADv1.json"
)
DEFAULT_MANIFEST = PROJECT_DIR / "dataset" / "selection_manifest.json"
DEFAULT_OUTPUT = PROJECT_DIR / "samples" / "downloaded"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_records(dataset_path: Path) -> dict[str, dict[str, Any]]:
    payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    records = payload.get("data")
    if not isinstance(records, list):
        raise ValueError(f"CUAD dataset has no data array: {dataset_path}")
    return {
        record["title"]: record
        for record in records
        if isinstance(record, dict) and isinstance(record.get("title"), str)
    }


def prepare_dataset(
    dataset_path: Path,
    manifest_path: Path = DEFAULT_MANIFEST,
    output_dir: Path = DEFAULT_OUTPUT,
    clean: bool = False,
    manifest_output: Path | None = None,
) -> dict[str, Any]:
    if not dataset_path.is_file():
        raise FileNotFoundError(
            f"CUAD dataset not found: {dataset_path}. Run the example 05 downloader first."
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_hash = manifest["source_file_sha256"]
    actual_hash = sha256_file(dataset_path)
    if actual_hash != expected_hash:
        raise ValueError(
            f"CUAD checksum mismatch: expected {expected_hash}, got {actual_hash}"
        )

    records = load_records(dataset_path)
    if clean:
        shutil.rmtree(output_dir, ignore_errors=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    materialized = []
    for document in manifest["documents"]:
        title = document["original_document_id"]
        if title not in records:
            raise ValueError(f"Selected CUAD document is missing: {title}")
        paragraphs = records[title].get("paragraphs", [])
        if not paragraphs or not isinstance(paragraphs[0].get("context"), str):
            raise ValueError(f"Selected CUAD document has no source text: {title}")
        source_text = paragraphs[0]["context"]
        word_count = len(source_text.split())
        if word_count != document["expected_words"]:
            raise ValueError(
                f"Word-count drift for {document['doc_id']}: "
                f"expected {document['expected_words']}, got {word_count}"
            )
        output_path = output_dir / f"{document['doc_id']}.txt"
        output_path.write_text(source_text, encoding="utf-8", newline="\n")
        materialized.append(
            {
                "doc_id": document["doc_id"],
                "path": str(output_path),
                "characters": len(source_text),
                "words": word_count,
                "sha256": hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
            }
        )

    output_manifest = {
        "selection_version": manifest["selection_version"],
        "source_revision": manifest["source_revision"],
        "documents": materialized,
    }
    manifest_output = manifest_output or output_dir / "materialized_manifest.json"
    manifest_output.parent.mkdir(parents=True, exist_ok=True)
    manifest_output.write_text(
        json.dumps(output_manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--clean", action="store_true")
    parser.add_argument(
        "--manifest-output", type=Path,
        help="Write provenance outside --output to keep native CLI source directories input-only",
    )
    args = parser.parse_args()
    result = prepare_dataset(
        args.dataset.resolve(),
        args.manifest.resolve(),
        args.output.resolve(),
        clean=args.clean,
        manifest_output=args.manifest_output.resolve() if args.manifest_output else None,
    )
    print(f"Prepared {len(result['documents'])} contracts in {args.output.resolve()}")


if __name__ == "__main__":
    main()
