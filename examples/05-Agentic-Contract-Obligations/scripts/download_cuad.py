"""Download and safely extract the pinned CUAD archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath

PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = PROJECT_DIR / "dataset" / "cuad_manifest.json"
DEFAULT_OUTPUT = PROJECT_DIR / "dataset" / "raw"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_member(name: str, allowed: set[str]) -> None:
    normalized = PurePosixPath(name)
    windows_path = PureWindowsPath(name)
    if (
        normalized.is_absolute()
        or windows_path.is_absolute()
        or bool(windows_path.drive)
        or ".." in normalized.parts
        or "\\" in name
        or name not in allowed
    ):
        raise ValueError(f"Unsafe or unexpected archive member: {name}")


def safe_extract(archive_path: Path, output_dir: Path, allowed: set[str]) -> None:
    output_dir = output_dir.resolve()
    with zipfile.ZipFile(archive_path) as archive:
        names = {item.filename for item in archive.infolist() if not item.is_dir()}
        unexpected = names - allowed
        missing = allowed - names
        if unexpected or missing:
            raise ValueError(
                f"Archive contents differ from manifest; unexpected={sorted(unexpected)}, "
                f"missing={sorted(missing)}"
            )
        for member in archive.infolist():
            if member.is_dir():
                continue
            _validate_member(member.filename, allowed)
            target = (output_dir / member.filename).resolve()
            try:
                target.relative_to(output_dir)
            except ValueError as exc:
                raise ValueError(
                    f"Archive member escapes output directory: {member.filename}"
                ) from exc
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, target.open("wb") as destination:
                shutil.copyfileobj(source, destination)


def download(manifest_path: Path, output_dir: Path, force: bool = False) -> Path:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = output_dir / "data.zip"

    if force or not archive_path.exists():
        request = urllib.request.Request(
            manifest["archive_url"],
            headers={"User-Agent": "CU-Tools-CUAD-downloader/1.0"},
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            with archive_path.open("wb") as destination:
                shutil.copyfileobj(response, destination)

    actual_hash = sha256_file(archive_path)
    expected_hash = manifest["archive_sha256"].lower()
    if actual_hash.lower() != expected_hash:
        archive_path.unlink(missing_ok=True)
        raise ValueError(
            f"CUAD archive checksum mismatch: expected {expected_hash}, got {actual_hash}"
        )

    safe_extract(
        archive_path,
        output_dir,
        set(manifest["allowed_archive_entries"]),
    )
    return output_dir / "CUADv1.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    dataset_path = download(args.manifest.resolve(), args.output.resolve(), args.force)
    print(f"Verified CUAD dataset: {dataset_path}")


if __name__ == "__main__":
    main()
