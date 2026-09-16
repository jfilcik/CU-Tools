# Offline analyzer validation

Check local analyzer schema structure and quality without credentials, network
requests, analyzer creation, or paid analysis. This standard-library-only
helper complements the official CLI's structural/spec validation.

From the repository root:

```powershell
python tools\cu-analyzer-validate\cu_analyzer_validator.py .\schemas\invoice_v1.json
cu analyzer validate .\schemas\invoice_v1.json --api-version 2025-11-01 --spec
```

The local checks cover field types, nested arrays/objects, methods,
descriptions, configuration combinations, and classify-and-route categories.
A routing-only analyzer can omit `fieldSchema`; do not invent fields merely
to satisfy a field-extraction workflow.

## Preview contract

```powershell
python tools\cu-analyzer-validate\cu_analyzer_validator.py `
  .\schemas\agentic.json --api-version 2026-06-01-preview
```

GA defaults to `2025-11-01`. `config.workflow: "Agentic"` requires the explicit
preview version and exact case. See [Agents.md](../../Agents.md#410-preview-agentic-api).

Exit code 0 means local validation passed (possibly with warnings); 1 means
validation failed. Inspect warnings as well as errors. A passed local check
does not establish resource availability, service acceptance, extraction
accuracy, or STP readiness.

## Integration

The [offline schema planner](../cu-schema-plan/README.md) reuses this validator
when freezing dependency-ordered schemas. Direct creation stays explicit:

```powershell
python tools\cu-analyzer-validate\cu_analyzer_validator.py .\schemas\invoice_v1.json
if ($LASTEXITCODE -ne 0) { throw "Local validation failed." }
cu analyzer create --name invoice_v1 --schema .\schemas\invoice_v1.json --api-version 2025-11-01
if ($LASTEXITCODE -ne 0) { throw "Analyzer creation failed." }
```

Choose a new analyzer ID; do not implicitly delete or replace existing
resources. For programmatic offline use, import `validate_cu_analyzer` or
`validate_cu_analyzer_file` and inspect the returned errors/warnings.

```powershell
python -m pytest tools\cu-analyzer-validate\tests -q
```

See [schema guidance](cu-analyzer-instructions.md),
[generation workflow](../../.github/skills/generate-analyzer.skill.md), and
[field-writing prompt](../../.github/prompts/write_schema_fields.prompt.md).
