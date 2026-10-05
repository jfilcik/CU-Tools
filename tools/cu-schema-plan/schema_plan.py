"""Build an offline, dependency-ordered schema plan for the official CU CLI."""

from __future__ import annotations

import argparse
import copy
import hashlib
import heapq
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterator

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cu-analyzer-validate"))
from cu_analyzer_validator import validate_cu_analyzer

DEFAULT_API_VERSION = "2025-11-01"
CUSTOM_ID = re.compile(r"[A-Za-z0-9_]{1,64}\Z")


def parse_schemas(values: list[str]) -> dict[str, Path]:
    schemas: dict[str, Path] = {}
    seen: set[str] = set()
    for value in values:
        alias, separator, filename = value.partition("=")
        if not separator or not CUSTOM_ID.fullmatch(alias):
            raise ValueError("--schema requires ALIAS=FILE with a valid custom analyzer alias")
        if alias.casefold() in seen:
            raise ValueError(f"Duplicate schema alias: {alias}")
        path = Path(filename)
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"Schema must be a regular, non-symlink file: {path}")
        seen.add(alias.casefold())
        schemas[alias] = path.resolve()
    if not schemas:
        raise ValueError("At least one --schema ALIAS=FILE is required")
    return schemas


def references(schema: dict[str, Any]) -> Iterator[tuple[dict[str, Any], str]]:
    if "baseAnalyzerId" in schema:
        yield schema, "baseAnalyzerId"
    config = schema.get("config", {})
    if not isinstance(config, dict):
        raise ValueError("config must be an object")
    categories = config.get("contentCategories", {})
    if not isinstance(categories, dict):
        raise ValueError("config.contentCategories must be an object")
    for category, definition in categories.items():
        if not isinstance(definition, dict):
            raise ValueError(f"Category {category} must be an object")
        if "analyzerId" in definition:
            yield definition, "analyzerId"


def creation_order(dependencies: dict[str, set[str]]) -> list[str]:
    remaining = {alias: len(refs) for alias, refs in dependencies.items()}
    dependents: dict[str, list[str]] = {alias: [] for alias in dependencies}
    for alias, refs in dependencies.items():
        for ref in refs:
            dependents[ref].append(alias)
    ready = [alias for alias, count in remaining.items() if count == 0]
    heapq.heapify(ready)
    ordered: list[str] = []
    while ready:
        alias = heapq.heappop(ready)
        ordered.append(alias)
        for dependent in dependents[alias]:
            remaining[dependent] -= 1
            if remaining[dependent] == 0:
                heapq.heappush(ready, dependent)
    if len(ordered) != len(dependencies):
        cycle = sorted(alias for alias, count in remaining.items() if count)
        raise ValueError(f"Circular schema dependencies: {', '.join(cycle)}")
    return ordered


def build_plan(
    schemas: dict[str, Path],
    *,
    id_prefix: str,
    output: Path,
    api_version: str = DEFAULT_API_VERSION,
    profile: str | None = None,
    external: set[str] | None = None,
) -> dict[str, Any]:
    """Validate and snapshot schemas without importing an Azure SDK or calling CU."""
    if not CUSTOM_ID.fullmatch(id_prefix):
        raise ValueError("ID prefix must contain only ASCII letters, digits, or underscores")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:-preview)?", api_version):
        raise ValueError("API version must be YYYY-MM-DD or YYYY-MM-DD-preview")
    if profile is not None and not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", profile):
        raise ValueError("Profile must contain 1-64 ASCII letters, digits, hyphens, or underscores")
    if output.exists() or output.is_symlink():
        raise ValueError(f"Output already exists; choose a new plan directory: {output}")
    schemas = parse_schemas([f"{alias}={path}" for alias, path in schemas.items()])
    external = set(external or ())
    for name in external:
        if not CUSTOM_ID.fullmatch(name) and not re.fullmatch(r"prebuilt-[A-Za-z0-9_-]+", name):
            raise ValueError(f"Invalid external analyzer ID: {name}")
    names = {alias: f"{id_prefix}_{alias}" for alias in schemas}
    for name in names.values():
        if not CUSTOM_ID.fullmatch(name):
            raise ValueError(f"Generated analyzer ID exceeds 64 characters: {name}")
        if name.casefold() in {item.casefold() for item in external}:
            raise ValueError(f"Generated analyzer ID conflicts with an external analyzer: {name}")

    payloads: dict[str, bytes] = {}
    source_hashes: dict[str, str] = {}
    dependencies: dict[str, set[str]] = {}
    warnings: list[str] = []
    used_external: set[str] = set()
    for alias, path in schemas.items():
        source = path.read_bytes()
        source_hashes[alias] = hashlib.sha256(source).hexdigest()
        schema = json.loads(source)
        if not isinstance(schema, dict):
            raise ValueError(f"Schema must be a JSON object: {path}")
        schema = copy.deepcopy(schema)
        schema.pop("analyzerId", None)
        dependencies[alias] = set()
        for owner, key in references(schema):
            ref = owner[key]
            if not isinstance(ref, str) or not ref:
                raise ValueError(f"{alias}: {key} must be a nonempty analyzer reference")
            if ref in names:
                dependencies[alias].add(ref)
                owner[key] = names[ref]
            elif ref in external or ref.startswith("prebuilt-"):
                used_external.add(ref)
            else:
                raise ValueError(
                    f"{alias}: unresolved analyzer reference {ref!r}; supply its "
                    "--schema mapping or explicitly declare --external"
                )
        validation = validate_cu_analyzer(schema, api_version=api_version)
        if not validation.is_valid:
            errors = "\n".join(str(error) for error in validation.errors)
            raise ValueError(f"Local schema validation failed for {alias}:\n{errors}")
        warnings.extend(f"{alias}: {warning}" for warning in validation.warnings)
        payloads[alias] = (json.dumps(schema, indent=2, ensure_ascii=False) + "\n").encode("utf-8")

    order = creation_order(dependencies)
    settings = ["--api-version", api_version]
    if profile:
        settings += ["--profile", profile]
    created_ids = [names[alias] for alias in order]
    plan = {
        "schema_version": 1,
        "kind": "schema_plan",
        "status": "planned",
        "api_version": api_version,
        "profile": profile,
        "service_checked": False,
        "external_analyzers": sorted(used_external),
        "creation_order": created_ids,
        "root_analyzers": [
            names[alias] for alias in order
            if not any(alias in refs for refs in dependencies.values())
        ],
        "analyzers": [
            {
                "alias": alias,
                "analyzer_id": names[alias],
                "source": str(schemas[alias]),
                "source_sha256": source_hashes[alias],
                "schema": f"{names[alias]}.json",
                "sha256": hashlib.sha256(payloads[alias]).hexdigest(),
                "dependencies": [names[ref] for ref in sorted(dependencies[alias])],
            }
            for alias in order
        ],
        "commands": {
            "create": [
                ["cu", "analyzer", "create", "--name", names[alias],
                 "--schema", f"{names[alias]}.json", *settings]
                for alias in order
            ],
            "delete": [
                ["cu", "analyzer", "delete", "--name", name, *settings]
                for name in reversed(created_ids)
            ],
        },
        "warnings": warnings,
        "limitations": [
            "Commands are relative to this plan directory and have not been executed.",
            "Resource access, analyzer availability, model mappings, and service acceptance are unverified.",
            "Use a new ID prefix; existing remote analyzers are never replaced by this tool.",
            "Only delete analyzers you actually created, in reverse dependency order.",
        ],
    }
    output.mkdir(parents=True, exist_ok=False)
    for alias in order:
        with (output / f"{names[alias]}.json").open("xb") as stream:
            stream.write(payloads[alias])
    with (output / "plan.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(plan, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    return plan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", action="append", required=True, metavar="ALIAS=FILE")
    parser.add_argument("--id-prefix", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--api-version", default=DEFAULT_API_VERSION)
    parser.add_argument("--profile")
    parser.add_argument("--external", action="append", default=[])
    args = parser.parse_args(argv)
    try:
        plan = build_plan(
            parse_schemas(args.schema), id_prefix=args.id_prefix, output=args.output,
            api_version=args.api_version, profile=args.profile, external=set(args.external),
        )
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Offline plan: {args.output / 'plan.json'}")
    print(f"Create order: {', '.join(plan['creation_order'])}")
    for warning in plan["warnings"]:
        print(f"Warning: {warning}", file=sys.stderr)
    print("No service calls were made. Review the plan before invoking cu.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
