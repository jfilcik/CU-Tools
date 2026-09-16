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

## Workspace binding

Follow [the v1 workspace guide](../../docs/iteration-workspaces.md).
`{baseline_folder}` is a preserved prior iteration; `{iteration_folder}` is
the selected next experiment. Keep customer work private. Record a hypothesis,
baseline ID, defect IDs, exact changes, input/schema hashes, and versioned
truth/evaluator before running. Store new schemas in `inputs/schemas/`, raw
output in `outputs/raw/`, derived diagnostics in `outputs/evaluation/`, and
the evidence/cost decision in `report.md`, all beneath `{iteration_folder}`.
Do not export new files into a completed baseline. Changed hypotheses,
configuration, datasets, or metrics require a new number; N stability repeats
are trials within one numbered experiment.
Link verified product bugs in the root and relevant iteration `bugs` arrays,
separately from local defects; follow [tracking bugs](../../docs/iteration-workspaces.md#tracking-bugs).

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
  --input "{baseline_folder}/outputs/raw/analysis" \
  --output "{iteration_folder}/outputs/evaluation/baseline.csv" \
  --diagnose
```

This produces:
- `baseline.csv` — All extracted values in tabular form
- `baseline.diagnosis.json` — Per-field metrics (fill rate, confidence, suggestions)
- Stdout diagnostic table with severity flags

**What to look for:**
- 🔴 **Critical**: Fill rate < 50% or confidence < 0.5 — field needs major revision
- 🟡 **Warning**: Fill rate < 80% or confidence < 0.7 — field needs improvement
- 🔵 **Info**: High variance or outliers — field may need disambiguation
- 🟢 **OK**: Field is performing well

### Step 2: Review Problem Fields

For each flagged field, investigate a possible cause; these diagnostic
patterns are hypotheses, not proof. Record cause status and confirm it only
with linked isolation/reproduction evidence:

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

```powershell
cu analyze "<sample_document>" --analyzer prebuilt-layout --out "{iteration_folder}\outputs\raw\layout"
```

Use official `cu` for this routine call. If diagnostics depend on the legacy
`.layout.md` format, retain `run.py --layout` and its bundle at the same
iteration-local output path. Check the resulting markdown to confirm:
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
iterations/
├── 001/inputs/schemas/my_analyzer_v1.json   ← preserved baseline
└── 002/inputs/schemas/my_analyzer_v2.json   ← candidate snapshot
```

### Step 5: Re-Test with Comparison

Run the improved schema and compare against the previous version:

```bash
python tools/cu-analyzer-run/create_and_test.py \
  --schema "{iteration_folder}/inputs/schemas/my_analyzer_v2.json" \
  --input "<sample_documents>" \
  --output "{iteration_folder}/outputs/raw/analysis" \
  --compare-with "{baseline_folder}/outputs/raw/analysis"
```

This generates:
- New test results in the selected iteration's `outputs/raw/analysis/`
- `comparison.md` — Field-by-field comparison with confidence deltas
- Indicators: ✅ improved, ⚠️ degraded, 🔄 value changed

Keep the integrated runner and its output bundle (it uses the legacy REST
backend, not official CLI/SDK). Link generated comparison files; put any
additional derived evaluation under `outputs/evaluation/`. Obtain cost
approval before paid repeat/scale runs.

### Step 6: Evaluate Improvement

Review the comparison report:

1. **Improved fields** (✅): Confirm the fix worked as expected
2. **Degraded fields** (⚠️): Check if the change inadvertently affected other fields
3. **Unchanged fields**: Verify they weren't affected by changes

Verify against reviewed truth, not confidence deltas alone. Report denominators,
raw sources, failures/retries, holdout scope, false accepts, review rate, and
iteration cost/status/basis in the manifest/report. Missing cost is null, not
zero; measured token usage times prices is still estimated cost.

**Decision criteria:**
- If critical fields improved and nothing degraded → **accept v2**
- If some fields improved but others degraded → **investigate regressions, create v3**
- If no improvement → **go back to Step 3, review layout more carefully**

### Step 7: Run Full Eval (Optional)

Once satisfied with field-level improvements, run a full eval:

Expanding the corpus changes scope: create the next numbered experiment,
bind `{iteration_folder}` to it, and select a baseline with matching scope.

```bash
python tools/cu-analyzer-run/create_and_test.py \
  --schema "{iteration_folder}/inputs/schemas/my_analyzer_v2.json" \
  --input "<full_corpus>" \
  --output "{iteration_folder}/outputs/raw/analysis" \
  --compare-with "{baseline_folder}/outputs/raw/analysis"
```

Then export and diagnose the full results to confirm improvements hold at scale.
Complete `report.md`, refresh the root iteration index, and freeze finished
evidence. Do not claim STP from global fill/confidence; use the workspace guide.

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
   python tools/cu-analyzer-run/run.py --layout --input "<doc.pdf>" --output "{iteration_folder}/outputs/raw/diag_layout/"
   ```
   Open the iteration-local `outputs/raw/diag_layout/<doc>.layout.md`. If the
   failing labels and values lack table structure and are separated in text
   order, investigate reading order as a possible cause.

2. **Compare with `--read` (no layout)**:
   ```bash
   python tools/cu-analyzer-run/run.py --read --input "<doc.pdf>" --output "{iteration_folder}/outputs/raw/diag_read/"
   ```
   Note the token order. If labels appear far before values in the read stream, the same will be true in the layout token stream that the LLM consumes.

3. **Test a flattened schema hypothesis in a new numbered experiment**:
   snapshot a minimal flat schema targeting the failing fields with
   label-relative descriptions; compare repeated correctness evidence before
   concluding that nesting contributed.

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
