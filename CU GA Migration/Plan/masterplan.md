# Migration Assistant Scope

## Mission

Make Preview-to-GA schema changes reviewable without owning another CU client.
The official `cu` executable owns authentication and every service operation.
This package is strictly an offline inventory, compatibility, transformation
and report helper.

## User journey

1. The user/skill runs `cu analyzer list --json` and
   `cu analyzer show NAME` (JSON stdout by default) to export analyzers.
2. The helper loads explicit files or directories and inventories only those
   analyzers. List-only metadata is not enough to transform a schema.
3. The helper plans one analyzer, selected IDs, or all supplied custom analyzers.
4. A dry run prints findings without writes. Export creates a new local review
   bundle with original source evidence, proposed payloads and commands.
5. The user resolves findings, validates proposals, then explicitly runs the
   official `cu analyzer create --name NAME --schema FILE --api-version 2025-11-01`.
6. The user tests representative documents and changes application references.

## Retained migration value

- Preview scenario-to-base-analyzer mapping.
- GA model choices with explicit unverified-resource warnings.
- Deprecated-property removal and unsupported-feature blockers.
- Preservation of field schemas, configuration and existing knowledge sources.
- Training-data reference conversion with storage and field-mapping review.
- Single, selected and all-local scopes.
- Source file hashes, exact source-file copies and original-record backups.
- Aggregate and per-analyzer findings, app checklist and official CLI handoff.

## Safety contract

- No HTTP, SDK, process execution, Azure identity, credential loading or service writes.
- No apply mode, endpoint/key options, implicit resource inventory or hidden defaults.
- New versioned IDs contain letters/digits/underscores only, at most 64 characters.
- Unknown scenarios, unresolved data, malformed inputs and validation failures
  cannot become success-shaped defaults.
- Unsupported-feature findings remain blockers after transformation.
- Existing output directories and files are never overwritten.
- Mixed-result exports retain evidence but return a failure exit code.
- Exported proposals never claim to be deployed.
- Local collision checks cannot prove target IDs are unused on a remote resource.

## Non-goals

No resource-management layer, auth abstraction, live storage validation,
model-deployment configuration, data copying, automated rollback, web UI,
internal telemetry or Microsoft-only test dependencies. Do not introduce a
replacement wrapper around the official CLI.

## Domain reference

[Public Preview-to-GA migration guidance](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/how-to/migration-preview-to-ga)

Offline checks are intentionally bounded; public API changes and unsupported
knowledge-source forms require review using the official CLI's schema checks.
See `..\README.md` for the implemented command and artifact contract.
