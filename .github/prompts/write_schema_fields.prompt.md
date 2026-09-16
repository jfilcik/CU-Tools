# Prompt: Write Schema Fields

Author or refine CU field definitions from source evidence, not from desired
sample answers. [Agents.md](../../Agents.md) owns technical rules;
[Generate Analyzer Schema](generate-analyzer-schema.prompt.md) supplies the
complete-schema context.

## Context

- Selected `case\iterations\NNN`, hypothesis/baseline, and schema snapshot.
- Fields to add/change and reviewed expected versus actual behavior.
- Local defect IDs and verified tracking bugs.
- Source text/layout evidence, document language, and selected API/modality.

Follow [iteration workspaces](../../docs/iteration-workspaces.md). Keep customer
data private, freeze/hash inputs and schema, and version truth/evaluator rules.
Write candidate definitions into the new iteration's `inputs\schemas\`; never
overwrite a finished baseline.

## Authoring checklist

1. Use descriptive PascalCase field names and correct types: strings,
   numbers, booleans, objects, or arrays of objects for repeated records.
2. Explicitly choose `extract`, `generate`, or `classify` for the field's
   purpose, within the selected modality/API contract.
3. Define the semantic value and its text anchors: exact label variants,
   section, party, row, and column. Avoid visual styling or position alone.
4. Specify source formatting or justified normalization, plus absent/ambiguous
   source behavior. Do not use another field as a fallback merely to fill it.
5. Describe the intended meaning positively, adding focused exclusions for
   confusable meanings such as due date versus issue date.
6. Match the source language. Use representative format examples that are
   not copied customer truth or literal sample answers.
7. Keep document totals separate from repeated line items; compute
   deterministic arithmetic downstream instead of asking extraction to guess.
8. Request source/confidence when supported. Missing confidence is unknown,
   and reported confidence does not establish correctness.

### Sparse summary fields

Inspect native saved layout content before choosing labels. If labels and
values are separated in text order, use a label-relative description such as
“the numeric value directly below `Gross Kgs` in the summary section.”
Reading-order failure is a hypothesis to isolate, not something proved by a
missing value with high confidence. See
[field diagnostics](../skills/iterate-schema.skill.md).

### Example definition

```json
{
  "InvoiceDate": {
    "type": "string",
    "method": "extract",
    "description": "The invoice issue date beside Invoice Date, Issued, or Date in the invoice header near the invoice identifier. Preserve the date format shown, such as MM/DD/YYYY or YYYY-MM-DD. Distinguish it from a payment due date; leave absent if no issue date is stated.",
    "estimateSourceAndConfidence": true
  }
}
```

Generic examples may appear in descriptions; any separate schema property
must be supported by the selected API. Do not add arbitrary validation or
training-example properties to a service schema.

## Output and verification

Return complete JSON field definitions and a short rationale: evidence,
expected benefit, ambiguity, and unchanged/protected behavior. Link the final
schema snapshot in the iteration manifest and run both official offline
validation and the local quality checks from
[Generate Analyzer Schema](generate-analyzer-schema.prompt.md).

A proposed description is not a measured improvement. Execute only through
official `cu`, using [the iteration workflow](../skills/iterate-analyzer-schema.skill.md)
for cost-approved tests and repeated comparisons. Preserve raw results, put
derived diagnostics under `outputs\evaluation\`, and complete report/manifest
with reviewed correctness, denominators, failures, cost/basis, and limitations.
Missing measurements stay unknown; fill/confidence alone cannot establish STP.
