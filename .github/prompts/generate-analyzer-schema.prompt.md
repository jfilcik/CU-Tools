# Prompt: Generate Analyzer Schema

Generate a valid, reusable CU schema from reviewed extraction requirements.
Use [Agents.md](../../Agents.md) for authoritative API/schema behavior and
[Generate Analyzer](../skills/generate-analyzer.skill.md) for execution.

## Context to supply

- Case and numbered iteration; private for customer data.
- Hypothesis, baseline, expected/actual defects, and verified tracking bugs.
- Document type/language, selected API/model, and available base analyzer.
- Fields, required/optional behavior, source evidence, and reviewed acceptance
  rules. Keep truth values separate from schema descriptions.

Follow [iteration workspaces](../../docs/iteration-workspaces.md). Freeze
candidate schemas under `{iteration_folder}\inputs\schemas\`; retain baseline
snapshots, input hashes, evaluator/truth versions, and development/holdout scope.
A changed schema/configuration or evaluation rule requires a new number.

## Design rules

1. **Text and structure:** document extraction operates on extracted
   text/structure. Reference labels, headings, sections, rows, and columns;
   do not depend on color, bold, font size, or position alone.
2. **Appropriate methods:** explicitly choose `extract` for source values,
   `generate` for inference/summaries, or `classify` for predefined choices,
   subject to the selected modality/API.
3. **Structured data:** use objects and arrays of objects, not strings
   requesting embedded JSON. Preserve all repeated entities.
4. **Scope:** separate document totals from line-item values and distinguish
   parties, issue/due dates, and subtotal/total amounts.
5. **Descriptions:** include semantic label variants, section context, format,
   missing-source behavior, and targeted disambiguation. Match the document
   language. Keep positive definitions primary; explicit exclusions can
   prevent a known confusion.
6. **No hard-coded truth:** examples illustrate formats, not customer answers.
   Do not tune to filenames, literal sample values, page numbers, coordinates,
   or a single customer's layout.
7. **Deterministic work:** compute arithmetic/normalization outside extraction
   where appropriate. An extracted line amount is the stated amount, not an
   instruction to multiply two fields.
8. **Grounding:** request source/confidence details where supported, then
   review the actual evidence. Confidence is not a correctness score.

Use descriptive PascalCase fields with appropriate `string`, `number`,
`boolean`, `array`, or `object` types. Confirm allowed names/options with the
offline validators. Do not invent top-level properties, supported models, or
API capabilities. Server analyzer identity is supplied to `cu analyzer create
--name`; dependency aliases belong in the offline planner, not an assumed
top-level identity field.

## Starter document schema

This is an illustrative starting point, not measured accuracy evidence:

```json
{
  "description": "Extract invoice identifiers, line items, and stated total amounts",
  "baseAnalyzerId": "prebuilt-document",
  "config": {
    "returnDetails": true,
    "estimateFieldSourceAndConfidence": true
  },
  "models": { "completion": "gpt-4.1" },
  "fieldSchema": {
    "fields": {
      "InvoiceNumber": {
        "type": "string",
        "method": "extract",
        "description": "The invoice identifier near the invoice heading, labeled Invoice Number, Invoice No., or Invoice #. Preserve its source formatting; distinguish it from a purchase-order identifier.",
        "estimateSourceAndConfidence": true
      },
      "LineItems": {
        "type": "array",
        "method": "extract",
        "description": "All billed product or service rows in the item table, including continuation rows. Keep document-level subtotal and total rows separate.",
        "items": {
          "type": "object",
          "description": "One billed product or service row with its stated quantity and amount.",
          "properties": {
            "ItemDescription": {
              "type": "string",
              "method": "extract",
              "description": "The product or service text in the Description or Item column for this row."
            },
            "Quantity": {
              "type": "number",
              "method": "extract",
              "description": "The quantity stated in the Quantity or Qty column for this row; leave absent when no quantity is given."
            },
            "Amount": {
              "type": "number",
              "method": "extract",
              "description": "The amount explicitly stated in the Amount or Line Total column for this row; do not calculate a replacement."
            }
          }
        }
      },
      "TotalAmount": {
        "type": "number",
        "method": "extract",
        "description": "The final invoice amount stated beside Total or Amount Due in the summary section, including applicable tax. Distinguish it from Subtotal and individual line amounts.",
        "estimateSourceAndConfidence": true
      }
    }
  }
}
```

For repeated packet types use [classify-and-route](classify-and-route-schema.prompt.md).
For video timestamps use [video generation](../skills/generate-analyzer-video.skill.md);
do not transfer document-only assumptions to video. Preview/Agentic schemas
must follow [the explicit preview contract](../skills/cu-preview-api.skill.md).

## Reading-order investigation

Sparse summaries and multi-row headers may be returned without useful table
structure, separating labels from values. Missing values—even with reported
confidence—do not establish that cause.

- Inspect saved native layout content and original source.
- Confirm exact labels instead of paraphrasing them.
- Describe label-relative location when helpful, such as the value below
  `Gross Kgs` in a summary section.
- Move document totals out of row arrays where their meaning demands it.
- Test the smallest coherent hypothesis across the controlled corpus.

Use [field diagnostics](../skills/iterate-schema.skill.md) for the approved
native layout command and isolation workflow. Do not claim undocumented
processing behavior or recommend a configuration workaround without validating
the API and measuring a controlled comparison.

## Validate offline

```powershell
cu analyzer validate "{iteration_folder}\inputs\schemas\invoice.json" `
  --api-version 2025-11-01 --spec
python tools\cu-analyzer-validate\cu_analyzer_validator.py `
  "{iteration_folder}\inputs\schemas\invoice.json" --api-version 2025-11-01
```

Fix structural/spec errors and review local quality warnings. These checks
make no service calls and do not prove resource/model availability or extraction
quality. Use the matching explicit preview version when relevant.

## Deliverables and next step

Return valid complete JSON plus a concise explanation of field scope, source
anchors, missing-value behavior, deliberate changes, and unresolved ambiguity.
Snapshot/hash the exact submitted schema and link it from the iteration.

Creation and analysis are separate official `cu` operations in
[Generate Analyzer](../skills/generate-analyzer.skill.md). Repeated comparisons
use [Iterate Analyzer Schema](../skills/iterate-analyzer-schema.skill.md).
Offline export/evaluation stays local.

After authorized testing, link raw outputs, reviewed correctness, protected
regressions, denominators, cost status/basis, and the decision in manifest/report.
Missing usage/cost is unknown/null; field fill and confidence alone do not
prove correctness or STP.

See [Write Schema Fields](write_schema_fields.prompt.md) for targeted edits.
