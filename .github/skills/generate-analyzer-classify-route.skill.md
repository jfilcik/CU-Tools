---
status: ✅ IMPLEMENTED
version: 1.0.0
last_updated: 2026-04-07
---

# Skill: Generate Analyzer – Classify-and-Route (Advanced Pattern)

Guided workflow to create a multi-analyzer pipeline that **classifies** document types and **routes** each to a specialized field-extraction analyzer.

> **Standard pattern first**: If you are working with a single document type, use
> `generate-analyzer.skill.md` instead. This skill is for document packets that contain
> **multiple distinct document types** in the same PDF or batch.

## Purpose

Help users design and deploy a classify-and-route pipeline that:
1. Identifies the document types present in your packet
2. Creates inner (field-extraction) analyzers for each type
3. Creates an outer (classifier) analyzer that routes pages to the right inner analyzer
4. Tests the full pipeline end-to-end

## When to Use

- A single PDF or batch contains **multiple document types** (e.g., vehicle titles + registrations)
- Different document types require **different extraction fields**
- You need to **classify first**, then extract fields per-type
- You are processing a production corpus where documents are mixed in unknown order

## When NOT to Use

- All documents share the same structure and fields → use `generate-analyzer.skill.md`
- You only need to classify (no field extraction) → consider a simpler schema with a single analyzer
- You're just getting started with CU → learn the standard pattern first

## How It Works (Two-Stage + Routing)

CU's two-stage pipeline applies here too:

```
Stage 1: OCR/Layout runs on the entire document packet
         ↓
Stage 2 (Classifier): GPT-4.1 segments the packet and classifies each segment
         ↓
Stage 2 (Inner Analyzers): GPT-4.1 extracts fields from each classified segment
```

**Key constraint**: Classification descriptions must use **text anchors** (headings, labels,
keywords found in OCR output), NOT visual appearance (colors, fonts, layout positions).

## Reference Example

`Issues/Carvana/` — Vehicle title + registration packets:
- Inner: `vehicle_title_extractor` (title-specific fields)  
- Inner: `vehicle_registration_extractor` (registration-specific fields)
- Outer: `vehicle_docs_classifier` (classifies pages and routes them)

---

## Workflow Steps

### Step 1: Identify Document Types in the Packet

**User Action**: Provide sample document packets and describe the document types present.

**Questions to answer**:
- How many distinct document types are in your packets?
- Do all packets contain all types, or are types optional?
- Can a single packet have multiple pages of the same type?

**Layout analysis across all types**:
```bash
python tools/cu-analyzer-run/run.py \
  --layout \
  --input {sample_folder} \
  --output {project_folder}/layout_results
```

Review the `.layout.md` files to identify type-distinguishing text patterns:
- What headings or titles uniquely identify each document type?
- What labels or keywords appear only in one type?
- Are there structured fields that appear in only one type?

**Output**: A list of document types with distinguishing text characteristics.

---

### Step 2: Create Inner Analyzer Schemas (One Per Document Type)

For each document type, create a standard field-extraction schema following `generate-analyzer.skill.md`.

**Inner schema structure**:
```json
{
  "description": "Extract fields from [document type]",
  "baseAnalyzerId": "prebuilt-document",
  "scenario": "document",
  "config": {
    "returnDetails": true,
    "estimateFieldSourceAndConfidence": true
  },
  "models": {
    "completion": "gpt-4.1"
  },
  "fieldSchema": {
    "fields": {
      "FieldName": {
        "type": "string",
        "method": "extract",
        "description": "Clear text-based description of the field",
        "estimateSourceAndConfidence": true
      }
    }
  }
}
```

**Naming convention**: `{project_folder}/schemas/{type}_extractor_v1.json`

**Example for two types**:
```
schemas/
├── invoice_extractor_v1.json      # Invoice fields
└── receipt_extractor_v1.json      # Receipt fields
```

---

### Step 3: Test Inner Analyzers Individually

**Critical**: Test each inner analyzer on its own document type *before* building the classifier.

```bash
# Test invoice extractor
python tools/cu-analyzer-run/create_and_test.py \
  --schema {project_folder}/schemas/invoice_extractor_v1.json \
  --input {project_folder}/samples/invoices/ \
  --output {project_folder}/test_results/invoice_extractor_v1 \
  --keep-analyzer

# Test receipt extractor
python tools/cu-analyzer-run/create_and_test.py \
  --schema {project_folder}/schemas/receipt_extractor_v1.json \
  --input {project_folder}/samples/receipts/ \
  --output {project_folder}/test_results/receipt_extractor_v1 \
  --keep-analyzer
```

> Use `--keep-analyzer` to retain inner analyzers — the classifier will reference them by ID.

**Note the analyzer IDs** from the test output or `metadata.json`. You'll need them in Step 5.

**Success criteria before proceeding**:
- Fill rate >80% for key fields in each inner analyzer
- No obvious mis-extractions on the sample set

---

### Step 4: Export Individual Results

```bash
python tools/cu-results-export/export.py \
  --input {project_folder}/test_results/invoice_extractor_v1 \
  --output {project_folder}/test_results/invoice_extractor_v1/results.csv

python tools/cu-results-export/export.py \
  --input {project_folder}/test_results/receipt_extractor_v1 \
  --output {project_folder}/test_results/receipt_extractor_v1/results.csv
```

Review the CSVs to confirm field extraction quality before proceeding.

---

### Step 5: Create the Classifier (Outer Analyzer) Schema

The outer analyzer only classifies — it has no `fieldSchema`. It uses `config.contentCategories`
with descriptions that tell GPT-4.1 how to tell document types apart.

**Outer schema structure**:
```json
{
  "description": "Classify document types and route to specialized extractors",
  "baseAnalyzerId": "prebuilt-document",
  "config": {
    "enableSegment": true,
    "contentCategories": {
      "invoice": {
        "description": "Classify as 'invoice' when the document contains text like 'Invoice', 'Invoice Number', line items with unit prices, and a total amount due. Often has 'Bill To' and 'Ship To' sections.",
        "analyzerId": "invoice_extractor_XXXXXXXX"
      },
      "receipt": {
        "description": "Classify as 'receipt' when the document contains 'Receipt', transaction date, and payment confirmation text. May include 'Thank you for your purchase' or similar language.",
        "analyzerId": "receipt_extractor_XXXXXXXX"
      },
      "other": {
        "description": "Classify as 'other' when the document does not match invoice or receipt patterns. No field extraction will be performed."
      }
    },
    "omitContent": true
  },
  "models": {
    "completion": "gpt-4.1"
  }
}
```

**Rules for category descriptions**:
- ✅ Use text anchors: `'Invoice Number'`, `'Bill To'`, `'Receipt'`
- ✅ Describe distinguishing keywords and phrases from OCR output
- ✅ Include what's unique to this type vs other types
- ❌ No visual descriptions: no colors, fonts, layout positions

**Save as**: `{project_folder}/schemas/{project}_classifier_v1.json`

**Replace the `analyzerId` placeholders** with the actual IDs captured in Step 3.

---

### Step 6: Validate the Classifier Schema

```bash
python tools/cu-analyzer-validate/cu_analyzer_validator.py \
  {project_folder}/schemas/{project}_classifier_v1.json
```

The validator checks that `contentCategories` are properly formed and that `enableSegment` is set.

---

### Step 7: Create the Classifier and Test the Full Pipeline

```bash
python tools/cu-analyzer-run/create_and_test.py \
  --schema {project_folder}/schemas/{project}_classifier_v1.json \
  --input {project_folder}/samples/mixed_packets/ \
  --output {project_folder}/test_results/classifier_v1 \
  --keep-analyzer
```

Use **mixed-document packets** (PDFs or batches containing multiple document types) for this test.

---

### Step 8: Export and Analyze Full Pipeline Results

```bash
python tools/cu-results-export/export.py \
  --input {project_folder}/test_results/classifier_v1 \
  --output {project_folder}/test_results/classifier_v1/results.csv
```

The exported CSV will include a `category` column showing how each segment was classified.

**Review for**:
- **Classification accuracy**: Are segments classified into the correct category?
- **Extraction quality**: Are fields from inner analyzers populated correctly?
- **"other" rate**: High rate suggests unrecognized document types or poor category descriptions

---

### Step 9: Iterate

#### If classification is inaccurate:
- Revise the `description` in `contentCategories` for the confused categories
- Add more distinguishing text anchors
- Create `{project}_classifier_v2.json` with improved descriptions

#### If extraction quality is low for a specific type:
- Improve that inner analyzer schema (follow `generate-analyzer.skill.md` iteration)
- Note: changing an inner analyzer requires the classifier to still reference the same analyzer ID;
  if you create a new inner analyzer, update the classifier schema with the new ID

---

## Example Session

```
User: I have packets of vehicle documents. Each packet is a multi-page PDF that 
      contains a vehicle title and a vehicle registration. I need to extract 
      different fields from each.

Copilot: This is a great fit for the classify-and-route pattern. Here's the plan:

  1. Analyze layout of sample packets to identify distinguishing text
  2. Create inner analyzers: title_extractor and registration_extractor
  3. Test each inner analyzer on its own document type
  4. Create outer classifier referencing both inner analyzers
  5. Test the full pipeline on mixed packets

Step 1: Running layout analysis on your samples...
[Runs layout analysis]

From the layout results I can see:
- Vehicle titles contain: "CERTIFICATE OF TITLE", "Odometer Reading", "Vehicle Identification Number"
- Registrations contain: "REGISTRATION CARD", "Expires", "License Plate Number"

I'll use those as category descriptions. Creating inner analyzer schemas...
[Creates title_extractor_v1.json and registration_extractor_v1.json]

Step 3: Testing inner analyzers...
  title_extractor: 100% fill rate on 5 title samples ✓
  registration_extractor: 90% fill rate on 5 registration samples ✓

Inner analyzer IDs:
  title_extractor_20260407_abc123
  registration_extractor_20260407_def456

Step 5: Creating classifier schema...
[Creates vehicle_docs_classifier_v1.json with category descriptions and analyzer IDs]

Step 7: Testing full pipeline on mixed packets...
  Classified: 10/10 segments correctly ✓
  Extractions: title fields 100%, registration fields 90% ✓

Results exported to test_results/classifier_v1/results.csv
```

---

## Output Artifacts

```
Issues/{project}/
├── samples/
│   ├── titles/                         # Title-only samples (for inner analyzer testing)
│   ├── registrations/                  # Registration-only samples
│   └── mixed_packets/                  # Full packets (for classifier testing)
├── layout_results/
├── schemas/
│   ├── title_extractor_v1.json         # Inner analyzer: titles
│   ├── registration_extractor_v1.json  # Inner analyzer: registrations
│   └── vehicle_docs_classifier_v1.json # Outer analyzer: classifier
├── test_results/
│   ├── title_extractor_v1/             # Individual type test results
│   ├── registration_extractor_v1/      # Individual type test results
│   └── classifier_v1/                  # Full pipeline test results
│       ├── metadata.json
│       ├── packet1.json
│       └── results.csv
└── reports/
```

---

## Deployment Sequence (REQUIRED ORDER)

> Inner analyzers MUST exist before the classifier is created.
> The classifier schema directly references inner analyzer IDs.

```
1. Create inner analyzers (title_extractor, registration_extractor)
2. Note their analyzer IDs
3. Update classifier schema with real IDs
4. Create classifier analyzer
5. Submit full packets to classifier
```

---

## Related Skill

- `generate-analyzer.skill.md` — Standard single-type analyzer (start here if new to CU)

## Related Prompts

- `classify-and-route-schema.prompt.md` — Schema design rules and nesting depth limits
- `analyze-document-structure.prompt.md` — Understand document layout
- `generate-analyzer-schema.prompt.md` — Generate field schemas for inner analyzers
- `write_schema_fields.prompt.md` — Write individual field descriptions
- `evaluate-analyzer.prompt.md` — Core eval workflow for testing pipeline results

## Related Tools

- `cu-analyzer-run/run.py` — Layout extraction and batch analysis
- `cu-analyzer-run/create_and_test.py` — Create and test each analyzer
- `cu-results-export/export.py` — Export results (includes `category` column for classify-and-route)
- `cu-analyzer-validate/cu_analyzer_validator.py` — Validate schemas before creation

## Technical Reference

For full API rules, error handling, and edge cases, see **Agents.md § 4.7 — Classify-and-Route Pattern**.

## Success Criteria

This skill is complete when:
1. ✅ Inner analyzers tested individually with >80% fill rate on their document type
2. ✅ Classifier schema created with text-anchor category descriptions and correct analyzer IDs
3. ✅ Full pipeline tested on mixed-packet samples
4. ✅ Classification accuracy verified (check `category` column in exported CSV)
5. ✅ Results exported and reviewed

## Quick Reference — Full Workflow

```bash
# 1. Layout analysis on all sample types
python tools/cu-analyzer-run/run.py --layout --input samples/ --output layout_results/

# 2. Create + test inner analyzers (one per document type), keep them
python tools/cu-analyzer-run/create_and_test.py \
  --schema schemas/type1_extractor_v1.json --input samples/type1/ \
  --output test_results/type1 --keep-analyzer

python tools/cu-analyzer-run/create_and_test.py \
  --schema schemas/type2_extractor_v1.json --input samples/type2/ \
  --output test_results/type2 --keep-analyzer

# 3. Update classifier schema with real inner analyzer IDs, then create + test
python tools/cu-analyzer-run/create_and_test.py \
  --schema schemas/classifier_v1.json --input samples/mixed_packets/ \
  --output test_results/classifier_v1

# 4. Export pipeline results (includes category column)
python tools/cu-results-export/export.py \
  --input test_results/classifier_v1 --output test_results/classifier_v1/results.csv
```
