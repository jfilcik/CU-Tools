---
status: ✅ IMPLEMENTED
version: 2.0.0
last_updated: 2026-01-30
---

# Skill: Eval CU

Evaluate your Content Understanding analyzer against baselines with systematic evals.

## Purpose

**Evals are the contract** — they define what good looks like for your extraction pipeline. This skill helps you:
- Run systematic evaluations on representative document sets
- Compare results against baselines to detect regressions
- Generate evidence bundles (metrics, diffs, exemplars) for accept/reject decisions
- Enable the *generate → eval → improve* feedback loop

## Why Evals Matter

Coding agents (and humans) get reliable by **checking their work** against well-defined evals, then applying targeted fixes, and checking again. Without evals there's no baseline, no regression guardrails, and no way to know if changes helped.

## Eval Types

### Scale Eval (1×N)
- Run **many documents** once each
- Purpose: Measure coverage, field-level accuracy, and fill rates across document variety
- Use when: Validating schema before production, establishing baselines

### Stability Eval (N×1)  
- Run **one document** (or few) multiple times
- Purpose: Measure extraction consistency and detect randomness/drift
- Use when: Debugging inconsistent results, tuning confidence thresholds

## Select the experiment before running

Follow [the canonical v1 workspace guide](../../docs/iteration-workspaces.md).
Use a private case for customer data. Bind `{iteration_folder}` to the selected
`case/iterations/NNN` and `{output_folder}` to its `outputs/raw/analysis`.
Record hypothesis, baseline ID, defects, exact changes, input/schema hashes,
versioned truth/evaluator, acceptance rules, and development/holdout scope.
New configuration, dataset, hypothesis, or metric changes need a new number.
`--iterations 10` means ten trials inside one experiment, not ten experiments.
Link verified product bugs in the root and relevant iteration `bugs` arrays,
separately from local defects; follow [tracking bugs](../../docs/iteration-workspaces.md#tracking-bugs).

Use official `cu` for routine analysis; use the existing runner below when
evaluation needs repeats, diagnostics, or its compatible bundle. Runners still
use their legacy REST backend, not the official CLI/SDK. Keep CLI and runner
resource configuration aligned as described in `Agents.md`.

---

## Workflow Steps

### Step 1: Configure Eval

Gather required information:

| Parameter | Scale Eval (1×N) | Stability Eval (N×1) |
|-----------|------------------|----------------------|
| Analyzer ID | Required | Required |
| Input documents | Folder with 20-100+ docs | 1-3 specific documents |
| Repeated trials (`--iterations`) | 1 (default) | 10 (subject to cost approval) |
| Output folder | Selected iteration's `outputs/raw/analysis` | Same |
| API version | Explicit when preview | Explicit when preview |

**Example prompts**:

For scale eval:
```
I'll run a scale eval on your analyzer.

Analyzer ID: invoice-v1
Documents: <private-case>/inputs/documents/ (report actual inventoried count)
Repeated trials: 1

State the expected billable scope, budget/estimate and unknowns; obtain cost approval.
```

For stability eval:
```
I'll run a stability eval on your analyzer.

Analyzer ID: invoice-v1
Document: <private-case>/inputs/documents/invoice_001.pdf
Repeated trials: 10

This will run the same document 10 times to measure consistency. Proceed?
```

### Step 2: Run Analysis

**Tool**: `tools/cu-analyzer-run/run.py`

**Scale eval command**:
```bash
python tools/cu-analyzer-run/run.py \
  --analyzer-id {analyzer_id} \
  --input "{documents_folder}" \
  --output "{output_folder}"
```

When the analyzer uses a preview-only contract, append the exact
`--api-version` used to create it. For agentic preview runs, follow
`cu-preview-api.skill.md`: one file per request, short smoke test first, and
explicit cost confirmation before scale or repeated runs.

For a Standard-vs-Agentic comparison, use separate numbered experiments linked
by `baseline_iteration`; keep the input documents and
`fieldSchema` identical, run Standard first, clean up its analyzer, and then run
Agentic. Score failed documents fail-closed rather than reporting only
survivors. 

**Stability eval command**:
```bash
python tools/cu-analyzer-run/run.py \
  --analyzer-id {analyzer_id} \
  --input "{document_path}" \
  --iterations 10 \
  --output "{output_folder}"
```

**Output**:
- `metadata.json` - Run configuration and summary
- `results/{document}.json` - Result for each document/iteration

### Step 3: Export Results

**Tool**: `tools/cu-results-export/export.py`

**Command**:
```bash
python tools/cu-results-export/export.py \
  --input "{output_folder}" \
  --output "{iteration_folder}/outputs/evaluation/results.csv"
```

**Output**:
- `results.csv` or `results.xlsx` - Wide table with extracted values
- `results.summary.json` - Fill rates and statistics

### Step 3.5: Account for This Iteration's Cost (Required)

**Tool**: `tools/cu-cost-estimator/`

Always populate the iteration manifest's cost status, amount/null, currency,
and basis. Use estimates where usage/pricing exist; otherwise record unknown
with the missing evidence. Unknown does not mean zero.

**From test results (usage-based estimate, not actual charge evidence)**:
```bash
python tools/cu-cost-estimator/generate_cost_summary.py \
  --input "{output_folder}" \
  --output "{iteration_folder}/outputs/evaluation/cost_report.md"
```

**Quick estimate for planning**:
```bash
python tools/cu-cost-estimator/cu_cost_estimator.py estimate \
  --file-type document \
  --quantity 1000 \
  --model gpt-4.1
```

**Output**:
- Cost breakdown by component (content extraction, tokens, model usage)
- Per-document and total cost estimates
- Comparison across deployment types (global vs data zone)

Include layout, failed/retried/repeated requests, and billable evaluator calls,
or declare exclusions. A price sheet applied to measured tokens is still
`estimated`; `measured` requires attributable actual charges. Report scope,
pricing source/date, model, currency, and document/acceptance denominators.

### Step 4: Generate Report

Create the summary at `{iteration_folder}/report.md`, update its manifest, and
synchronize the root iteration index. Link existing outputs only.

**Report template**:
```markdown
# Eval Report: {analyzer_id}

**Run ID**: {run_id}  
**Eval Type**: {scale|stability}  
**Date**: {timestamp}

## Hypothesis and Scope

Hypothesis: {one sentence}
Baseline: {prior iteration or none}
Defects/changes: {identifiers and differences}
Inputs, schema hashes, truth/evaluator versions: {manifest links}
Development/holdout counts and acceptance/review policy: {scope}
Exact sanitized commands, tool/git/API/model versions, runtime IDs: {evidence}

## Summary

| Metric | Value |
|--------|-------|
| Documents Processed | {count} |
| Successful | {success_count} |
| Failed | {fail_count} |
| Repeated Trials | {trial_count} |
| Retried Attempts | {retry_count} |

## Correctness and Acceptance

Report reviewed correctness and case-level STP, false-accept, human-review,
failure/rejection counts and rates only where supported. Every metric needs
a denominator, unit, calculation rule, and raw/evaluator source link.
State exclusions and holdout/audit limits; missing output fails closed.

## Fill Rates and Confidence (Diagnostics, Not STP)

| Field | Fill Rate | Confidence (p50) | Notes |
|-------|-----------|------------------|-------|
| {field1} | {rate}% | {conf} | {notes} |
| ... | ... | ... | ... |

## Issues Found

{list of issues observed}

## Recommendations

{recommendations for schema improvements}

## Cost and Decision

Cost: {measured|estimated|unknown|not_applicable}; amount: {number or null} USD.
Basis, source, coverage, pricing assumptions, exclusions: {evidence}
Decision: {accept|reject|inconclusive}, with limitations and next hypothesis.

## Files

- Manifest: `manifest.json`
- Raw results and metadata: `outputs/raw/analysis/`
- Exports and evaluation: `outputs/evaluation/`
```

### Step 5: Review and Recommend

For **scale evals**, analyze:
- Fields with low fill rates (< 80%) — indicates coverage gaps
- Patterns in failed extractions — may need description improvements
- Edge cases that need handling — document variations

For **stability evals**, analyze:
- Fields that vary between iterations — extraction inconsistency
- Confidence score variance — may need threshold tuning
- Potential non-determinism issues — description ambiguity

These diagnostic thresholds do not establish correctness or STP. Apply the
predeclared reviewed-truth and case-level gates, including failures, false
accepts, review, protected behavior, holdout limitations, and cost.

---

## Example: Scale Eval Session

Illustrative dialogue only, not results for the selected case:

```
User: Run a scale eval on my invoice_v1 analyzer with the documents in my private case.

Copilot: I'll run a scale eval on your invoice-v1 analyzer.

Configuration:
- Analyzer: invoice-v1
- Documents: <private-case>/inputs/documents/ (52 PDF files)
- Eval type: Scale (1×N)
- Output: <private-case>/iterations/002/outputs/raw/analysis/

Running analysis...

[Progress: 52/52 documents processed]

Results:
✓ 50 successful
✗ 2 failed (error reading document)

Exporting to CSV...

## Eval Report

| Field | Fill Rate | Confidence (p50) |
|-------|-----------|------------------|
| InvoiceNumber | 100% | 0.95 |
| InvoiceDate | 96% | 0.92 |
| VendorName | 88% | 0.87 |
| TotalAmount | 100% | 0.98 |
| LineItems | 94% | 0.89 |

### Issues Found

1. **VendorName (88%)**: 6 documents missing vendor name
   - 4 had vendor info in different location (footer vs header)
   - 2 had vendor name as logo only (no text)

2. **InvoiceDate (96%)**: 2 documents with date in non-standard format

### Recommendations

1. Update VendorName description to check both header and footer
2. Add examples of date formats to InvoiceDate field
3. Route image-only vendor identification to review; field descriptions operate on extracted text/structure.

Full report: <private-case>/iterations/002/report.md
The real report must also include reviewed correctness, denominators, raw
sources, and this iteration's cost; these illustrative diagnostics are not STP.
```

---

## Example: Stability Eval Session

Illustrative dialogue only. A stability configuration change is a new
numbered experiment; ten repeats remain inside it.

```
User: Check the stability of invoice-v1 on invoice_007.pdf

Copilot: I'll run a stability eval (10 iterations) on invoice_007.pdf.

Configuration:
- Analyzer: invoice-v1  
- Document: <private-case>/inputs/documents/invoice_007.pdf
- Iterations: 10
- Output: <private-case>/iterations/003/outputs/raw/analysis/

Running 10 iterations...

## Stability Eval Results

| Field | Consistent? | Unique Values | Confidence Variance |
|-------|-------------|---------------|---------------------|
| InvoiceNumber | ✓ Yes | 1 | 0.01 |
| InvoiceDate | ✓ Yes | 1 | 0.02 |
| VendorName | ✗ No | 2 variants | 0.08 |
| TotalAmount | ✓ Yes | 1 | 0.00 |

### Inconsistency Found

**VendorName** showed 2 different values across 10 runs:
- "Acme Corporation" (7 times)
- "ACME CORPORATION" (3 times)

This appears to be a casing inconsistency. The field description should 
specify the expected casing format.

### Recommendation

Update VendorName description to specify: "Extract vendor name with 
original casing as it appears in the document."
```

---

## Output Artifacts

```
{iteration_folder}/
├── manifest.json
├── inputs/                    # Schemas, corpus inventory, truth/evaluator
├── outputs/
│   ├── raw/analysis/           # Original runner bundle, including metadata
│   └── evaluation/             # Exports, comparisons, cost basis
└── report.md
```

---

## KPIs to Track

When evaluating, consider these metrics per field:

Targets below are illustrative diagnostics, not production acceptance gates;
set appropriate thresholds for the actual modality, workload, and API.

| Metric | Description | Target |
|--------|-------------|--------|
| Fill Rate | % of documents where field is populated | >80% |
| Confidence (p50) | Median confidence score | >0.85 |
| Stability Rate | % of iterations with consistent value (N×1) | >95% |
| Accuracy/F1 | Match against ground truth labels | Varies |
| Latency (p95) | Processing time per document | <5s |
| Cost per doc | Token usage and API costs | Budget-dependent |

For any rate, define the denominator and source. For STP use document/business
case correctness and holdout evidence, not an average of field-fill scores.

---

## Related Tools

- `cu-analyzer-run` - Execute analysis
- `cu-results-export` - Export to CSV/Excel
- `cu-cost-estimator` - Estimate processing costs

## Related Skills

- `generate-analyzer.skill.md` - Create new analyzer (often done before evaluating)
- `cu-preview-api.skill.md` - Preview API compatibility, test resource, and cost gate

## Related Prompts

- `evaluate-analyzer.prompt.md` - Quick eval reference and report template
- `write_schema_fields.prompt.md` - Improve field descriptions based on eval results
