---
status: ✅ IMPLEMENTED
version: 1.1.0
last_updated: 2026-04-18
replaces: eval-cu.prompt.md, eval-cu-workflow.prompt.md
---

# Prompt: Evaluate Analyzer

Core evaluation workflow for Content Understanding analyzers. Works for all modalities (document, image, video, audio).

> **Video-specific eval**: See `evaluate-analyzer-video.prompt.md` for timestamp validation, keyframe matching, and video-specific KPIs.
> **Classify-and-route eval**: See `classify-and-route-schema.prompt.md` for classification accuracy checks and pipeline testing patterns.

## Goal

Run systematic evals to measure quality, stability, and cost, then decide whether to accept changes or iterate on the schema.

## Select a numbered experiment

Follow [the canonical v1 workspace guide](../../docs/iteration-workspaces.md);
use private workspaces for customer data. Bind `{iteration_folder}` to
`case/iterations/NNN`, and `{output_folder}` to its `outputs/raw/analysis`.
Record the hypothesis, baseline ID, defects/changes, input/schema hashes,
versioned truth/evaluator, acceptance policy, and development/holdout scope.
Do not overwrite completed experiments; changed hypothesis/configuration/
dataset/metrics require a new number. `--iterations N` denotes trials inside
one experiment, not N numbered experiments.
Preserve verified issue/iteration `bugs` links separately from local defect IDs;
follow [tracking bugs](../../docs/iteration-workspaces.md#tracking-bugs).

Use official `cu` for simple calls; the commands below retain `run.py` for
repeat trials, diagnostics, and evaluator-compatible CU-Tools bundles.
The runner backend remains legacy REST, not the official CLI/SDK.
Confirm the resource/configuration and obtain explicit cost approval for
paid scale/stability work before execution.

## Eval Types

### Scale Eval (1×N)
- Run **many documents** once each
- Purpose: Measure coverage and field-level accuracy across document variety
- Use when: Establishing baselines, validating schema before production

### Stability Eval (N×1)
- Run **one document** (or few) multiple times
- Purpose: Measure extraction consistency and detect drift
- Use when: Debugging inconsistent results, tuning confidence thresholds

## Commands

### Scale Eval
```bash
# Run analyzer on many documents
python tools/cu-analyzer-run/run.py \
  --analyzer-id {analyzer_id} \
  --input "{documents_folder}" \
  --output "{output_folder}"

# Export results to CSV
python tools/cu-results-export/export.py \
  --input "{output_folder}" \
  --output "{iteration_folder}/outputs/evaluation/results.csv"
```

### Stability Eval
```bash
# Run same document 10 times
python tools/cu-analyzer-run/run.py \
  --analyzer-id {analyzer_id} \
  --input "{document_path}" \
  --iterations 10 \
  --output "{output_folder}"

# Export results to CSV
python tools/cu-results-export/export.py \
  --input "{output_folder}" \
  --output "{iteration_folder}/outputs/evaluation/results.csv"
```

### Per-Iteration Cost Accounting (Required)

Always record cost status/amount/currency/basis in the manifest, even when
cost is unknown. Run an estimate only with available usage/pricing evidence.

```bash
# From test results (usage-based estimate, not measured charges)
python tools/cu-cost-estimator/generate_cost_summary.py \
  --input "{output_folder}" \
  --output "{iteration_folder}/outputs/evaluation/cost_report.md"

# Quick estimate for planning
python tools/cu-cost-estimator/cu_cost_estimator.py estimate \
  --file-type document \
  --quantity 1000 \
  --model gpt-4.1
```

Include layout, analysis, repeat/retry, failed, and billable evaluator calls
or state exclusions. Price-based calculations are `estimated`, attributable
actual charges `measured`; missing usage/prices stay `unknown` with null
amount, never zero. State the price source/date and cost denominators.

## Required Parameters

| Parameter | Scale Eval (1×N) | Stability Eval (N×1) |
|-----------|------------------|----------------------|
| `--analyzer-id` | Required | Required |
| `--input` | Folder with documents | Single document path |
| `--iterations` | 1 (default) | 10 (recommended) |
| `--output` | Selected iteration's `outputs/raw/analysis` | Same |

## What to Analyze

### For Scale Evals
- Fields with low fill rates (< 80%) — coverage gaps
- Patterns in failed extractions — description improvements needed
- Edge cases that need handling — document variations
- Documents that failed completely — format issues

### For Stability Evals
- Fields that vary between iterations — extraction inconsistency
- Confidence score variance — may need threshold tuning
- Potential non-determinism issues — description ambiguity
- Casing or formatting inconsistencies — normalization needs

## KPIs to Track

These diagnostic targets must be adapted to the modality and workload; they
are not proof of correctness or production-readiness.

| Metric | Description | Target |
|--------|-------------|--------|
| Fill Rate | % of documents where field is populated | >80% |
| Confidence (p50) | Median confidence score | >0.85 |
| Stability Rate | % of iterations with consistent value (N×1) | >95% |
| Latency (p95) | Processing time per document | <5s |
| Cost per doc | Token usage and API costs | Budget-dependent |

For acceptance, measure reviewed critical-field and business-case correctness
with denominators/sources, protected-field regressions, failures, and held-out
coverage. STP needs verified case-level automatic correctness, false accepts,
human review, eligible scope, and audit limitations, not global fill/confidence.

## Report Template

After exporting results, create `{iteration_folder}/report.md`, update its
manifest, and synchronize the root iteration index:

```markdown
# Eval Report: {analyzer_id}

**Run ID**: {run_id}
**Eval Type**: {scale|stability}
**Date**: {timestamp}

## Hypothesis, Inputs, and Execution

Hypothesis/baseline/defect IDs/changes: {manifest}
Input inventory/schema hashes, truth/evaluator versions: {links}
Scope, holdout counts, acceptance and review policy: {definitions}
Exact sanitized commands, working directory, tool/git/API/model, runtime IDs: {evidence}

## Summary

| Metric | Value |
|--------|-------|
| Documents Processed | {count} |
| Successful | {success_count} |
| Failed | {fail_count} |
| Retried Attempts | {retry_count} |
| Repeated Trials | {trial_count} |

## Reviewed Correctness and Acceptance

{metrics with units, denominators, calculation rules, and raw/evaluator sources}
{critical behavior, false accepts, review, failures, holdout and audit limits}

## Fill Rates and Confidence (Diagnostics)

| Field | Fill Rate | Confidence (p50) | Notes |
|-------|-----------|------------------|-------|
| {field} | {rate}% | {conf} | {notes} |

## Issues Found

{list issues observed}

## Recommendations

{schema improvements — propose specific field description changes}

## Cost, Limitations, and Decision

{cost status, amount or null, USD, source/pricing basis, coverage/exclusions}
{accept/reject/inconclusive; protected behavior, limitations, next hypothesis}

## Evidence

{links to manifest, actual raw results, execution metadata, exports/evaluation}
```

## Eval-Driven Improvement Loop

When evaluating, follow this pattern:
1. Read/create the selected iteration manifest and predeclare acceptance rules
2. Run the appropriate eval (scale or stability)
3. Export results and generate report
4. If metrics are below targets, produce an actionable diff plan:
   - Identify specific fields that need improvement
   - Propose concrete description changes
   - State proposed KPI deltas as hypotheses, not measured outcomes
   - Cite exemplar documents showing the issue
5. Record this iteration's cost, limitations, and evidence-backed decision;
   optionally project production cost with explicit assumptions
6. Start the next numbered experiment for any changed configuration, data, or
   metric; keep completed evidence and raw results immutable

## Output Files

```
{iteration_folder}/
├── manifest.json
├── inputs/                  # Schema snapshots, inventory, truth/evaluator
├── outputs/
│   ├── raw/analysis/        # Unchanged runner bundle and attempt metadata
│   └── evaluation/          # Exports, comparisons, cost evidence
└── report.md
```

## See Also

- Full workflow guide: `.github/skills/eval-cu.skill.md`
- Video-specific eval: `.github/prompts/evaluate-analyzer-video.prompt.md`
- Classify-and-route eval: `.github/prompts/classify-and-route-schema.prompt.md`
- Create analyzer: `.github/prompts/generate-analyzer-schema.prompt.md`
- Write field descriptions: `.github/prompts/write_schema_fields.prompt.md`
