---
name: cu-preview-api
description: Configures and tests Azure AI Content Understanding preview analyzers, including agentic workflows, explicit preview API versions, Studio bug-bash setup, and Southeast Asia test resources. Use when users ask for CU preview API, agentic mode, config.workflow Agentic, gpt-5.2 analyzers, preview compatibility testing, or the CU Studio bug bash.
---

# Skill: CU Preview API

Use this workflow only for preview-specific Content Understanding features. Keep the GA default unchanged.

## Select an iteration

Use [the canonical v1 workspace guide](../../docs/iteration-workspaces.md).
Keep customer material private. Select `case/iterations/NNN` before creating
schemas or outputs; snapshot schemas in `inputs/schemas/`, inventory/hash
documents, and version truth/evaluator. Save raw responses under `outputs/raw/`,
derived evaluation under `outputs/evaluation/`, and the evidence/cost decision
in `report.md` and the iteration manifest. A smoke test and a broader corpus,
or Standard and Agentic configurations, are separate numbered experiments.
Trials from `--iterations N` remain within one experiment.
Link verified product bugs in the root and relevant iteration `bugs` arrays,
separately from local defects; follow [tracking bugs](../../docs/iteration-workspaces.md#tracking-bugs).

Use official `cu` for routine operations when its installed flags support
the requested contract; retain the validator for CU-Tools preview checks and
the runners below for lifecycle, repeats, diagnostics, or bundle compatibility.
They remain REST-based; installing the official CLI does not change them.

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
  "{iteration_folder}\inputs\schemas\schema.json" `
  --api-version 2026-06-01-preview
```

Create and test explicitly:

```powershell
python tools\cu-analyzer-run\create_and_test.py `
  --schema "{iteration_folder}\inputs\schemas\schema.json" `
  --input <single-file> `
  --output "{iteration_folder}\outputs\raw\analysis" `
  --api-version 2026-06-01-preview `
  --timeout 600
```

Run an existing analyzer explicitly:

```powershell
python tools\cu-analyzer-run\run.py `
  --analyzer-id <analyzer-id> `
  --input <single-file> `
  --output "{iteration_folder}\outputs\raw\analysis" `
  --api-version 2026-06-01-preview `
  --timeout 600
```

## Compatibility gate

Before paid scale or stability work:

1. Validate with the preview API version.
2. Use a short, non-sensitive sample for a create/analyze/delete smoke cycle.
3. Confirm the result contains the expected fields and grounded source details.
4. Record sanitized commands, tool/git/API/model versions, region, runtime
   IDs, latency, tokens, successes/failures/retries, and cost status/basis.
5. Obtain explicit cost approval before larger agentic runs.

Long contracts can exceed ten minutes. Treat timeout as a latency/capacity result, not as proof that the schema contract was rejected. Do not silently replace `config.workflow` with another preview property.

Account for every iteration, including failed/timed-out calls. Missing cost
stays unknown/null, not zero; usage times prices is estimated, not measured
charges. Link actual evidence, state incomplete results honestly, and refresh
the root iteration index. A compatible smoke test is not evidence of STP.

See `Agents.md` for authoritative API rules,
`examples/05-Agentic-Contract-Obligations/` for broad preview testing, and
`examples/06-Contract-Obligation-Golden-Set/` for a controlled Standard-vs-
Agentic comparison on reviewed atomic obligations.
