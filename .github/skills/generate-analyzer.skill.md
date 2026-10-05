---
name: generate-analyzer
description: Creates and tests Azure AI Content Understanding schemas for a single document type using official cu, offline validation, and reviewed evaluation. Use for new analyzers, layout extraction, or a first schema version.
---

# Skill: Generate Analyzer

Use this workflow for one document type. For mixed packets use
[classify-and-route](generate-analyzer-classify-route.skill.md); for video use
[video generation](generate-analyzer-video.skill.md); for preview or Agentic
use [preview compatibility](cu-preview-api.skill.md).

## 1. Freeze the experiment

Follow [the workspace contract](../../docs/iteration-workspaces.md) and
[iteration workflow](iterate-analyzer-schema.skill.md). Select the next
`case\iterations\NNN` before writing artifacts. Keep customer material private.
Record expected versus actual behavior, hypothesis, baseline, defects, and
verified tracking bugs. Freeze 3–5 representative inputs, schema snapshots,
reviewed truth, evaluator versions, and acceptance rules with hashes.

Commands below are PowerShell templates run from the repository root with the
official PyPI `cu-cli` installed; replace all placeholders. Follow the
[README](../../README.md) for installation and profiles. Official `cu` is the
only CU execution backend. Obtain explicit approval for the billable scope,
including layout and analysis, before running the service commands.

## 2. Inspect layout

```powershell
cu analyze --source "{sample_folder}" `
  --analyzer prebuilt-layout --json --api-version 2025-11-01 `
  --output-dir "{iteration_folder}\outputs\raw\layout" `
  --report-file "{iteration_folder}\outputs\raw\layout-status.json" `
  --concurrency 3 --yes --on-existing error
```

Use an input-only staging folder containing exactly the frozen corpus; keep
manifests, schemas, and outputs outside that source. The verified beta CLI's
discovery filters can miss files, so do not depend on them. Add `--recursive`
only if inventoried subfolders are intended. For selected files use explicit
`--file "{document_path}"` selectors instead of `--source`, repeating as needed.
Inspect the native `.result.json` files for text, tables, section boundaries,
and repeated entities. Without `--json`, the CLI defaults to markdown; do not
rerun a paid analysis merely to get another representation of saved data.
Status reports are execution evidence, not extracted documents.

## 3. Draft a versioned schema

Use [the schema prompt](../prompts/generate-analyzer-schema.prompt.md) and
[field descriptions](../prompts/write_schema_fields.prompt.md).

- Describe text labels, alternative labels, sections, rows, and columns—not
  color, font, or position alone.
- Use explicit methods and appropriate structured types. Repeated entities
  belong in arrays of objects; document totals do not belong in each row.
- Define missing/ambiguous-value behavior and distinguish confusable fields.
- Keep expected sample answers out of descriptions and format examples.
- Enable applicable source/confidence details for review; those are diagnostic,
  not proof of correctness.

Save the candidate under `{iteration_folder}\inputs\schemas\`. Technical API
and schema rules live in [Agents.md](../../Agents.md).

## 4. Validate offline, then create

```powershell
cu analyzer validate "{iteration_folder}\inputs\schemas\invoice_v1.json" `
  --api-version 2025-11-01 --spec
python tools\cu-analyzer-validate\cu_analyzer_validator.py `
  "{iteration_folder}\inputs\schemas\invoice_v1.json" --api-version 2025-11-01
```

Both checks are offline. The local validator adds CU-Tools quality checks.
Resolve errors and review warnings before executing the separate create step:

```powershell
cu analyzer create --name invoice_001 `
  --schema "{iteration_folder}\inputs\schemas\invoice_v1.json" `
  --api-version 2025-11-01
```

Use a new unique ID containing only letters, digits, and underscores (up to
64 characters). Stop on a nonzero exit; never delete/recreate an existing ID
to make creation succeed. Use the same explicit API version and, if selected,
`--profile NAME` for creation and analysis.

## 5. Analyze and review

```powershell
cu analyze --source "{sample_folder}" `
  --analyzer invoice_001 --json --api-version 2025-11-01 `
  --output-dir "{iteration_folder}\outputs\raw\analysis" `
  --report-file "{iteration_folder}\outputs\raw\analysis-status.json" `
  --concurrency 3 --yes --on-existing error
python tools\cu-results-export\export.py `
  --input "{iteration_folder}\outputs\raw\analysis" `
  --output "{iteration_folder}\outputs\evaluation\results.csv" --diagnose
```

After analysis completes, inspect both exit status and per-input report
statuses. Preserve failed/missing inputs in evaluation denominators. The
offline exporter reads native results recursively and supports legacy saved
results; a successful export does not mean all intended inputs succeeded.

Follow [Eval CU](eval-cu.skill.md) for correctness, repeated trials, cost, and
the report. Missing usage/latency is unknown, not zero; console `--usage` or
`--time` output is not guaranteed per-file metadata. Fill and confidence are
diagnostics; acceptance and STP require reviewed case-level correctness.

## 6. Close or iterate

Complete the iteration manifest/report and synchronize the root index.
Preserve raw results and submitted schemas. Changes require the next numbered
experiment and a new analyzer ID; use the [iteration workflow](iterate-analyzer-schema.skill.md).
Cleanup is separate and explicit: `cu analyzer delete invoice_001` only when
that analyzer was actually created and is owned by this experiment, after
checking dependents and cleanup authorization. Do not delete pre-existing IDs.
