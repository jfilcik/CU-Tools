# Tutorial 02: Invoice extraction

Develop an analyzer by inspecting layout, improving field descriptions, and
measuring reviewed correctness and cost. All CU operations use the official
CLI; local helpers support validation and evaluation.

## Numbered iteration navigation

- [Case manifest](manifest.json)
- [001 - Planned baseline](iterations/001/manifest.json)
- [001 - Plan/report: not run](iterations/001/report.md)
- [Workspace contract](../../docs/iteration-workspaces.md)

Iteration `001` links the public `invoice.pdf` and `invoice_v1.json` with
SHA-256 hashes. It is **not run**: no API results, measured cost, accuracy, or
STP readiness is claimed. `receipt.png` is not in this selected baseline.
The instructions below do not change that state until someone executes and
records an approved run.

## Prepare

Follow the [root Quick Start](../../README.md#quick-start). Use Python 3.10+,
the official CLI profile, your authorized resource/model mappings, and local
CU-Tools reporting dependencies. Run commands from the repository root.

Select the planned iteration and freeze the exact schema without overwriting:

```powershell
$case = ".\examples\02-Invoice-Extraction"
$iteration = "$case\iterations\001"
$schema = "$iteration\inputs\schemas\invoice_v1.json"
if (Test-Path $schema) { throw "A snapshot exists; review it or select a new iteration." }
New-Item -ItemType Directory -Force "$iteration\inputs\schemas" | Out-Null
Copy-Item "$case\schemas\invoice_v1.json" $schema
```

Link/hash the snapshot in the iteration manifest. Keep the shared samples and
historical evidence in place. A new schema/configuration/dataset/metric means
`002` or the next number, not an overwrite.

## Inspect layout

Layout analysis is billable; review the scope and cost before executing.

```powershell
cu analyze "$case\samples\invoice.pdf" --analyzer prebuilt-layout `
  --output-dir "$iteration\outputs\raw\layout" `
  --report-file "$iteration\outputs\raw\layout-status.json" --on-existing error
```

Read the native markdown output for labels, line-item tables, section headings,
and alternative wording. Describe these anchors in the schema rather than
color, font, or styling.

## Design and validate

The supplied schema demonstrates detailed descriptions, alternative labels,
format examples, disambiguation, and arrays for line items. For example:

```json
{
  "InvoiceDate": {
    "type": "string",
    "method": "extract",
    "description": "Invoice issue date near the invoice number. May be labeled Invoice Date, Date, or Issued. Return the issue date rather than the payment deadline, in YYYY-MM-DD format."
  }
}
```

```powershell
cu analyzer validate $schema --api-version 2025-11-01
python tools\cu-analyzer-validate\cu_analyzer_validator.py $schema
```

The first performs official CLI validation; the second adds offline schema
quality checks. Neither proves the deployed analyzer will extract correctly.

## Create and analyze explicitly

Choose an unused versioned analyzer ID. After resource and cost approval:

```powershell
cu analyzer create --name tutorial_invoice_v1 --schema $schema --api-version 2025-11-01
cu analyzer show tutorial_invoice_v1 > "$iteration\inputs\schemas\deployed.json"

cu analyze "$case\samples\invoice.pdf" --analyzer tutorial_invoice_v1 `
  --json --output-dir "$iteration\outputs\raw\analysis" `
  --report-file "$iteration\outputs\raw\analysis-status.json" `
  --api-version 2025-11-01 --on-existing error
```

Preserve native result bytes and the separate status report. Do not rerun into
these paths or overwrite the deployed snapshot. Record CLI version, API
version, analyzer ID, exact sanitized commands, and outcomes in the manifest.
Explicitly delete only analyzers you created and no longer need.

## Evaluate correctness and cost

```powershell
python tools\cu-results-export\export.py `
  --input "$iteration\outputs\raw\analysis" `
  --output "$iteration\outputs\evaluation\results.csv"
```

Compare dates, parties, line items, totals, and arithmetic against reviewed
source truth. Record missing/failed documents, denominators, ground-truth and
evaluator versions, regressions, and the accept/reject/inconclusive decision.
Fill rate and confidence diagnose extraction; they are not accuracy or STP.

Native CLI JSON does not guarantee per-document usage or latency.
`--usage`/`--time` can preserve additional console evidence; absent numbers
remain unknown. Document price basis/coverage for estimates and do not call
them actual charges. Complete the report and synchronize the root index.

## Scale, repeat, and compare

For an approved corpus in a **new iteration**, run one native batch with
`cu analyze --source DIRECTORY --recursive --concurrency 5`, keeping a fresh
output directory and status report.

For ten repeated trials of this invoice, use the focused experiment helper:

```powershell
python tools\cu-experiments\experiment.py plan `
  --input "$case\samples\invoice.pdf" --analyzer tutorial_invoice_v1 `
  --iterations 10 --concurrency 5 --output .\invoice-stability-experiment

# Review ten planned analyses and cost before proceeding.
python tools\cu-experiments\experiment.py run .\invoice-stability-experiment --confirm-cost
```

Place the experiment under the selected numbered iteration when recording
real work. To compare versions, create the new analyzer explicitly and add a
second `--analyzer` to the plan. Ten trials remain inside one experiment.
See the [evaluation skill](../../.github/skills/eval-cu.skill.md) and
[schema iteration workflow](../../.github/skills/iterate-schema.skill.md).
