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
  --input {documents_folder} \
  --output {output_folder}

# Export results to CSV
python tools/cu-results-export/export.py \
  --input {output_folder} \
  --output {output_folder}/results.csv
```

### Stability Eval
```bash
# Run same document 10 times
python tools/cu-analyzer-run/run.py \
  --analyzer-id {analyzer_id} \
  --input {document_path} \
  --iterations 10 \
  --output {output_folder}

# Export results to CSV
python tools/cu-results-export/export.py \
  --input {output_folder} \
  --output {output_folder}/results.csv
```

### Cost Estimation (Optional)
```bash
# From test results (usage-based - most accurate)
python tools/cu-cost-estimator/generate_cost_summary.py \
  --input {output_folder} \
  --output {output_folder}/cost_report.md

# Quick estimate for planning
python tools/cu-cost-estimator/cu_cost_estimator.py estimate \
  --file-type document \
  --quantity 1000 \
  --model gpt-4.1
```

## Required Parameters

| Parameter | Scale Eval (1×N) | Stability Eval (N×1) |
|-----------|------------------|----------------------|
| `--analyzer-id` | Required | Required |
| `--input` | Folder with documents | Single document path |
| `--iterations` | 1 (default) | 10 (recommended) |
| `--output` | Required | Required |

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

| Metric | Description | Target |
|--------|-------------|--------|
| Fill Rate | % of documents where field is populated | >80% |
| Confidence (p50) | Median confidence score | >0.85 |
| Stability Rate | % of iterations with consistent value (N×1) | >95% |
| Latency (p95) | Processing time per document | <5s |
| Cost per doc | Token usage and API costs | Budget-dependent |

## Report Template

After exporting results, create a summary at `{output_folder}/REPORT.md`:

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

## Fill Rates (Coverage)

| Field | Fill Rate | Confidence (p50) | Notes |
|-------|-----------|------------------|-------|
| {field} | {rate}% | {conf} | {notes} |

## Issues Found

{list issues observed}

## Recommendations

{schema improvements — propose specific field description changes}
```

## Eval-Driven Improvement Loop

When evaluating, follow this pattern:
1. Read the eval manifest (if exists) or use defaults
2. Run the appropriate eval (scale or stability)
3. Export results and generate report
4. If metrics are below targets, produce an actionable diff plan:
   - Identify specific fields that need improvement
   - Propose concrete description changes
   - Quantify expected KPI deltas
   - Cite exemplar documents showing the issue
5. Optionally estimate costs for production deployment

## Output Files

```
{output_folder}/
├── metadata.json           # Run configuration and summary
├── results/
│   ├── {document}.json     # Result for each document
│   └── {document}_iter002.json  # (stability eval iterations)
├── results.csv             # Exported analysis table
├── results.summary.json    # Fill rates and statistics
├── cost_report.md          # Cost estimate (if generated)
└── REPORT.md               # Summary report
```

## See Also

- Full workflow guide: `.github/skills/eval-cu.skill.md`
- Video-specific eval: `.github/prompts/evaluate-analyzer-video.prompt.md`
- Classify-and-route eval: `.github/prompts/classify-and-route-schema.prompt.md`
- Create analyzer: `.github/prompts/generate-analyzer-schema.prompt.md`
- Write field descriptions: `.github/prompts/write_schema_fields.prompt.md`
