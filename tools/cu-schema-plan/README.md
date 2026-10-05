# Offline schema dependency plans

Use this helper only for a **set of dependent analyzers**. For a single schema,
use `cu analyzer validate` and `cu analyzer create` directly. For additional
local schema-quality checks, use `cu-analyzer-validate`.

The planner performs no authentication or service calls. It preserves source
files, assigns explicitly prefixed analyzer IDs, rewrites local
`baseAnalyzerId` and `config.contentCategories.*.analyzerId` references,
validates locally, and snapshots schemas with SHA-256 hashes. It emits
dependency-first create commands and reverse-order delete commands for `cu`;
it does not execute them or replace existing analyzers.

```powershell
python tools\cu-schema-plan\schema_plan.py `
  --schema invoice=.\schemas\invoice.json `
  --schema packet=.\schemas\packet.json `
  --id-prefix case001_v1 `
  --output .\case\iterations\001\inputs\deployment `
  --api-version 2025-11-01
```

Inside `packet.json`, an `analyzerId: "invoice"` reference selects the local
`invoice` alias. Classification-only categories need no analyzer reference.
Custom dependencies outside this set require `--external EXISTING_ID`;
prebuilt references are retained. External availability is not checked.
Use `--profile NAME` to put the same resource selector on every generated
command. Profiles and credentials are managed by the official CLI.

`plan.json` records creation order, roots, dependencies, source and snapshot
hashes, local warnings, and exact argument arrays. Commands use paths relative
to the plan directory. Review the plan, then invoke the official CLI in order:

```powershell
Push-Location .\case\iterations\001\inputs\deployment
try {
    $plan = Get-Content .\plan.json -Raw | ConvertFrom-Json
    foreach ($command in $plan.commands.create) {
        $arguments = @($command | Select-Object -Skip 1)
        & cu @arguments
        if ($LASTEXITCODE -ne 0) { throw "Analyzer creation failed; stop and inspect the CLI error." }
    }
} finally {
    Pop-Location
}
```

Use `cu analyzer show ID` to verify remote definitions. Analyze with the root
analyzer via `cu analyze`. Only delete IDs that this experiment actually
created; use the plan's reverse order and retain CLI confirmation. A partial
creation failure does not authorize deleting pre-existing resources.

Plans reject missing references, cycles, invalid IDs, malformed schemas,
case-insensitive name collisions, and existing output directories. No schema
defaults are invented: only analyzer references and a source `analyzerId`
metadata property are changed. `plan.json` is written last; an incomplete
directory is not a completed plan. Service compatibility, model deployment
availability, and extraction quality still require separate verification.

```powershell
python -m pytest tools\cu-schema-plan\tests -q
```
