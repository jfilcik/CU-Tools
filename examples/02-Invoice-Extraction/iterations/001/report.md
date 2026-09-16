# 001 — Existing public invoice baseline

**Planned — not run.** This addition provides iteration navigation, not
new analyzer results. No API analysis, paid run, or evaluation was performed.

- [Issue manifest](../../manifest.json)
- [Iteration manifest and input hashes](manifest.json)
- [Original tutorial](../../README.md)
- [Existing invoice](../../samples/invoice.pdf)
- [Existing schema](../../schemas/invoice_v1.json)

## Hypothesis

The existing invoice schema can extract the selected public invoice's critical fields correctly against reviewed source values.

This is the initial baseline; there is no prior iteration or verified defect.
Only `invoice.pdf` is selected. The existing `receipt.png` and legacy
`layout_results/`, `test_results/`, and `reports/` remain untouched and are not
claimed as evidence for this experiment.

## Plan before execution

1. Preserve the shared sample and verify the manifest's SHA-256 hashes.
2. Copy the selected schema into `inputs/schemas/`, hash the snapshot, and
   update the input link before analysis; do not edit the shared original.
3. Supply reviewed truth, a versioned evaluator/configuration, critical-field
   and business-rule acceptance checks, and input inventory. A single invoice
   is development/reproduction scope, not a representative holdout.
4. Select API/model/deployment/region, analyzer identity, tools/versions,
   sanitized commands, and cost budget/approval. None has been executed.
5. Save responses/attempt metadata in `outputs/raw/`, derived evaluation and
   exports in `outputs/evaluation/`, and link actual files in the manifest.

Use official `cu` for simple calls; use the existing CU-Tools runners for
repeats, lifecycle orchestration, diagnostics, or their compatible output
bundles. Follow the [workspace guide](../../../../docs/iteration-workspaces.md).

## Results and cost

- Quality, latency, usage, success/failure/retry counts: **not measured**.
- Cost: **unknown**, amount `null`, currency USD. No usage-based estimate or
  attributable charge evidence exists; do not interpret missing cost as zero.
- Straight-through processing: **unverified**. Field fill/confidence alone
  would not establish it; reviewed correctness, eligible scope, holdout,
  false-accept and human-review rates are required.

## Decision

Keep this iteration planned until prerequisites are supplied. After a real
run, report metrics with denominators, evidence sources, cost basis, and an
accept/reject/inconclusive decision. Put any next hypothesis, configuration,
dataset, or metric change in `002`; never overwrite a finished baseline.
