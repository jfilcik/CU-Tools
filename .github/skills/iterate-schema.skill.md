---
status: ✅ IMPLEMENTED
version: 1.0.0
last_updated: 2026-06-19
---

# Skill: Iterate Schema

Improve a Content Understanding analyzer schema based on test results and field diagnostics.

## Purpose

Schema iteration is the most common workflow after creating a v1 analyzer. This skill guides you through:
- Reviewing test results to identify underperforming fields
- Running diagnostics to surface low-confidence and low-fill-rate fields
- Making targeted field description improvements
- Re-testing and comparing versions to verify improvements

## When to Use

- After running an eval (see `eval-cu.skill.md`) and getting results below target
- When fill rate is < 80% for critical fields
- When confidence is < 0.85 for critical fields
- When iterating from v1 → v2 → v3 of a schema

## Prerequisites

- An existing analyzer schema (v1 or later)
- Test results from a previous run (JSON output directory)
- Sample documents for re-testing

## See Also

- `eval-cu.skill.md` — Run evals to generate the results this skill analyzes
- `generate-analyzer.skill.md` — Create the initial schema (v1)
- `generate-analyzer-classify-route.skill.md` — For classify-and-route pipelines
- Prompts: `generate-analyzer-schema.prompt.md`, `write_schema_fields.prompt.md`

---

## Workflow Steps

### Step 1: Run Diagnostics on Current Results

Export results and run field-level diagnostics:

```bash
python tools/cu-results-export/export.py \
  --input <test_results_dir> \
  --output <test_results_dir>/results.csv \
  --diagnose
```

This produces:
- `results.csv` — All extracted values in tabular form
- `results.diagnosis.json` — Per-field metrics (fill rate, confidence, suggestions)
- Stdout diagnostic table with severity flags

**What to look for:**
- 🔴 **Critical**: Fill rate < 50% or confidence < 0.5 — field needs major revision
- 🟡 **Warning**: Fill rate < 80% or confidence < 0.7 — field needs improvement
- 🔵 **Info**: High variance or outliers — field may need disambiguation
- 🟢 **OK**: Field is performing well

### Step 2: Review Problem Fields

For each flagged field, identify the root cause:

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Low fill rate, OK confidence | Field missing in some doc variations | Add alternative labels, broaden description |
| OK fill rate, low confidence | Ambiguous description | Add location hints, format examples, disambiguation |
| Low fill rate AND low confidence | Description doesn't match document content | Review layout output, rewrite description from scratch |
| High variance | Inconsistent across doc types | Add more specific location context |
| Value mismatch (wrong extractions) | Confusing with another field | Add "not to be confused with..." disambiguation |
| **No `valueString` returned, but `confidence ≥ 0.7`** | **Reading-order broken: LLM knows the field exists but can't resolve which token is the value** | **See "Diagnosing Missing Values with High Confidence" below** |
| Field works with `enableLayout: false` but fails with `enableLayout: true` | Layout model failed to detect a table; values and labels are positionally separated in OCR reading order | Flatten nested arrays, anchor by "directly below the label" in description, match exact document labels |
| Only some summary/footer fields fail (e.g., totals row) | Summary footer rendered as free text, not `<table>` | Same as above — see "Diagnosing Missing Values with High Confidence" |

### Step 3: Review Layout Output

If a field has very low fill rate, verify the content exists in the document:

```bash
python tools/cu-analyzer-run/run.py \
  --layout \
  --input <sample_document> \
  --output <output_dir>
```

Check the `.layout.md` output to confirm:
- The target text exists in the OCR output
- The text labels match what your description references
- The document structure (tables, sections) is correctly identified

### Step 4: Improve Field Descriptions

Apply the two-stage pipeline rules (see `Agents.md` §4.5):

**DO reference:**
- Text content and labels: `"near 'Total:' label"`
- Document structure: `"in the header section"`, `"in the line items table"`
- Alternative labels: `"May be labeled as 'Amount', 'Total Due', or 'Balance'"`
- Format examples: `"Format: MM/DD/YYYY. Examples: '01/15/2024', '2024-01-15'"`

**DON'T reference:**
- Visual appearance: colors, fonts, bold, size
- Position without text context: "top left corner"

**Create a new schema version** (don't overwrite the previous one):

```
schemas/
├── my_analyzer_v1.json   ← keep for comparison
├── my_analyzer_v2.json   ← improved version
```

### Step 5: Re-Test with Comparison

Run the improved schema and compare against the previous version:

```bash
python tools/cu-analyzer-run/create_and_test.py \
  --schema schemas/my_analyzer_v2.json \
  --input <sample_documents> \
  --output <test_results>/v2 \
  --compare-with <test_results>/v1
```

This generates:
- New test results in `v2/`
- `comparison.md` — Field-by-field comparison with confidence deltas
- Indicators: ✅ improved, ⚠️ degraded, 🔄 value changed

### Step 6: Evaluate Improvement

Review the comparison report:

1. **Improved fields** (✅): Confirm the fix worked as expected
2. **Degraded fields** (⚠️): Check if the change inadvertently affected other fields
3. **Unchanged fields**: Verify they weren't affected by changes

**Decision criteria:**
- If critical fields improved and nothing degraded → **accept v2**
- If some fields improved but others degraded → **investigate regressions, create v3**
- If no improvement → **go back to Step 3, review layout more carefully**

### Step 7: Run Full Eval (Optional)

Once satisfied with field-level improvements, run a full eval:

```bash
python tools/cu-analyzer-run/create_and_test.py \
  --schema schemas/my_analyzer_v2.json \
  --input <full_corpus> \
  --output <test_results>/v2_full \
  --compare-with <test_results>/v1_full
```

Then export and diagnose the full results to confirm improvements hold at scale.

---

## Common Patterns

### Pattern: Iterating on a Single Problem Field

1. Run `--diagnose` to identify the worst field
2. Check layout output for that document
3. Rewrite just that field's description
4. Run `create_and_test.py` with `--compare-with` to verify
5. Repeat until field meets targets

### Pattern: Improving Fill Rate Across Documents

1. Run scale eval (1×N) with diverse documents
2. Export with `--diagnose`
3. Group documents by which fields are missing
4. For each group, check if the field label varies
5. Add alternative labels to cover all variations
6. Re-test on the full corpus

### Pattern: Reducing Confidence Variance

1. Run stability eval (N×1) on a representative document
2. Export with `--diagnose`
3. For high-variance fields, add more specific anchoring:
   - Section headings: "in the 'Payment Details' section"
   - Proximity to other fields: "below the invoice number"
   - Format constraints: "exactly 10 digits"
4. Re-test stability to verify variance decreased

### Pattern: Diagnosing Missing Values with High Confidence (Reading-Order Issues)

**Signature**: Some fields extract reliably; others consistently return no `valueString` despite `confidence ≥ 0.7`. Re-running 10× yields the same misses — this is NOT stochastic LLM variance.

**Likely cause**: The layout model failed to detect a region (commonly summary footers, multi-row headers, or sparse grids) as a `<table>`. Labels and values are emitted as free text, and OCR reading order separates them by many tokens. The LLM sees the label, knows a value should exist (hence the confidence), but cannot resolve which token is the value.

**Real-world example (APL Logistics packing list)**:
- `enableLayout: true` (default): `GrossWeight`, `CartonsQty`, `PiecesQty` consistently missing across 10 runs
- `enableLayout: false`: Same fields extract correctly every time (prebuilt-document key-value pair detection uses spatial proximity)
- Document Intelligence markdown output identical in both environments → not a service-side issue
- Initial diagnosis: "DEV vs PROD discrepancy" — actually a schema/layout interaction

**Diagnostic steps**:

1. **Inspect the layout output for the failing region**:
   ```bash
   python tools/cu-analyzer-run/run.py --layout --input <doc.pdf> --output diag_layout/
   ```
   Open `diag_layout/<doc>.layout.md`. If the failing fields' labels and values appear as plain text (no `<table>` wrapping) and labels are visually above values, reading order is likely broken.

2. **Compare with `--read` (no layout)**:
   ```bash
   python tools/cu-analyzer-run/run.py --read --input <doc.pdf> --output diag_read/
   ```
   Note the token order. If labels appear far before values in the read stream, the same will be true in the layout token stream that the LLM consumes.

3. **Verify with a flattened test schema**: Create a minimal flat schema (no nested arrays) targeting only the failing fields with explicit "directly below the label" descriptions. If the flat schema works, the original nested schema's complexity was a contributing factor.

**Mitigations** (in order of preference):

1. **Flatten** — move summary/total fields out of nested `Goods[]` / `LineItems[]` arrays to top-level. Document-level totals don't belong in line-item arrays.
2. **Anchor by position relative to the label** — `"The numeric value appearing directly below the 'Gross Kgs' label"`.
3. **Match exact document labels** — if the document says "# of Cartons", don't write `"labeled 'Total Cartons'"`. Read the actual label from `.layout.md`.
4. **Fix examples** — examples that look nothing like real values bias the LLM. If the real value is `180.82`, don't use `"2459044"` as an example.
5. **Workaround**: `enableLayout: false` in analyzer config. Trades layout-table awareness for `prebuilt-document` key-value detection. Use when document-level rewrite isn't feasible.

**Reference**: `Agents.md` §4.5 (two-stage pipeline) and `generate-analyzer-schema.prompt.md` §7 (reading-order pitfalls).

---

## Tips

- **Always create a new schema version** — never overwrite. Version history is essential for debugging.
- **Fix one field at a time** when debugging — changing many fields simultaneously makes it hard to attribute improvements.
- **Use `--compare-with` religiously** — it's the fastest way to verify improvements.
- **Target confidence ≥ 0.85** for production fields. Below 0.7 needs attention.
- **Fill rate targets depend on the document corpus** — 100% isn't always achievable if fields are optional.
