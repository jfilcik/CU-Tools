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

---

## Workflow Steps

### Step 1: Configure Eval

Gather required information:

| Parameter | Scale Eval (1×N) | Stability Eval (N×1) |
|-----------|------------------|----------------------|
| Analyzer ID | Required | Required |
| Input documents | Folder with 20-100+ docs | 1-3 specific documents |
| Iterations | 1 (default) | 10 (recommended) |
| Output folder | Required | Required |

**Example prompts**:

For scale eval:
```
I'll run a scale eval on your analyzer.

Analyzer ID: invoice-v1
Documents: Issues/Acme/test_docs/ (47 files found)
Iterations: 1

This will process 47 documents to measure coverage. Proceed?
```

For stability eval:
```
I'll run a stability eval on your analyzer.

Analyzer ID: invoice-v1
Document: Issues/Acme/samples/invoice_001.pdf
Iterations: 10

This will run the same document 10 times to measure consistency. Proceed?
```

### Step 2: Run Analysis

**Tool**: `tools/cu-analyzer-run/run.py`

**Scale eval command**:
```bash
python tools/cu-analyzer-run/run.py \
  --analyzer-id {analyzer_id} \
  --input {documents_folder} \
  --output {output_folder}
```

**Stability eval command**:
```bash
python tools/cu-analyzer-run/run.py \
  --analyzer-id {analyzer_id} \
  --input {document_path} \
  --iterations 10 \
  --output {output_folder}
```

**Output**:
- `metadata.json` - Run configuration and summary
- `results/{document}.json` - Result for each document/iteration

### Step 3: Export Results

**Tool**: `tools/cu-results-export/export.py`

**Command**:
```bash
python tools/cu-results-export/export.py \
  --input {output_folder} \
  --output {output_folder}/results.csv
```

**Output**:
- `results.csv` or `results.xlsx` - Wide table with extracted values
- `results.summary.json` - Fill rates and statistics

### Step 3.5: Estimate Costs (Optional)

**Tool**: `tools/cu-cost-estimator/`

Use cost estimation to project production costs based on test results:

**From test results (usage-based - most accurate)**:
```bash
python tools/cu-cost-estimator/generate_cost_summary.py \
  --input {output_folder} \
  --output {output_folder}/cost_report.md
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

### Step 4: Generate Report

Create a markdown summary report at `{output_folder}/REPORT.md`:

**Report template**:
```markdown
# Eval Report: {analyzer_id}

**Run ID**: {run_id}  
**Eval Type**: {scale|stability}  
**Date**: {timestamp}

## Summary

| Metric | Value |
|--------|-------|
| Documents Processed | {count} |
| Successful | {success_count} |
| Failed | {fail_count} |
| Total Iterations | {total_iterations} |

## Fill Rates (Coverage)

| Field | Fill Rate | Confidence (p50) | Notes |
|-------|-----------|------------------|-------|
| {field1} | {rate}% | {conf} | {notes} |
| ... | ... | ... | ... |

## Issues Found

{list of issues observed}

## Recommendations

{recommendations for schema improvements}

## Files

- Raw results: `results/`
- Export: `results.csv`
- Metadata: `metadata.json`
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

---

## Example: Scale Eval Session

```
User: Run a scale eval on my invoice-v1 analyzer with the documents in Issues/Acme/invoices/

Copilot: I'll run a scale eval on your invoice-v1 analyzer.

Configuration:
- Analyzer: invoice-v1
- Documents: Issues/Acme/invoices/ (52 PDF files)
- Eval type: Scale (1×N)
- Output: Issues/Acme/test_results/scale_20260126/

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
3. Consider adding VendorLogo field for logo-based identification

Full report: Issues/Acme/test_results/scale_20260126/REPORT.md
```

---

## Example: Stability Eval Session

```
User: Check the stability of invoice-v1 on invoice_007.pdf

Copilot: I'll run a stability eval (10 iterations) on invoice_007.pdf.

Configuration:
- Analyzer: invoice-v1  
- Document: Issues/Acme/samples/invoice_007.pdf
- Iterations: 10
- Output: Issues/Acme/test_results/stability_20260126/

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
{output_folder}/
├── metadata.json           # Run configuration
├── results/
│   ├── doc1.json          # Individual results
│   ├── doc1_iter002.json  # (stability eval iterations)
│   └── ...
├── results.csv            # Exported table
├── results.summary.json   # Statistics
└── REPORT.md              # Summary report
```

---

## KPIs to Track

When evaluating, consider these metrics per field:

| Metric | Description | Target |
|--------|-------------|--------|
| Fill Rate | % of documents where field is populated | >80% |
| Confidence (p50) | Median confidence score | >0.85 |
| Stability Rate | % of iterations with consistent value (N×1) | >95% |
| Accuracy/F1 | Match against ground truth labels | Varies |
| Latency (p95) | Processing time per document | <5s |
| Cost per doc | Token usage and API costs | Budget-dependent |

---

## Related Tools

- `cu-analyzer-run` - Execute analysis
- `cu-results-export` - Export to CSV/Excel
- `cu-cost-estimator` - Estimate processing costs

## Related Skills

- `generate-analyzer.skill.md` - Create new analyzer (often done before evaluating)

## Related Prompts

- `evaluate-analyzer.prompt.md` - Quick eval reference and report template
- `write_schema_fields.prompt.md` - Improve field descriptions based on eval results
