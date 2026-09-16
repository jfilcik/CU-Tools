---
name: iterate-analyzer-schema
description: Runs evidence-driven CU schema experiments with immutable baselines, official cu execution, offline diagnostics, repeated parallel trials, and correctness promotion gates. Use to improve consistency, compare versions, or investigate regressions.
---

# Skill: Iterate Analyzer Schema

This is the common experiment workflow. Use task-specific skills for
[initial creation](generate-analyzer.skill.md),
[routing](generate-analyzer-classify-route.skill.md),
[video](generate-analyzer-video.skill.md), or [preview](cu-preview-api.skill.md).
[Agents.md](../../Agents.md) owns API rules;
[iteration workspaces](../../docs/iteration-workspaces.md) owns the manifest,
bug-link, cost, and STP contracts. Do not invent a second workspace format.

## 1. Select a numbered experiment

- Keep customer samples, truth, schemas, and outputs private; reusable tools
  and approved public examples stay in CU-Tools.
- Use the next unused `case\iterations\NNN`. Baseline `001` is immutable;
  candidates record `baseline_iteration`, expected/actual defects, and exact
  changes. Link verified product bugs in the relevant root/iteration `bugs`
  arrays, separately from local defect IDs.
- State one coherent, reusable hypothesis and a safety/budget stopping cap.
  Do not tune to filenames, customer names, coordinates, page numbers, or
  literal sample answers.
- Freeze/hash selected inputs and all submitted schema snapshots. Version
  truth, evaluator/config, acceptance rules, and development/holdout membership.
- A changed hypothesis, configuration, dataset, evaluator, or metric requires
  a new number. Repeated trials and a predeclared baseline/candidate comparison
  matrix are within one experiment; later matrix changes require another.

Keep exact schemas under `inputs\schemas\`, native responses and execution
evidence under `outputs\raw\`, and derived exports/comparisons under
`outputs\evaluation\`. Use the canonical `manifest.json` and `report.md`;
the helper's immutable `experiment.json` plan/jobs (`cu-experiments/v1`) and
separate `run.json` execution state/outcomes (`cu-experiments/run/v1`)
supplement, not replace, them. Execution must not overwrite the frozen plan.

## 2. Establish reviewed behavior

Define denominators and evidence sources for:

1. **Correctness:** reviewed exact/rule-based expectations and business checks.
2. **Coverage:** every required row, segment, repeated entity, and input.
3. **Stability:** distinct values, population, row/segment-count drift.
4. **False positives:** cross-field leakage and semantically wrong fallbacks.
5. **Efficiency:** observable latency, usage, and attributable/estimated cost.
6. **Diagnostics:** fill, source coverage, and confidence where present.

Record cause status as unknown/suspected/confirmed. A missing value with high
confidence does not prove a reading-order or service defect; isolate against
source text, structure, and reviewed truth. See
[field diagnostics](iterate-schema.skill.md) for targeted investigation.

For STP, predeclare eligible cases, critical-field and business-rule gates,
automatic acceptance/review policy, false-accept auditing, and holdout scope.
An API success, filled field, or confident answer is not reviewed correctness.

## 3. Validate and prepare execution

Official `cu` is the sole CU execution backend. Use its structural/spec
validation and the offline local quality validator:

```powershell
cu analyzer validate "{iteration_folder}\inputs\schemas\candidate.json" `
  --api-version 2025-11-01 --spec
python tools\cu-analyzer-validate\cu_analyzer_validator.py `
  "{iteration_folder}\inputs\schemas\candidate.json" --api-version 2025-11-01
```

Use explicit preview versions when needed. Create each new analyzer with
`cu analyzer create --name VERSIONED_ID --schema SCHEMA --api-version VERSION`.
For dependencies, use the offline schema planner and reviewed dependency-first
official commands in the [routing skill](generate-analyzer-classify-route.skill.md).
Analyzer creation/deletion is never part of the experiment helper.

Snapshot the observed definition of any reused analyzer before planning:

```powershell
cu analyzer show invoice_001 > "{iteration_folder}\inputs\schemas\baseline-observed.json"
```

Retain the original submitted schema separately; observed definitions may
contain service metadata. Record CLI package/version, actual sanitized
commands and working directory, API/model/profile/resource identity, schema
hashes, and observed analyzer/request IDs. Never save credentials.

## 4. Choose the smallest execution path

- **One file or ordinary folder batch:** use native `cu analyze` as in
  [Eval CU](eval-cu.skill.md). Native `--concurrency` is 1–32.
- **Repeated trials or multiple analyzers:** use the task-specific experiment
  helper. It snapshots explicit files and plans the full matrix offline.
  Do not use it for ordinary directory discovery.

Five parallel repeats of one file:

```powershell
python tools\cu-experiments\experiment.py plan `
  --input "{document_path}" --analyzer invoice_002 `
  --iterations 5 --concurrency 5 --api-version 2025-11-01 `
  --output "{iteration_folder}\outputs\raw\experiment"
```

Review the planned file hashes, analyzers, repeats, API/profile, **total**
request count, and cost assumptions. Only after explicit paid-run approval:

```powershell
python tools\cu-experiments\experiment.py run `
  "{iteration_folder}\outputs\raw\experiment" --confirm-cost
```

For ten parallel repeats use `--iterations 10 --concurrency 10` at planning
time. Repeat `--input FILE` for more frozen documents and `--analyzer ID` for
a comparison, snapshotting each analyzer's schema. The request count is
inputs × analyzers × iterations. Use `--profile NAME` at planning time when
needed; `run --cu-executable PATH` selects the intended official executable.

Concurrency is a **global** request cap, divided among the native CLI
processes—not multiplied per analyzer. The helper invokes one native batch per
analyzer over distinct staged trial files; native `cu` owns scheduling,
submission, and polling. There is no native repeat or multi-analyzer flag.
Use a new output directory for any rerun; there is no automatic resume or
rebilling. Never restart uncertain failures without assessing incurred cost.

## 5. Evaluate the complete matrix

Use [Eval CU](eval-cu.skill.md) for the exact helper artifact paths, offline
export, and reporting. Preserve native `.result.json` files, CLI status reports,
the immutable plan/hashes, and the separate `run.json` execution record/logs.
Keep completed evidence unchanged. Status reports are not analysis data,
accuracy scores, or guaranteed
per-input token/latency records. Missing usage or timings stay unknown/null;
console telemetry is not a stable machine-readable schema.

Evaluate all planned inputs and trials, including failures. Failed/missing
outputs fail closed for case acceptance; incomplete comparisons are
inconclusive, not correct null values. Match baseline/candidate by the frozen
input identity and schema, not merely filenames in different output folders.
Rerun the full controlled corpus, not only the motivating failure.

## 6. Apply promotion gates and close

Promote only when required trials complete, critical correctness and coverage
pass, false-positive leakage does not increase, protected behavior does not
regress, and schema language passes the anti-hard-coding review. Efficiency
cannot compensate for correctness regressions.

Complete report/manifest with source-linked metrics and denominators, reviewed
expected/actual examples, limitations, accept/reject/inconclusive decision,
and the next hypothesis. Record every iteration's cost, including layout,
repeats, failures/retries, and billable evaluation, or disclose exclusions.
Price × usage is estimated, actual attributable charges are measured, and
missing evidence means unknown/null—not zero.

Synchronize the root iteration index; preserve finished evidence. Delete only
actually-created, owned analyzers after explicit cleanup authorization and
dependency checks, in reverse creation order. Retain evidence even when the
experiment is rejected or blocked.
