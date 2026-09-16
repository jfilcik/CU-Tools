# Offline Migration Implementation Plan

This replaces the former remote-client/apply-mode plan.

## Components

| Component | Responsibility |
|---|---|
| `inventory.py` | Strict local JSON loading, identity resolution, export normalization and readiness |
| `models.py` | Source evidence, proposed payloads, findings and offline runs |
| `rules.py` | Removed-feature blockers and compatibility warnings |
| `transform.py` | Scenario/config/schema/model transformation and new versioned IDs |
| `knowledge.py` | Preserve existing knowledge references and convert Preview training references |
| `validator.py` | Offline structural checks; never resource access |
| `executor.py` | Selection, severity aggregation, collision detection and exclusive bundle writes |
| `reports.py` | Human reports, evidence and official CLI command text |
| `cli.py` | Explicit local inputs, dry-run/export/report commands and nonzero failures |

There is no `client.py` or `auth.py`. Runtime dependencies are Click, Rich and
Pydantic; tests require pytest, not HTTP mocks or Azure credentials.

## Verification checkpoints

1. Load standalone definitions, properties envelopes, arrays, list wrappers
   and directories. Require an explicit source ID for one ID-less file.
2. Reject corrupt JSON, empty inputs, ambiguous IDs, duplicate keys/IDs,
   incomplete pagination and unknown selections.
3. Retain source JSON and byte-level export hashes; do not mutate source files.
4. Propagate every blocking rule through final run status. Unknown scenarios
   must not acquire a default document base.
5. Preserve fields/config/models and existing knowledge sources; retain
   training-data arrays and flag unresolved references as blockers.
6. Enforce GA custom-ID rules and detect local target collisions.
7. Write only into a new output directory. Keep failed payloads separate;
   never generate create commands for failed analyzers.
8. Save the manifest last. A failed/incomplete write must return nonzero and
   cannot look like a complete bundle.
9. Verify dry runs write nothing, obsolete remote/apply options fail with
   Click errors, and mixed failures return nonzero despite useful artifacts.
10. Run `python -m pytest tests -q` entirely offline.

## Official CLI boundary

The user or skill, not this package, performs discovery/export and creation:

```powershell
cu analyzer list --json > .\new_inventory.json
cu analyzer show invoice_preview > .\new_invoice_export.json
cu-migrate migrate --input .\new_invoice_export.json --mode export --output .\new_review
```

After reviewing and validating the proposal, run the generated official
creation command from the review directory. Source export files and output
directories must be new; shell redirection is not an overwrite guard.

## Release limits

Offline shape checks cannot establish resource access, deployment availability,
knowledge-source permissions, API acceptance or quality parity. Validate those
separately through the official CLI. No live or paid service tests are part of
the helper's offline release gate.
