---
name: generate-analyzer-classify-route
description: Designs and tests mixed-document CU pipelines with an offline dependency plan and explicit official cu creation, analysis, and cleanup. Use when different packet types need different field schemas.
---

# Skill: Generate Analyzer — Classify-and-Route

Use for packets containing distinct document types that need different
extraction schemas. For one type, use [standard generation](generate-analyzer.skill.md).
Technical routing rules belong in [Agents.md §4.7](../../Agents.md#47-classify-and-route-pattern-contentcategories);
the [schema prompt](../prompts/classify-and-route-schema.prompt.md) is a concise
design checklist.

## 1. Freeze the pipeline experiment

Follow [Iterate Analyzer Schema](iterate-analyzer-schema.skill.md) and
[iteration workspaces](../../docs/iteration-workspaces.md). Select
`case\iterations\NNN`; keep customer packets private. Record hypothesis,
baseline, expected/actual defects, verified bugs, input hashes, reviewed truth,
and evaluator/acceptance rules. Freeze all inner and outer schema sources.

Predeclare layout, individual-inner checks, and mixed-packet tests as phases
with separate raw output directories. Obtain explicit cost approval for all
phases and any repeats. New schemas, scope, or metrics require a new number.

## 2. Identify types and design schemas

Inspect saved layout or use the approved native layout command in
[standard generation](generate-analyzer.skill.md). Identify text headings,
labels, section transitions, and type-distinguishing anchors. Do not classify
documents by colors, fonts, or position alone.

Create one ordinary field schema per type. Keep document-level totals separate
from line-item arrays and define source/null behavior. The outer schema uses
`enableSegment: true` and `contentCategories`; it needs no `fieldSchema`
when all extraction is delegated. Classification-only categories omit
`analyzerId`.

Use **source aliases** for local dependencies, not guessed deployment IDs.
For `packet.json`, referencing supplied aliases `invoice` and `receipt`:

```json
{
  "description": "Classify invoice and receipt segments and route their fields",
  "baseAnalyzerId": "prebuilt-document",
  "config": {
    "enableSegment": true,
    "contentCategories": {
      "invoice": {
        "description": "Invoice heading, Invoice Number label, item prices, and Amount Due or Total identify an invoice segment.",
        "analyzerId": "invoice"
      },
      "receipt": {
        "description": "Receipt heading, transaction date, payment confirmation, and amount paid identify a receipt segment.",
        "analyzerId": "receipt"
      },
      "other": {
        "description": "Content that lacks the distinguishing invoice or receipt anchors; classify without field extraction."
      }
    },
    "omitContent": true
  },
  "models": { "completion": "gpt-4.1" }
}
```

For complex packets, contrast the closest confusable types and define
continuation-page cues. Do not add unnecessary routing depth or assume document
nesting rules apply to video.

## 3. Build and review the offline dependency plan

From the repository root:

```powershell
python tools\cu-schema-plan\schema_plan.py `
  --schema "invoice={iteration_folder}\inputs\schemas\invoice.json" `
  --schema "receipt={iteration_folder}\inputs\schemas\receipt.json" `
  --schema "packet={iteration_folder}\inputs\schemas\packet.json" `
  --id-prefix invoice_001 --api-version 2025-11-01 `
  --output "{iteration_folder}\inputs\schemas\resolved"
```

The output directory must be new. Optional `--profile NAME` is recorded in
commands; `--external EXISTING_ID` explicitly permits a pre-existing dependency
without creating or owning it. The planner patches supplied aliases in
`baseAnalyzerId` and `contentCategories` to prefixed IDs, validates locally,
and snapshots/hashes resolved schemas. It makes **no service calls**.

Review `plan.json`: dependencies, unique IDs, final schema hashes, API/profile,
warnings, dependency-first `commands.create`, and reverse `commands.delete`.
Those are argument arrays relative to the plan directory, not executed work.
Validate the resolved snapshots with `cu analyzer validate ... --spec` too.
Offline validation does not establish external analyzer availability, model
mappings, resource permissions, or service acceptance.

## 4. Create with official `cu`

Inner analyzers must exist before the outer analyzer. Review and run the
plan's ordered create commands from its directory. For an authorized sequence,
this PowerShell loop stops on the first failure:

```powershell
Push-Location "{iteration_folder}\inputs\schemas\resolved"
try {
    $plan = Get-Content -Raw .\plan.json | ConvertFrom-Json
    foreach ($command in $plan.commands.create) {
        $executable = $command[0]
        $arguments = @($command | Select-Object -Skip 1)
        & $executable @arguments
        if ($LASTEXITCODE -ne 0) {
            throw "Creation failed; stop and inspect before any further service operation."
        }
        Add-Content -Path .\created-analyzers.txt -Value $command[4]
    }
}
finally {
    Pop-Location
}
```

Use the official executable from the configured environment, not another
program named `cu`. Record creation evidence and observed IDs. Do not rerun
the sequence to replace IDs. After an uncertain failure, inspect state before
retry or cleanup; the planned ID list is not proof those analyzers were created.

## 5. Test inners, then the full packet

Test each inner on its own frozen type before **analyzing** mixed packets
through the outer. Keep analyzers available for their dependents. Each source
must be an input-only staging folder matching the frozen selection; keep
manifests, schemas, and outputs outside it. Use repeated `--file FILE` selectors
instead when staging is unnecessary; do not rely on beta discovery filters.

```powershell
cu analyze --source "{invoice_samples}" `
  --analyzer invoice_001_invoice --json --api-version 2025-11-01 `
  --output-dir "{iteration_folder}\outputs\raw\invoice" `
  --report-file "{iteration_folder}\outputs\raw\invoice-status.json" `
  --concurrency 3 --yes --on-existing error
```

Repeat for `invoice_001_receipt` with its own samples/output/report. Proceed
only after reviewed inner correctness meets the predeclared gates:

```powershell
cu analyze --source "{mixed_packets}" `
  --analyzer invoice_001_packet --json --api-version 2025-11-01 `
  --output-dir "{iteration_folder}\outputs\raw\packet" `
  --report-file "{iteration_folder}\outputs\raw\packet-status.json" `
  --concurrency 3 --yes --on-existing error
python tools\cu-results-export\export.py `
  --input "{iteration_folder}\outputs\raw\packet" `
  --output "{iteration_folder}\outputs\evaluation\packet.csv"
```

Apply `--profile NAME` consistently if selected. For stability use the
explicit-file experiment helper in [Eval CU](eval-cu.skill.md), not another
pipeline executor.

## 6. Evaluate, report, and clean up

Review packet/segment boundaries, correct categories, classification-only
segments, per-category fields, row retention, and reviewed case acceptance.
An elevated `other` rate suggests a hypothesis, not a known cause. Report
denominators, false accepts, review/failures, protected behavior, and holdout
limits; category/fill scores alone are not STP.

Preserve native raw results and CLI reports. Reports describe input statuses,
not guaranteed latency/usage or correctness. Missing usage/cost stays unknown;
price-based costs are estimated. Include inner checks, layout, routed calls,
and failed/repeated attempts in cost scope. Finish manifest/report and root
navigation with evidence-backed expected/actual findings and bug links.

Review reverse-order cleanup commands and execute only for actually-created,
owned IDs, with explicit authorization; retain confirmation by default.
Never delete external/pre-existing analyzers or every planned ID after an
uncertain failure. A new inner version requires a newly resolved outer version;
do not mutate a completed pipeline or its snapshots.
