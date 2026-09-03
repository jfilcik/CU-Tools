---
name: cu-preview-api
description: Configures and tests Azure AI Content Understanding preview analyzers, including agentic workflows, explicit preview API versions, Studio bug-bash setup, and Southeast Asia test resources. Use when users ask for CU preview API, agentic mode, config.workflow Agentic, gpt-5.2 analyzers, preview compatibility testing, or the CU Studio bug bash.
---

# Skill: CU Preview API

Use this workflow only for preview-specific Content Understanding features. Keep the GA default unchanged.

## Studio test setup

1. Open `https://aka.ms/custudiobugbash` and sign in.
2. Select the Southeast Asia AI resource:
   - Subscription: `MMI - Dev 01`
   - Resource group: `mmi-usw3-studiotest`
   - Resource: `mmi-southeastasia-resource`
3. Save the resource setting.
4. Create a custom analyzer project with a project name that identifies the tester and purpose.
5. Configure project storage:
   - Subscription: `MMI - Dev 02`
   - Resource group: `mmi-eft-infra`
   - Storage account: `mmicustudiotestwus3`
   - Blob container: `bugbash`

Never write keys, bearer tokens, SAS URLs, or `.env` contents into schemas, commands saved in the repository, logs, or reports.

## Verified agentic contract

The following contract was verified on the named Southeast Asia resource:

- API version: `2026-06-01-preview`
- Completion model: `gpt-5.2`
- Schema selector: `"config": { "workflow": "Agentic" }`
- One input file per analysis request

Validate explicitly:

```powershell
python tools\cu-analyzer-validate\cu_analyzer_validator.py `
  <schema.json> `
  --api-version 2026-06-01-preview
```

Create and test explicitly:

```powershell
python tools\cu-analyzer-run\create_and_test.py `
  --schema <schema.json> `
  --input <single-file> `
  --output <results-folder> `
  --api-version 2026-06-01-preview `
  --timeout 600
```

Run an existing analyzer explicitly:

```powershell
python tools\cu-analyzer-run\run.py `
  --analyzer-id <analyzer-id> `
  --input <single-file> `
  --output <results-folder> `
  --api-version 2026-06-01-preview `
  --timeout 600
```

## Compatibility gate

Before paid scale or stability work:

1. Validate with the preview API version.
2. Use a short, non-sensitive sample for a create/analyze/delete smoke cycle.
3. Confirm the result contains the expected fields and grounded source details.
4. Record API version, region, model, latency, and token usage.
5. Obtain explicit cost approval before larger agentic runs.

Long contracts can exceed ten minutes. Treat timeout as a latency/capacity result, not as proof that the schema contract was rejected. Do not silently replace `config.workflow` with another preview property.

See `Agents.md` for authoritative API rules,
`examples/05-Agentic-Contract-Obligations/` for broad preview testing, and
`examples/06-Contract-Obligation-Golden-Set/` for a controlled Standard-vs-
Agentic comparison on reviewed atomic obligations.
