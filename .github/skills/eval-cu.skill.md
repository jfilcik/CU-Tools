---
name: eval-cu
description: Evaluates CU analyzers with official cu batches or cost-approved parallel experiments, then offline export, reviewed correctness, stability, and cost reporting.
---

# Skill: Eval CU

Evaluate quality against reviewed truth, not merely whether analysis succeeds.
Use [Iterate Analyzer Schema](iterate-analyzer-schema.skill.md) for shared
planning/promotion and [iteration workspaces](../../docs/iteration-workspaces.md)
for manifests, bug links, metric definitions, and STP requirements.

## 1. Declare scope before execution

Choose the case and next unused `iterations\NNN`; customer material stays
private. Freeze/hash inputs and every analyzer schema. Record hypothesis,
baseline, expected/actual defects, verified bugs, truth/evaluator versions,
acceptance rules, development/holdout split, budget, and stopping conditions.

| Eval | Purpose | Execution |
|---|---|---|
| Scale (1×N) | Coverage and reviewed accuracy across varied inputs | Native file/folder batch |
| Stability (N×1) | Value, row, and segment consistency | Explicit-file experiment with repeats |
| Comparison | Baseline/candidate on identical inputs | Predeclared multi-analyzer experiment |

New configurations/scopes need a new numbered experiment. Trials within the
planned matrix stay inside it. Obtain explicit cost approval for the complete
input × analyzer × trial scope before running analysis.

## 2. Execute with official `cu`

### Ordinary folder evaluation

Run from the repository root after configuring the official CLI as described
in [README](../../README.md). Replace placeholders; the source folder must
contain only staged input files matching the frozen inventory. Keep manifests,
schemas, and outputs outside the source. The verified beta CLI's discovery
filters can miss files; use input-only staging or explicit file selectors.

```powershell
cu analyze --source "{documents_folder}" `
  --analyzer invoice_001 --json --api-version 2025-11-01 `
  --concurrency 5 --yes --on-existing error `
  --output-dir "{iteration_folder}\outputs\raw\analysis" `
  --report-file "{iteration_folder}\outputs\raw\analysis-status.json"
```

Add `--recursive` only for the intended inventoried subfolders. For one file,
replace `--source ...` with `--file "{document_path}"`; repeat `--file` for
multiple explicit files without directory discovery. Native concurrency
is 1–32. Use `--profile NAME` when required and the analyzer's exact API
version; [preview compatibility](cu-preview-api.skill.md) comes before
Agentic corpus runs.

### Ten parallel repeats

```powershell
python tools\cu-experiments\experiment.py plan `
  --input "{document_path}" --analyzer invoice_001 `
  --iterations 10 --concurrency 10 --api-version 2025-11-01 `
  --output "{iteration_folder}\outputs\raw\experiment"
```

Planning is offline. Review the matrix, staged input hashes, API/profile, and
cost. Only after explicit approval:

```powershell
python tools\cu-experiments\experiment.py run `
  "{iteration_folder}\outputs\raw\experiment" --confirm-cost
```

For five parallel repeats set both counts to 5 when planning. Repeat
`--input FILE` or `--analyzer ID` to expand the fixed matrix. Concurrency is
global across native CLI processes. The helper does not create/delete
analyzers or implement CU submission/polling; native `cu` executes each
analyzer's staged-file batch. Select an alternate official executable with
`run --cu-executable PATH` if needed. Reruns require new paths and renewed
cost review; no automatic resume/rebilling.

## 3. Preserve and inspect actual outputs

- Native JSON can contain SDK-shaped contents or an LRO envelope with
  `result.contents`; inspect the actual payload. Native results are
  `.result.json`, possibly under source-relative subdirectories.
- For repeated work, `experiment.json` (`cu-experiments/v1`) is the immutable
  plan/jobs record. Separate `run.json` (`cu-experiments/run/v1`) records
  execution state/outcomes; execution never overwrites the plan.
- Frozen trial files are
  `inputs\trial-NNNN\input-NNNN\file`. Per-analyzer results are
  `batches\analyzer-NNNN\results\trial-NNNN\input-NNNN\file.result.json`.
  Each analyzer batch also retains `native-report.json`, `stdout.txt`, and
  `stderr.txt` alongside `results`. Preserve these with plan hashes and
  identity mappings; keep completed execution evidence unchanged.
- Reconcile all intended inputs/trials, exit statuses, and failures before
  scoring. A report is execution evidence, not extracted data or accuracy.
- `--usage` and `--time` print separate console telemetry; they do not
  guarantee persisted per-file usage or latency. Missing values remain
  unknown/null. Do not scrape console text as a stable schema or divide total
  elapsed time to invent per-input latency.

## 4. Export and score offline

Set `{raw_folder}` to this experiment's native analysis or experiment output:

```powershell
python tools\cu-results-export\export.py `
  --input "{raw_folder}" `
  --output "{iteration_folder}\outputs\evaluation\results.csv" --diagnose
python tools\cu-cost-estimator\generate_cost_summary.py `
  "{raw_folder}" --json `
  --output "{iteration_folder}\outputs\evaluation\cost-summary.json"
```

The offline tools accept native recursive results and legacy saved evidence,
excluding CLI status reports from analysis data. Missing usage is unknown,
not zero. Retaining old saved results does not require another service backend.

Use the case's versioned evaluator for reviewed field and case correctness,
array/segment retention, stability, false accepts, and human-review rates.
Count failed/missing planned outputs fail-closed; do not evaluate only
survivors. Compare matched inputs and all protected fields.

Cost is required per iteration: status, amount/null, USD, evidence basis,
price source/date, scope, and exclusions. Usage × price is estimated, not
measured charges. Include layout, failed/retried/repeated calls, and billable
evaluation or disclose missing coverage. Do not silently apply defaults to
unsupported models or infer usage from successful output.

## 5. Report the decision

Create `{iteration_folder}\report.md`, update its manifest, and synchronize
the root index. Link actual artifacts, not planned filenames.

Required sections:

1. Hypothesis, baseline, expected/actual defects, exact changes, and bugs.
2. Frozen scope, schema/input hashes, truth/evaluator, acceptance/holdout policy.
3. Actual sanitized commands, CLI/tool/API/model/profile versions and observed
   IDs; input/trial success, failure, retry, and exclusion counts.
4. Reviewed correctness and case acceptance with units, denominators,
   calculation rules, and raw/evaluator sources.
5. Diagnostic fill/confidence and stability, separate from correctness.
6. Observable latency/usage, cost status/basis, evidence gaps, and limitations.
7. Accept/reject/inconclusive decision and protected-behavior regression checks.

Fill >80% or confidence >0.85 may be workload-specific diagnostic targets,
not production gates. STP requires reviewed correct automatic completion
over all eligible cases, false-accept auditing, review/failure rates, and
representative holdout evidence. Without these, label STP unverified.

Use [video evaluation](../prompts/evaluate-analyzer-video.prompt.md) for
timestamp/detection metrics and
[routing](generate-analyzer-classify-route.skill.md) for packet boundaries
and per-category correctness.
