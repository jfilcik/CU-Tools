# 001 — Reproduction baseline

**Status: planned — not run.** No analysis or evaluation has been performed.
This document is a plan, not evidence of successful extraction.

- [Iteration manifest](manifest.json)
- [Issue manifest](../../manifest.json)
- [Case overview](../../README.md)

## Hypothesis and baseline

The selected analyzer can reproduce the reported behavior on the frozen input set.

Baseline iteration: none. Defects, expected behavior, actual behavior, scope,
and deliberate changes: not provided. Distinguish reported symptoms from
verified observations and suspected causes from confirmed causes.

## Inputs and reproducibility

No documents, schema, truth, or evaluator are supplied. Before running, link
the exact document inventory/hashes, schema snapshots/hashes, versioned
ground truth and evaluator/configuration, development/holdout membership,
critical-field checks, and acceptance/review rules in `manifest.json`.

## Execution

Not run. After execution, record exact sanitized commands and working
directory, tool versions/git commits, API/model/deployment/region, analyzer
IDs, operation/request/run IDs, timestamps, concurrency, timeout/retry policy,
and successful/failed/retried attempt counts. Unknown values remain unknown.
Never include keys, tokens, or SAS query strings.

## Evidence and evaluation

There are no raw results or evaluation artifacts. Preserve future raw
responses under `outputs/raw/`; write only derived exports, comparisons, and
evaluator results to `outputs/evaluation/`. Link actual files after creation.

For each metric, report its value, unit, denominator, evaluation rule, and
source. Include failures in acceptance accounting; do not score only
survivors. For STP, record eligible and held-out scope, critical-field and
business-rule correctness, auto-accept audit coverage, false accepts, human
review, failures/rejections, and limitations. Fill/confidence is not STP.

## Iteration cost

**Unknown; amount not available (USD).** No usage, price calculation, or
attributable charge evidence is available. This is not a zero-cost result.

After execution, include layout, analysis, repeats/retries, and billable
evaluation calls or list exclusions. Label price-based calculations
`estimated`, attributable actual charges `measured`, and missing cost
`unknown`. Give price/source/date assumptions and relevant denominators.

## Decision and next experiment

Do not run until inputs, acceptance criteria, and any required cost approval
are recorded. No promotion or production-readiness claim can be made.
Record the supported decision after evaluation. Create `002` rather than
overwriting a finished baseline when the hypothesis, configuration, dataset,
or measurement changes.
