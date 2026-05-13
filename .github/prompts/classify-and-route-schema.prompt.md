---
status: ✅ IMPLEMENTED
version: 1.0.0
last_updated: 2026-04-18
---

# Prompt: Classify-and-Route Schema Design

Design classify-and-route analyzer pipelines that classify documents/videos into categories and route each to a specialized inner analyzer for field extraction.

> **Full workflow guide**: See `.github/skills/generate-analyzer-classify-route.skill.md` for the complete step-by-step process. This prompt covers schema design rules and patterns.

## When to Use Classify-and-Route

- Document packets contain **multiple distinct document types** (e.g., titles + registrations)
- Different types need **different extraction fields**
- Multi-page PDFs where each page group is a different form
- Video content with distinct segments needing different extraction

## Architecture

```
Document/Video Input
       |
       v
+---------------------------+
| Outer Analyzer (Classifier)|  contentCategories + enableSegment
| baseAnalyzerId: prebuilt-* |
+---------------------------+
       |
  +----+----+----+
  v         v    v
+-------+ +-----+ +-------+
| Inner | |Inner| | Other |  (classification only)
| Ana.1 | |Ana.2| |       |
+-------+ +-----+ +-------+
```

## Schema Identity and References

Each analyzer schema uses the standard `analyzerId` field as its identity:

```json
{
  "analyzerId": "invoice_extractor",
  "baseAnalyzerId": "prebuilt-document",
  "fieldSchema": { "fields": { ... } }
}
```

The outer classifier references inner schemas by their `analyzerId`:

```json
{
  "analyzerId": "doc_classifier",
  "baseAnalyzerId": "prebuilt-document",
  "config": {
    "enableSegment": true,
    "contentCategories": {
      "invoice": {
        "description": "...",
        "analyzerId": "invoice_extractor"
      }
    }
  }
}
```

## Nesting Depth Rules

### Documents: Up to 5-6 levels

Documents support deep recursive classification. An inner analyzer can itself be a classifier with its own `contentCategories`, routing to further inner analyzers:

```
Level 0: doc_packet_classifier
  ├── financial_docs → Level 1: financial_classifier
  │     ├── invoice → Level 2: invoice_extractor (leaf)
  │     └── receipt → Level 2: receipt_extractor (leaf)
  └── legal_docs → Level 1: legal_classifier
        ├── contract → Level 2: contract_extractor (leaf)
        └── amendment → Level 2: amendment_extractor (leaf)
```

Use deeper nesting when:
- A broad initial classification narrows into subtypes
- Different teams own different classification levels
- The document corpus has a natural taxonomy

### Videos: 1 level only

Video analyzers support **only 1 level** of classify-and-route:
- The outer classifier can segment video into categories
- Each segment routes to exactly one inner field-extraction analyzer
- Inner analyzers for video **cannot** themselves be classifiers

This limit exists because video segmentation operates on temporal boundaries (keyframes, audio transitions) which don't support the structural nesting that document pages do.

## Category Description Rules

Category descriptions follow the same two-stage pipeline rule as field descriptions — reference **text and structure**, not visual appearance:

✅ **DO**:
```json
"description": "Classify as 'invoice' when the document contains 'Invoice' heading, 'Invoice Number' label, line items with unit prices, and 'Total' or 'Amount Due'."
```

❌ **DON'T**:
```json
"description": "Classify as 'invoice' when the document has a blue header and bold company logo at the top."
```

**Best practices**:
- List **required anchors**: text that MUST appear for this classification
- List **forbidden anchors**: text that means it's NOT this type (helps resolve confusions)
- Be specific about what distinguishes this type from similar types
- For video: describe audio/transcript cues and temporal patterns, not visual frames

## Schema Organization

Put all schemas for a pipeline in the **same directory**:

```
schemas/classify_route/
├── doc_classifier.json        # Outer (root) — has contentCategories
├── invoice_extractor.json     # Inner (leaf) — has fieldSchema
├── receipt_extractor.json     # Inner (leaf) — has fieldSchema
└── README.md                  # Documents the pipeline structure
```

## Testing Pipeline

### Test inner analyzers first

```bash
# Test each inner analyzer individually
python tools/cu-analyzer-run/create_and_test.py \
  --schema schemas/classify_route/invoice_extractor.json \
  --input samples/invoices/ \
  --output test_results/invoice_v1 \
  --keep-analyzer
```

### Test full pipeline

```bash
# Using --inner-schema for explicit mapping
python tools/cu-analyzer-run/create_and_test.py \
  --schema schemas/classify_route/doc_classifier.json \
  --inner-schema invoice=schemas/classify_route/invoice_extractor.json \
  --inner-schema receipt=schemas/classify_route/receipt_extractor.json \
  --input samples/mixed_packets/ \
  --output test_results/classify_route_v1

# Future: auto-discovery from directory
python tools/cu-analyzer-run/create_and_test.py \
  --schema-dir schemas/classify_route/ \
  --input samples/mixed_packets/ \
  --output test_results/classify_route_v1
```

### What to check in results

- **Classification accuracy**: Is each segment assigned the correct category?
- **"other" rate**: High rate suggests missing categories or weak descriptions
- **Extraction quality per category**: Check fill rates for each inner analyzer's fields
- **Segment boundaries**: Are multi-page documents split at the right pages?

## Common Patterns

### Classification-only (no routing)

Categories without `analyzerId` classify but don't extract fields:

```json
"other": {
  "description": "Classify as 'other' when the document does not match any defined category."
}
```

### Mixed routing (some categories route, some don't)

```json
"contentCategories": {
  "invoice": { "description": "...", "analyzerId": "invoice_extractor" },
  "receipt": { "description": "...", "analyzerId": "receipt_extractor" },
  "cover_letter": { "description": "..." },
  "other": { "description": "..." }
}
```

### Complex document packets (Arch-style)

For document packets with many types (10+ categories), use very detailed category descriptions with:
- Required anchors (text that MUST appear)
- Forbidden anchors (text that means NOT this type)
- Classification anchors (additional evidence for interior pages)
- Closest confusable classes (fallback when evidence is weak)
- Segmentation cues (page boundaries, header/footer changes)

See `Issues/Arch/schemas/arch_segmentation_v1.json` for a production example with 10+ categories.

## See Also

- Full workflow: `.github/skills/generate-analyzer-classify-route.skill.md`
- Example schemas: `Issues/_TEMPLATE/schemas/classify_route_example/`
- Core eval: `.github/prompts/evaluate-analyzer.prompt.md`
- Field descriptions: `.github/prompts/write_schema_fields.prompt.md`
