---
name: cu-preview-api
description: Validates and tests CU preview or Agentic schemas on an authorized resource using official cu, explicit API versions, a short compatibility smoke test, and cost gates.
---

# Skill: CU Preview API

Use only for preview-specific capabilities. Keep the GA default unchanged.
Follow [Agents.md](../../Agents.md) for the technical contract,
[iteration workspaces](../../docs/iteration-workspaces.md) for evidence, and
[Iterate Analyzer Schema](iterate-analyzer-schema.skill.md) for shared workflow.

## Resource and experiment

Use your own authorized resource and the official CLI profile/environment
configuration from [README](../../README.md). `CU_ENDPOINT`, `CU_API_KEY`, and
`CU_API_VERSION` or saved profiles configure `cu`; it does not automatically
load a repository `.env`. Never place keys, tokens, or signed URLs in command
arguments, schemas, reports, or logs.

Confirm preview/workflow/model availability on that resource. Do not assume
a subscription, region, model deployment, or access grant. Inspect resource-wide
model defaults before proposing any change; never replace them incidentally.

Select `case\iterations\NNN`, freeze/hash schema and sample inputs, and record
hypothesis/baseline, expected/actual defects, bugs, truth/evaluator, and cost
approval. Keep customer material private. A compatibility smoke and an expanded
corpus are separate numbered scopes; repeats stay inside the chosen experiment.

## Agentic contract

- API version: `2026-06-01-preview`
- Completion model: `gpt-5.2`
- Selector: `config.workflow: "Agentic"` (case-sensitive)
- One input file per analysis request

Do not substitute another property when the contract is rejected. A CLI batch
can contain several local files but must still send one file per request.

## Offline validation

```powershell
cu analyzer validate "{iteration_folder}\inputs\schemas\agentic.json" `
  --api-version 2026-06-01-preview --spec
python tools\cu-analyzer-validate\cu_analyzer_validator.py `
  "{iteration_folder}\inputs\schemas\agentic.json" `
  --api-version 2026-06-01-preview
```

These checks make no service calls. Fix errors and review warnings before
running a short, non-sensitive, cost-approved smoke sample.

## Explicit create and analyze

```powershell
cu analyzer create --name contract_agentic_001 `
  --schema "{iteration_folder}\inputs\schemas\agentic.json" `
  --api-version 2026-06-01-preview
```

Stop if creation fails; use a fresh unique ID, not delete-and-replace.
Only after successful creation:

```powershell
cu analyze "{short_contract_path}" --analyzer contract_agentic_001 `
  --api-version 2026-06-01-preview --json --yes --on-existing error `
  --output-dir "{iteration_folder}\outputs\raw\smoke" `
  --report-file "{iteration_folder}\outputs\raw\smoke-status.json"
```

Apply `--profile NAME` consistently when using a named profile. After inspecting
results and saving evidence, explicitly clean up only the actually-created,
owned analyzer when authorized:

```powershell
cu analyzer delete contract_agentic_001 --api-version 2026-06-01-preview
```

Deletion prompts by default; use `--yes` only for explicitly authorized cleanup.
Never delete all planned IDs after an uncertain creation failure.

## Compatibility and scale gate

Verify the native result's expected fields and available grounding against
reviewed truth. Record service acceptance, input/trial statuses, and observed
IDs separately from extraction correctness. The CLI status report is not an
accuracy report or guaranteed token/latency record.

Agentic runs can be substantially slower and more expensive. Long contracts
may take more than ten minutes; a timeout is not proof of schema rejection.
The verified CLI has no configurable analysis timeout option. Preserve
incomplete evidence, assess incurred cost, and do not automatically resubmit.

For repeats or Standard/Agentic comparisons use
[Eval CU](eval-cu.skill.md), planning the exact model/schema/input matrix and
cost cap first. Keep comparison fields and inputs fixed, snapshot each
configuration, and fail missing results closed.

Record every iteration's cost, including failed calls. Missing usage/charges
remain unknown/null; usage-based pricing is estimated. Finish manifest/report
and root navigation with limitations. A successful smoke test is not STP.

Public examples:
[Agentic contract obligations](../../examples/05-Agentic-Contract-Obligations/)
and [reviewed obligation gold set](../../examples/06-Contract-Obligation-Golden-Set/).
