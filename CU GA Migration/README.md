# CU Migrate — Offline Preview-to-GA Schema Planner

Inventory **local analyzer exports**, propose GA schemas, and produce an
evidence-backed review bundle. This helper does not authenticate, read
environment credentials, call HTTP/SDKs, launch `cu`, or deploy anything.
The separately installed **official `cu` executable owns every CU service
operation**. No Microsoft-internal service, telemetry, or test resource is needed.

## Install

From this directory:

```powershell
python -m pip install -e .
```

The helper only needs Click, Rich and Pydantic. Install the official CLI
separately from public PyPI, then configure it using the repository's root README:

```powershell
python -m pip install --upgrade --pre cu-cli
```

Never pass credentials as migration arguments or put them in schemas.

## Workflow

### 1. Inspect and export with the official CLI

Run these commands yourself, using the intended resource and source API
version configured in the official CLI. Use a **new export filename** each
time: shell `>` overwrites an existing file.

```powershell
cu analyzer list --json > .\inventory_20260916.json
cu analyzer show invoice_preview > .\invoice_preview_20260916.json
```

An inventory listing may contain metadata rather than complete definitions.
In that case, use `cu analyzer show NAME` for every analyzer you intend
to migrate. If a source needs a Preview API version, check the installed
official command's `--help` for the appropriate version selection.
Do not combine a metadata listing and full exports of the same IDs as inputs:
duplicate IDs are rejected instead of silently choosing one.

These commands match public PyPI `cu-cli 0.1.0b1`: `analyzer show` emits JSON
by default and accepts neither `--json` nor `--output-file`. Redirect its stdout
to a new file. Do not substitute a divergent globally installed checkout.

### 2. Inventory and plan offline

```powershell
cu-migrate inventory --input .\inventory_20260916.json
cu-migrate inventory --input .\exports --json

# Single analyzer, no files written
cu-migrate migrate --input .\invoice_preview_20260916.json -a invoice_preview

# Multiple analyzers from one or more local exports
cu-migrate migrate --input .\exports -a invoice_preview -a receipt_preview `
  --mode export --output .\review_v1

# All custom analyzers supplied locally, not all analyzers in a resource
cu-migrate migrate --input .\exports --mode export --output .\review_all_v1

# Standalone schema without analyzerId: supply its identity explicitly
cu-migrate migrate --input .\schema.json --source-id invoice_preview `
  --mode export --output .\review_schema_v1

# Report is a convenience command for the same complete export bundle
cu-migrate report --input .\exports --output .\review_report_v1
```

`--input` is required and repeatable. Each input is either a file or a
directory's immediate `*.json` children (not recursive). Accepted JSON shapes:

- A single analyzer definition, with `analyzerId` (also accepts `id` or `name`).
- A single response with an outer identity and a `properties` definition object.
- An array of those objects.
- A list wrapper: `{"value": [...]}`, `{"analyzers": [...]}`, or `{"items": [...]}`.
- An ID-less standalone definition file with explicit `--source-id`.

Conflicting identity aliases, duplicate IDs/JSON keys, empty exports,
malformed values and unfinished pagination (`nextLink`) fail closed.
`--source-id` is not a filename inference mechanism and cannot identify an
entire directory or list. Unknown `-a` selections fail before output is written.
Built-ins are excluded by default; `inventory --include-prebuilt` shows them,
but they cannot be migration targets.

### 3. Review, validate and explicitly create using the official CLI

Inspect `migration_report.md`, compare `backups` with `proposed`, and review
model choices, knowledge sources and classifier references. Check the official
CLI's local schema-validation help before creation. Check that the intended
new analyzer ID is unused; the offline planner cannot inspect the destination.

The generated `official_cu_commands.md` contains commands like this, to run
**from inside the bundle directory** only after review:

```powershell
cu analyzer create --name invoice_preview_ga_v1 `
  --schema '.\proposed\invoice_preview_ga_v1.json' --api-version 2025-11-01
```

GA remains `2025-11-01`. Generated names use only letters, digits and
underscores, up to 64 characters, with a new `_ga_v1` suffix. Long names receive
a deterministic hash before the suffix. Collisions with local source IDs or
other proposals are blockers. Availability on the service remains unverified.
Never delete/recreate a source ID to perform an update. Test representative
documents with the official CLI before switching application references.

## Output and failure contract

| Mode/command | Behavior |
|---|---|
| `migrate` / `--mode dry_run` | Print report; no filesystem writes; `--output` is rejected |
| `migrate --mode export` | Require `--output NEW_DIRECTORY`; export proposals, evidence and reports |
| `report` | Same complete export bundle; requires `--output NEW_DIRECTORY` |

Existing output directories are rejected, including empty ones. Source exports
are never edited. Individual artifact writes use exclusive creation.
A final `manifest.json` marks a fully written bundle; an interrupted write may
leave a partial directory without that manifest. Choose a fresh directory to retry.

| Artifact | Meaning |
|---|---|
| `sources/NNNN.json` | Byte-for-byte original input files, including list wrappers |
| `backups/NNNN.json` | Original per-analyzer JSON records before normalization |
| `proposed/NAME.json` | Non-blocked proposed creation payloads; **not deployed** |
| `blocked/NNNN.json` | Failed transformation payloads, when available; diagnostic only |
| `migration_run.json` | Complete structured results and findings |
| `manifest.json` | Source paths/SHA-256 evidence, payload paths, counts, commands and `deployed: false` |
| `migration_report.md` | Common and analyzer-specific findings plus source provenance |
| `app_checklist.md` | Human review, creation, testing and application-change checklist |
| `official_cu_commands.md` | Explicit official CLI creation commands; blocked analyzers have none |

An input file changed between loading and backup is rejected.
Treat exports and bundles as sensitive: schema descriptions, storage URLs,
SAS query strings or customer metadata may be present in the source and are
preserved for evidence. Inspect/redact copies before sharing; this is not a
credential-redaction utility.

Exit status:

- **0**: inventory/planning/export completed without blockers. Warnings still
  require human review; this never means deployment or runtime parity succeeded.
- **1**: input/selection/output error, failed validation, unsupported features
  or another planning failure. In a mixed export, successful proposals and
  failed-analyzer evidence are retained; the command still exits nonzero.
- **2**: invalid Click invocation, missing required options or obsolete options.

`--endpoint`, `--key`, `--yes`, and `--mode apply` have been removed and produce
Click errors. They are never ignored. The helper has no authentication options
or automatic environment configuration.

## Compatibility coverage and limits

The planner retains Preview scenario mapping, deprecated-property removal,
Pro/Face/person-directory blockers, inline-upload and video/segmentation
warnings, field schema/config preservation, training-data conversion and reports.
Existing `knowledgeSources` and model choices are preserved. Missing models use
review-required GA model IDs, not deployment objects. Unknown scenarios never
silently fall back to a document analyzer.

Unresolvable training data and invalid model/field/ID shapes are blockers.
Classifier references are preserved and flagged for manual routing review,
not automatically redirected. Model deployment availability, storage
permissions, service acceptance and extraction quality cannot be verified
offline. The knowledge-source mapper covers the existing blob-reference
pattern; unsupported representations require manual conversion and validation.
This tool copies references only, never training data or blobs.

## Development

```powershell
python -m pip install -e ".[dev]"
python -m pytest tests -q
```

All tests are offline and use local synthetic fixtures. Test working files are
created beneath this subtree and cleaned up; no Azure credentials are required.
