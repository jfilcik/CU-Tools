# Tutorial 02: Invoice Extraction — Agent-Based Workflow

Build a document field extraction analyzer using the AI-assisted workflow. This tutorial walks through the full cycle: layout analysis → schema design → validation → testing → evaluation.

## What You'll Learn

- How Content Understanding's two-stage pipeline works (OCR → AI field extraction)
- The agent-based `generate-analyzer` workflow
- Schema design best practices for documents
- How to run scale and stability evals
- Iterating on schema quality with evidence

## Prerequisites

- Azure AI Foundry with Content Understanding enabled
- Python 3.9+ with dependencies installed (`pip install -r ../../requirements.txt`)
- `.env` configured at repo root (copy from `.env.sample`)
- GitHub Copilot (recommended, but manual steps are provided)

## Sample Documents

This tutorial includes two public sample documents in `samples/`:

| File | Type | What It Contains |
|------|------|------------------|
| `invoice.pdf` | PDF | Standard commercial invoice with line items |
| `receipt.png` | Image | Point-of-sale receipt |

---

## Workflow Overview

```
samples/          →  layout_results/   →  schemas/          →  test_results/    →  reports/
(invoice.pdf)        (extracted text)      (invoice_v1.json)    (JSON results)      (CSV export)
```

---

## Step 1: Extract Document Layout

Layout extraction (Stage 1) runs OCR and structure analysis on your documents. This shows you what the AI model will "see" — text content, tables, and layout.

**With Copilot:**
```
"Run layout extraction on Examples/02-Invoice-Extraction/samples/"
```

**Manually:**
```bash
python tools/cu-analyzer-run/run.py \
  --layout \
  --input Examples/02-Invoice-Extraction/samples/ \
  --output Examples/02-Invoice-Extraction/layout_results/
```

**What to look for** in the `.layout.md` output:
- Field labels ("Invoice Number:", "Date:", "Total:")
- Table structures (line items with columns)
- Section headers and their relative positions
- Alternative label variations across documents

---

## Step 2: Design the Schema

A schema tells Content Understanding what fields to extract, where to find them, and what format to expect. The key insight: **describe text and structure, not visual appearance** (the AI sees OCR text, not the original image).

**With Copilot:**
```
"Using generate-analyzer-schema, create an invoice analyzer 
 that extracts vendor, dates, line items, and totals. 
 Use the layout results in Examples/02-Invoice-Extraction/layout_results/"
```

**Pre-built schema:** A ready-to-use schema is included at `schemas/invoice_v1.json`. Review it to see best practices:

- **Detailed descriptions** with location hints and alternative labels
- **Format examples** ("Format is usually MM/DD/YYYY")
- **Disambiguation** ("Not to be confused with subtotal which excludes tax")
- **Array fields** for repeating structures (line items)

### Schema Design Tips

✅ Good field description:
```json
"InvoiceDate": {
  "description": "The date when the invoice was issued. Found near the invoice number 
   at the top right. May be labeled 'Invoice Date', 'Date', or 'Issue Date'. 
   Format: MM/DD/YYYY or YYYY-MM-DD."
}
```

❌ Bad field description:
```json
"InvoiceDate": {
  "description": "Get the date"
}
```

---

## Step 3: Validate the Schema

Validation catches errors before you spend time creating an analyzer.

```bash
python tools/cu-analyzer-validate/cu_analyzer_validator.py \
  Examples/02-Invoice-Extraction/schemas/invoice_v1.json
```

Fix any errors before proceeding. Common issues:
- Missing `method` on fields (must be `extract`, `generate`, or `classify`)
- Vague descriptions (validator flags descriptions under 20 characters)
- Invalid field types

---

## Step 4: Create Analyzer and Test

This all-in-one command validates the schema, creates an analyzer in Azure, runs it against your samples, and saves results.

**With Copilot:**
```
"Create and test the invoice analyzer using the schema in 
 Examples/02-Invoice-Extraction/schemas/invoice_v1.json 
 with samples from Examples/02-Invoice-Extraction/samples/"
```

**Manually:**
```bash
python tools/cu-analyzer-run/create_and_test.py \
  --schema Examples/02-Invoice-Extraction/schemas/invoice_v1.json \
  --input Examples/02-Invoice-Extraction/samples/ \
  --output Examples/02-Invoice-Extraction/test_results/v1/
```

This creates JSON result files in `test_results/v1/` — one per document.

---

## Step 5: Export and Evaluate Results

Convert JSON results to CSV for easy review:

```bash
python tools/cu-results-export/export.py \
  --input Examples/02-Invoice-Extraction/test_results/v1/ \
  --output Examples/02-Invoice-Extraction/test_results/v1/results.csv
```

**What to evaluate:**

| Metric | Target | What It Means |
|--------|--------|---------------|
| Fill Rate | >80% | Percentage of documents where a field was extracted |
| Confidence | >0.85 | Model's certainty about extracted values |
| Accuracy | Manual check | Do extracted values match the document? |

---

## Step 6: Run Evals

### Scale Eval (1×N) — Coverage

Run many different documents to measure extraction quality across variations:

```bash
python tools/cu-analyzer-run/run.py \
  --analyzer-id {your-analyzer-id} \
  --input Examples/02-Invoice-Extraction/samples/ \
  --output Examples/02-Invoice-Extraction/test_results/scale/
```

### Stability Eval (N×1) — Consistency

Run the same document multiple times to measure extraction consistency:

```bash
python tools/cu-analyzer-run/run.py \
  --analyzer-id {your-analyzer-id} \
  --input Examples/02-Invoice-Extraction/samples/invoice.pdf \
  --iterations 10 \
  --output Examples/02-Invoice-Extraction/test_results/stability/
```

---

## Step 7: Iterate

If quality is low on certain fields:

1. **Tighten descriptions** — Add more specific location hints and alternative labels
2. **Add format examples** — "Format: MM/DD/YYYY. Examples: '01/15/2024'"
3. **Disambiguate** — "Not the shipping date; this is the date the invoice was created"
4. **Save as v2** — Always version your schemas (`invoice_v2.json`)
5. **Re-test and compare** — Run the same samples and compare CSV output

```bash
# Test v2
python tools/cu-analyzer-run/create_and_test.py \
  --schema Examples/02-Invoice-Extraction/schemas/invoice_v2.json \
  --input Examples/02-Invoice-Extraction/samples/ \
  --output Examples/02-Invoice-Extraction/test_results/v2/
```

---

## Folder Structure

```
02-Invoice-Extraction/
├── README.md              # This tutorial
├── samples/               # Source documents
│   ├── invoice.pdf        # Sample commercial invoice
│   └── receipt.png        # Sample receipt
├── schemas/               # Analyzer schemas (versioned)
│   └── invoice_v1.json    # Initial schema with best practices
├── layout_results/        # Layout extraction output (generated)
├── test_results/          # Analysis results by run (generated)
└── reports/               # Summary reports and exports (generated)
```

## Next Steps

- **[Tutorial 03: Video Analysis](../03-Video-Analysis/)** — Apply the same workflow to video content
- **[Eval Skill](../../.github/skills/eval-cu.skill.md)** — Deep dive into evaluation methodology
- **[Schema Iteration Skill](../../.github/skills/iterate-schema.skill.md)** — Systematic schema improvement

## Related Resources

- [Agents.md](../../Agents.md) — Technical reference (Section 4.5: Two-Stage Pipeline, Section 4.6: Schema Design)
- [generate-analyzer skill](../../.github/skills/generate-analyzer.skill.md) — Full workflow reference
- [Analyzer templates](../../analyzer_templates/) — More example configurations
