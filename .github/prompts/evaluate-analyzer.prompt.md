# Prompt: Evaluate Analyzer

Evaluate reviewed correctness, stability, coverage, and cost; decide whether
to accept, reject, or investigate a CU analyzer change.

## Context to supply

- Selected case/iteration and immutable baseline.
- Expected/actual defects, exact changes, and verified tracking bugs.
- Existing analyzer IDs with schema snapshots; API/profile/model.
- Frozen input inventory/hashes; reviewed truth and evaluator/config versions.
- Scale, stability, or predeclared comparison matrix.
- Acceptance/protected-field policy, development/holdout scope, cost budget,
  and stopping rule.

Use [iteration workspaces](../../docs/iteration-workspaces.md) for the canonical
manifest/evidence format. Keep customer material private. Select the next
unused `iterations\NNN` before execution; new configuration, data, or metrics
requires another number. Multiple trials belong inside the planned experiment.

## Execute the requested evaluation

Follow [Eval CU](../skills/eval-cu.skill.md), which contains the command
templates and output contract:

- Ordinary local-file/folder batches go directly through official `cu analyze`
  with native concurrency, `--json`, `--output-dir`, `--report-file`, and
  `--on-existing error`. Use input-only staging folders with manifests/outputs
  outside the source, or explicit `--file` selectors; avoid beta discovery filters.
- Five/ten parallel repeats or multi-analyzer comparisons use
  `tools\cu-experiments\experiment.py plan` with explicit input files,
  followed by `run ... --confirm-cost` only after explicit paid-run approval.
- The helper's concurrency limit is global. It delegates batches, request
  scheduling, and polling to official `cu`; no second CU execution backend.
- Analyzer creation/deletion remains explicit official CLI work outside the
  experiment helper.
- `experiment.json` is the immutable plan/jobs record; separate `run.json`
  holds execution state/outcomes. Preserve native raw results/reports and
  completed execution evidence. Reruns require new paths and cost review,
  not automatic resume/rebilling.

Preview/Agentic evaluation first passes
[the preview compatibility gate](../skills/cu-preview-api.skill.md).

## Evaluate offline

1. Reconcile all planned inputs/analyzers/trials with native per-input statuses
   and available raw results. Include failures and exclusions explicitly.
2. Export native recursive `.result.json` or legacy saved results with the
   offline exporter. Status reports are not extraction data.
3. Use the versioned evaluator and reviewed truth to score values, business
   checks, array/segment retention, and case acceptance.
4. For stability, compare values, missingness, row/segment counts, and
   normalization across every planned trial—not only successful outputs.
5. Evaluate protected-field regressions and expected/actual exemplars across
   the full frozen corpus.
6. Report fill/confidence as diagnostics separately. Missing confidence,
   usage, or latency stays unknown/null; CLI console telemetry does not
   guarantee stable per-input measurements.

Failed/missing outputs fail closed for acceptance. Incomplete matrices or
missing truth make comparisons inconclusive. A status report says whether
inputs completed, not whether extracted answers were correct.

## Required report

Write `{iteration_folder}\report.md`, update its manifest, and synchronize
the root iteration index. Link only actual artifacts.

| Section | Required evidence |
|---|---|
| Hypothesis and changes | Baseline, local defects, expected/actual behavior, verified bugs |
| Scope | Input/schema hashes, truth/evaluator versions, eligible/held-out counts |
| Execution | Actual sanitized commands/working directory, tool/API/model/profile versions, observed IDs/statuses |
| Correctness | Critical fields and case-level gates with units, denominators, rules, sources |
| Coverage/stability | All planned trials, row/segment retention, failures/retries/exclusions |
| Diagnostics | Fill/source/confidence distributions where available |
| Cost and efficiency | Observable timings/usage, cost status/amount/null/currency/basis |
| Decision | Accept/reject/inconclusive, protected behavior, limitations, next hypothesis |

Record cost for every iteration, including layout, repeats, failures/retries,
and paid evaluator calls, or disclose omissions. Usage × documented prices is
estimated; attributable actual charges are measured. Missing evidence is
unknown with a null amount, never zero.

STP needs reviewed correct automatic completion over all eligible cases,
false-accept auditing, human-review/failure rates, and representative holdout
scope. API success, field fill, or high confidence alone is not STP evidence.

## Modality overlays

- [Video](evaluate-analyzer-video.prompt.md): temporal grounding, detection
  correctness, and raw versus post-processed results.
- [Routing](classify-and-route-schema.prompt.md): packet/segment boundaries,
  categories, and per-type extraction.
- [Schema iteration](../skills/iterate-analyzer-schema.skill.md): promotion
  gates and the next controlled hypothesis.
