---
name: iterate-schema
description: Diagnoses saved CU results and proposes targeted field-description improvements. Use after evaluation reveals missing, ambiguous, or inconsistent fields; follows the canonical analyzer iteration workflow.
---

# Skill: Iterate Schema — Field Diagnostics

Use [Iterate Analyzer Schema](iterate-analyzer-schema.skill.md) for experiment
planning, execution, promotion, bugs, and cost. This skill is its focused
offline diagnostic entry point, not another execution workflow.

## 1. Diagnose existing evidence

Select a new numbered experiment under
[the workspace contract](../../docs/iteration-workspaces.md). Read the
preserved baseline; put new derivatives in the candidate, not the baseline:

```powershell
python tools\cu-results-export\export.py `
  --input "{baseline_folder}\outputs\raw" `
  --output "{iteration_folder}\outputs\evaluation\baseline.csv" --diagnose
```

The exporter supports native recursive `.result.json` and legacy saved
results, excluding CLI status reports. Inspect its actual generated
diagnostics; absent confidence is unknown, not low confidence. Fill/confidence
can prioritize review but cannot establish a defect, correctness, or STP.

## 2. Investigate expected versus actual

| Observation | Hypothesis to test |
|---|---|
| Missing field | Source is absent, label varies, or extraction missed it |
| Wrong populated field | Confusable labels, wrong party/section, or row leakage |
| Changing value/count across trials | Ambiguity, repeated-entity loss, or normalization |
| Missing value with reported confidence | Source/reading-order/schema interaction; not a proven cause |
| Summary totals missing within arrays | Document totals may have been modeled as row properties |

For each issue, cite raw source and reviewed expectation, track the local
defect, and label cause unknown/suspected until isolated. Do not explain model
internals from confidence scores.

## 3. Inspect text and structure

Reuse saved layout where possible. If a new billable layout call is approved:

```powershell
cu analyze "{document_path}" --analyzer prebuilt-layout --json `
  --api-version 2025-11-01 `
  --output-dir "{iteration_folder}\outputs\raw\layout" `
  --report-file "{iteration_folder}\outputs\raw\layout-status.json" `
  --yes --on-existing error
```

Inspect native results for the exact labels, value text, tables, and reading
order. Missing table structure or separated labels/values supports a
reading-order hypothesis, not a confirmed root cause. Check original content
and controlled comparisons before attributing the defect.

## 4. Make one coherent schema change

- Bind to semantic labels and their real variants, with section/row/column
  boundaries; a label-relative location can clarify sparse summaries.
- Separate document totals from line-item arrays; preserve every required row.
- Disambiguate party, date, or amount meanings; do not substitute a different
  field just to raise fill rate.
- Keep examples generic and format-representative, not copied truth answers.
- Specify justified normalization and missing-source behavior.
- Validate any configuration change against the selected API, then test it
  as a new hypothesis. Do not infer an undocumented processing mechanism.

See [field descriptions](../prompts/write_schema_fields.prompt.md) and
[Agents.md](../../Agents.md) for schema rules.

## 5. Verify and decide

Validate offline, create a new versioned analyzer with official `cu`, then use
the [iteration workflow](iterate-analyzer-schema.skill.md) for approved native
batches or five/ten parallel repeats. Compare reviewed correctness and
protected behavior on the full frozen corpus, not confidence deltas alone.

Use a versioned offline evaluator; there is no implicit service-side comparison.
Record missing/failed outputs, denominators, coverage, false accepts, review,
holdout limits, and unknown usage/cost honestly. Finish manifest/report and
root navigation; link actual product bugs separately from local defects.
