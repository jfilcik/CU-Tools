# AGENTS.md - CU Analyzer Testing Lab

## Purpose

This repository is a **streamlined toolkit for creating and testing Azure AI Content Understanding (CU) analyzers**. It's designed for developers who need to extract structured data from documents (invoices, forms, contracts, etc.) using AI-powered field extraction.

**Target Audience**: Developers building CU analyzers for production use, testing schema designs, and validating extraction quality.

> **⚠️ DEDUPLICATION RULE**: This file is the authoritative source for technical specifications.
> `.github/copilot-instructions.md` contains behavioral guidance and quick references only.
> Do NOT duplicate content between these files. When adding new content:
> - **Here**: API rules, error handling, testing patterns, definition of done, correctness rules
> - **copilot-instructions.md**: AI behavior, vocabulary, style constraints, navigation hints

**Key Use Cases**:
- Schema development with AI-assisted field generation
- Scale testing (1×N documents) to verify coverage across document variations
- Stability testing (N×1 document) to measure extraction consistency
- Cost estimation and token usage analysis
- Results export and analysis in CSV/Excel format

---

## Repo Map

### Core Capabilities

**Analysis & Testing**:
- `tools/cu-analyzer-run/`
  - `run.py` - Run analysis with existing analyzer or extract layout for schema development
  - `create_and_test.py` - Create analyzer from schema and test on samples (all-in-one workflow)

**Validation & Export**:
- `tools/cu-analyzer-validate/`
  - `cu_analyzer_validator.py` - Validate schema before creating analyzer (auto-runs in create_and_test.py)
- `tools/cu-results-export/`
  - `export.py` - Export JSON results to CSV/Excel for analysis

**Client Library**:
- `tools/cu-client/`
  - `content_understanding_client.py` - Base CU API client (shared by all tools)

**Supporting Tools**:
- `tools/cu-reading-order-viz/`
  - `visualize_reading_order.py` - Overlays numbered bounding boxes and directional arrows onto PDF pages to visualize the reading order produced by CU Layout extraction. Use to diagnose mis-ordered paragraphs or layout quality issues. Supports single documents, batch folders, side-by-side comparison of two layout sources (e.g. prod vs selfhost), and per-page filtering. Auto-detects CU (`result.contents[].paragraphs`) and Document Intelligence (`analyzeResult.paragraphs`) JSON formats.
- `tools/review_file/`
  - `review_file.py` - Automated document review and extraction
- `tools/test_notebooks/`
  - `test_notebooks.py` - Jupyter notebook testing

### Documentation

**Getting Started**:
- `README.md` - Overview and quick start
- `GETTING_STARTED.md` - Step-by-step first analyzer walkthrough
- `Agents.md` (this file) - Authoritative guide for AI assistants

**Guidance**:
- `.github/copilot-instructions.md` - AI assistant behavior and navigation preferences
- `.github/TROUBLESHOOTING.md` - Common issues and solutions
- `.github/ISSUE_TEMPLATE.md` - Issue reporting template
- `.github/PULL_REQUEST_TEMPLATE.md` - PR template

**AI Prompts & Skills**:
- `.github/prompts/` - AI-assisted task prompts (6 files)
  - `analyze-document-structure.prompt.md` - Understand document layout
  - `generate-analyzer-schema.prompt.md` - Create analyzer schema
  - `write_schema_fields.prompt.md` - Write field descriptions
  - `evaluate-analyzer.prompt.md` - Core eval workflow (scale/stability)
  - `evaluate-analyzer-video.prompt.md` - Video-specific eval (timestamps, keyframes)
  - `classify-and-route-schema.prompt.md` - Classifier schema design and nesting rules
- `.github/skills/` - Complete workflow guides (5 files)
  - `generate-analyzer.skill.md` - Analyzer creation workflow (standard, single document type)
  - `generate-analyzer-video.skill.md` - Video analyzer with keyframe-anchored timestamps
  - `generate-analyzer-classify-route.skill.md` - Classifier + multi-type routing (advanced pattern)
  - `eval-cu.skill.md` - Evaluation workflow

### Examples

**Project Examples** (Issues/):
- `Issues/_TEMPLATE/` - Template for new analyzer projects
- `Issues/WK_Runs/WK/` - K-1 tax form extraction (complex nested fields)
- `Issues/Crowne/` - Purchase order extraction (line items)
- `Issues/LuciHub/` - Video object detection with timestamps (keyframe anchoring investigation)
- `Issues/Carvana/` - Vehicle title/registration classify-and-route pattern
- `Issues/LeftTurn/` - Legal document extraction
- Other project-specific examples

**Learning Resources** (AzureSamples/):
- `AzureSamples/notebooks/` - Jupyter tutorial notebooks
- `AzureSamples/analyzer_templates/` - Example analyzer schemas

### Configuration

- `.env.sample` - Template for Azure credentials
- `requirements.txt` - Core Python dependencies
- `schemas/` - User-created analyzer schemas

---

## Commands

### Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Configure Azure credentials
cp .env.sample .env
# Edit .env with your AZURE_AI_ENDPOINT and AZURE_AI_API_KEY
```

**Explanation**: Installs all required Python packages and sets up Azure AI credentials. The `.env` file must contain your Azure AI endpoint and API key from Azure AI Foundry.

### Validate Setup

```bash
# Test Azure connectivity (if validation scripts exist)
python tools/cu-analyzer-validate/cu_analyzer_validator.py schemas/example.json
```

**Explanation**: Validates that your schema is correct before attempting to create an analyzer. This catches errors early and provides clear error messages.

### Test

```bash
# Validate a schema file
python tools/cu-analyzer-validate/cu_analyzer_validator.py schemas/my_analyzer.json

# Run validation on multiple schemas
find schemas -name "*.json" -exec python tools/cu-analyzer-validate/cu_analyzer_validator.py {} \;
```

**Explanation**: Use validation to catch schema errors before creating analyzers. The validator checks JSON syntax, required fields, field types, and description quality.

### Run Examples

**Extract Layout** (Stage 1: OCR + Document Structure):
```bash
python tools/cu-analyzer-run/run.py \
  --layout \
  --input samples/ \
  --output layout_results/
```

**Explanation**: Runs prebuilt-layout analysis to extract text and document structure. Use this to understand document layout before creating schemas. Creates `.layout.md` markdown files showing extracted text.

**Create Analyzer and Test** (Complete Workflow):
```bash
python tools/cu-analyzer-run/create_and_test.py \
  --schema schemas/my_analyzer_v1.json \
  --input samples/ \
  --output test_results/v1
```

**Explanation**: All-in-one command that validates schema, creates analyzer, and runs tests on sample documents. Use this for iterative schema development.

**Run Analysis with Existing Analyzer**:
```bash
# Single document
python tools/cu-analyzer-run/run.py \
  --analyzer-id my-analyzer \
  --input document.pdf \
  --output results/single/

# Batch analysis (folder)
python tools/cu-analyzer-run/run.py \
  --analyzer-id my-analyzer \
  --input documents/ \
  --output results/batch/

# Stability test (10 iterations)
python tools/cu-analyzer-run/run.py \
  --analyzer-id my-analyzer \
  --input document.pdf \
  --iterations 10 \
  --output results/stability/
```

**Explanation**: Use these patterns for testing existing analyzers. Stability tests (N×1) measure consistency, batch analysis (1×N) measures coverage.

**Export Results to CSV**:
```bash
python tools/cu-results-export/export.py \
  --input test_results/v1 \
  --output test_results/v1/results.csv
```

**Explanation**: Converts JSON results to CSV for analysis in Excel. Creates one row per document with all extracted fields, confidence scores, and metadata.

---

## API Rules & Correctness

### 4.1 Authentication

**API Key vs DefaultAzureCredential**:
- Primary: Use API key from `.env` file (`AZURE_AI_API_KEY`)
- Alternative: Use `DefaultAzureCredential` for managed identity scenarios
- Client initialization checks for API key first, falls back to credential

**.env Management**:
- **NEVER commit `.env` to git** - contains sensitive credentials
- `.env.sample` provides template
- `.gitignore` excludes `.env` by default

**Client Initialization Validation**:
```python
# Client validates credentials on initialization
client = AzureContentUnderstandingClient(endpoint, credential)
# Raises ValueError if endpoint/credential invalid
```

### 4.2 Rate Limits & Retries

**Rate Limits**:
- Per-minute limits vary by resource tier
- Per-second limits may apply
- HTTP 429 indicates rate limit exceeded

**Auto-Retry Behavior**:
- Client uses exponential backoff for 429 responses
- Default retry: 3 attempts with increasing delays
- Configurable via client initialization

**Polling Behavior**:
- Analysis operations are async (submit + poll for completion)
- Default timeout: 180 seconds
- Configurable via `--timeout` parameter

### 4.3 Pagination

**List Operations**:
```python
# list_analyzers() returns paginated results
analyzers = client.list_analyzers(top=50)  # Max 50 per page
```

**Results Pagination**:
- Maximum 1000 results per response
- Use continuation tokens for large result sets
- Client handles pagination automatically

### 4.4 Error Taxonomy

**ValueError**: Invalid input parameters (e.g., missing analyzer ID, invalid file path)

**TimeoutError**: Operation exceeded timeout limit (default 180s)

**HTTP Status Codes**:
- `401 Unauthorized` - Invalid API key or missing authentication
- `403 Forbidden` - Insufficient permissions or resource access denied
- `429 Too Many Requests` - Rate limit exceeded (auto-retries)
- `4xx Client Errors` - Invalid request (check parameters)
- `5xx Server Errors` - Azure service issues (retry may resolve)

**Logging Standards**:
- Use Python `logging` module for all tools
- Log level: INFO for normal operations, DEBUG for detailed tracing
- Include request IDs in error logs for Azure support

### 4.5 Two-Stage Pipeline ⭐ CRITICAL

Content Understanding uses a **two-stage pipeline**:

```
Stage 1: Content Extraction (OCR + Layout)
  ↓ Extracts text, identifies structure (tables, sections, headers)
  ↓ Outputs: Structured text + layout metadata (NOT original images)
  ↓
Stage 2: Field Extraction (AI analyzes text)
  ↓ GPT-4.1 analyzes extracted text and structure
  ↓ Uses your field descriptions to identify values
  ↓ Returns: Field values + confidence scores + grounding
```

**Critical Rules for Field Descriptions**:

✅ **DO**:
- Reference **text content, labels, and structure**
- Use **text-based location hints**: "near 'Total:' label", "in delivery section"
- Leverage base analyzers (prebuilt-document, prebuilt-layout) for rich structure
- Provide **alternative labels**: "May be labeled as 'Invoice Date', 'Billing Date', or 'Date'"
- Include **format examples**: "Format: MM/DD/YYYY. Examples: '01/15/2024', '2024-01-15'"

❌ **DON'T**:
- Reference **visual appearance**: colors, fonts, bold, italics, font size
- Describe by visual position alone without text context
- Expect model to "see" images directly - it analyzes extracted text

**Example - Good Field Description**:
```json
"invoiceDate": {
  "type": "string",
  "method": "extract",
  "description": "The date when the invoice was issued, typically found at the top right corner near the invoice number. May be labeled as 'Invoice Date', 'Date', or 'Billing Date'. Format is usually MM/DD/YYYY or DD-MM-YYYY. Examples: '01/15/2024', 'January 15, 2024'."
}
```

### 4.6 Schema Design Rules

**Required Elements**:
1. **Clear field descriptions** with location hints and alternative labels
2. **Explicit extraction method**: `extract`, `generate`, or `classify`
3. **Appropriate field types**: string, number, boolean, array, object
4. **Language matching**: Field descriptions must match document language

**Field Description Best Practices**:
- Include **what to extract**: "The total amount including tax"
- Specify **where to find it**: "typically found at the bottom of the invoice"
- List **alternative labels**: "May be labeled as 'Total', 'Amount Due', or 'Grand Total'"
- Provide **format expectations**: "Format: Currency with 2 decimals. Example: '$1,234.56'"
- Add **disambiguation**: "Not to be confused with Subtotal (which excludes tax)"

**Avoid Common Pitfalls**:
- ❌ Vague descriptions: "Get the date" → ✅ "Invoice issue date from top right"
- ❌ Negative language: "Not the due date" → ✅ "Issue date when invoice was created"
- ❌ Visual references: "Bold text at top" → ✅ "Text near 'Invoice #' label"
- ❌ Language mismatch: English descriptions for Spanish documents
- ❌ Missing method: Always specify extract/generate/classify

**Testing Strategy**:
- Start with 3-5 representative sample documents
- Extract layout first to understand structure
- Iterate on descriptions based on results
- Test across document variations

### 4.7 Classify-and-Route Pattern (contentCategories)

CU supports a **classify-and-route** architecture where an outer analyzer classifies pages/segments and routes each to a specialized inner analyzer for field extraction. This is configured via `config.contentCategories`.

> **Guided workflow**: Use `.github/skills/generate-analyzer-classify-route.skill.md` for step-by-step
> instructions on building a classify-and-route pipeline. This section covers the technical rules and API details.

> **Standard pattern first**: If all your documents share the same structure and fields, use the standard
> single-analyzer workflow (`.github/skills/generate-analyzer.skill.md`). Classify-and-route is an
> advanced pattern for packets containing **multiple distinct document types**.

**Architecture**:
```
Document Packet (multi-page PDF or batch of images)
        |
        v
+---------------------------+
| Outer Analyzer (Classifier)|  config.contentCategories + enableSegment
| baseAnalyzerId: prebuilt-* |
+---------------------------+
        |
   +----+----+----+
   v         v    v
+-------+ +-----+ +-----+
| Inner | |Inner| |Other|  (no routing — classification only)
| Ana.1 | |Ana.2| |     |
+-------+ +-----+ +-----+
```

**When to Use**:
- Document packets contain **multiple document types** (e.g., titles + registrations + receipts)
- You need to **classify before extracting** — different fields for different doc types
- Multi-page PDFs where each page (or page group) is a different form
- Processing batches from a known set of document categories

**Outer Analyzer Schema** (classifier/router):
```json
{
    "description": "Classify and route documents",
    "baseAnalyzerId": "prebuilt-document",
    "config": {
        "enableSegment": true,
        "contentCategories": {
            "invoice": {
                "description": "Classify as 'invoice' when the document contains 'Invoice' heading, invoice number, line items with prices, and a total amount.",
                "analyzerId": "my_invoice_extractor"
            },
            "receipt": {
                "description": "Classify as 'receipt' when the document contains 'Receipt' heading, transaction details, and payment amount.",
                "analyzerId": "my_receipt_extractor"
            },
            "other": {
                "description": "Classify as 'other' when the document does not match invoice or receipt patterns."
            }
        },
        "omitContent": true
    },
    "models": { "completion": "gpt-4.1" }
}
```

**Key Rules**:

1. **No `fieldSchema` needed** — The outer analyzer only classifies; field extraction is delegated to inner analyzers referenced by `analyzerId`.

2. **`enableSegment: true`** — Required for the classifier to segment multi-page documents into logical units before classifying each segment.

3. **Category descriptions** — Write classification criteria using text anchors (headings, labels, keywords), NOT visual cues. The two-stage pipeline rule (§4.5) applies here too.

4. **Inner analyzers must exist first** — The `analyzerId` values must reference analyzers that already exist in your Azure AI resource. Create inner analyzers before the classifier.

5. **Categories without `analyzerId`** — Categories like "other" can omit `analyzerId` for classification-only (no field extraction). The result will include the category label but no extracted fields.

6. **`omitContent: true`** — Recommended for classifiers to reduce token usage. The inner analyzers access the full content independently.

**Inner Analyzer Schemas** — Standard field extraction schemas with `fieldSchema`. Each is a regular analyzer optimized for one document type.

**Deployment Sequence**:
1. Create all inner analyzers (field extraction schemas with `fieldSchema`)
2. Note their analyzer IDs
3. Update the classifier schema with real analyzer IDs in `contentCategories`
4. Create the classifier analyzer
5. Submit documents to the classifier — it routes automatically

**Result Structure** — Classify-and-route results have one entry per classified segment in `result.contents[]`, each with a `category` field:
```json
{
  "result": {
    "contents": [
      {
        "category": "invoice",
        "fields": { "invoiceNumber": {...}, "total": {...} }
      },
      {
        "category": "receipt",
        "fields": { "transactionId": {...}, "amount": {...} }
      }
    ]
  }
}
```

**Testing Classify-and-Route**:
- Test inner analyzers individually first with their own sample documents
- Then test the full pipeline with mixed-document packets
- Verify classification accuracy before evaluating extraction quality
- Use `Issues/Carvana/review_app/test_classify_route.py` as a reference implementation

### 4.8 Testing Patterns

**Scale Test (1×N): Coverage Verification**
- Run many different documents once each
- Purpose: Verify fill rate and consistency across document variations
- Pattern: 100+ documents from production corpus
- Metrics: Fill rate per field, confidence distribution, edge cases
- Use: Schema validation before production deployment

**Stability Test (N×1): Consistency Verification**
- Run same document multiple times (typically 10 iterations)
- Purpose: Measure extraction consistency and detect randomness
- Pattern: 10 runs of representative documents
- Metrics: Confidence variance, field stability, extraction jitter
- Use: Field reliability analysis, confidence threshold tuning

**Export and Analyze**:
- Always export results to CSV for analysis
- Include: latency, tokens (prompt/completion), confidence, fill rate
- Compare across schema versions to detect drift/regression

### 4.9 Cost & Token Management

**Token Tracking**:
- Results include `promptTokens` and `completionTokens`
- Use for cost estimation (varies by model/tier)
- Export tokens to CSV for analysis

**Cost Optimization**:
- Use appropriate base analyzers (prebuilt-layout vs prebuilt-document)
- Minimize redundant analyses (cache results where possible)
- Consider field complexity vs extraction value

---

## Critical Correctness Rules

### Rule 1: Two-Stage Pipeline (REQUIRED)

**Rule**: Field descriptions must reference text content and structure, never visual appearance.

**Consequence of Violation**: Low confidence, incorrect extractions, or null values. Model cannot "see" colors, fonts, or styling.

**Example**:
- ❌ Bad: "Extract the bold text at the top of the page"
- ✅ Good: "Extract the text labeled 'Invoice Number' typically found at the top of the page"

### Rule 2: Schema Design (REQUIRED)

**Rule**: Every field must have a clear, detailed description with location hints and alternative labels.

**Consequence of Violation**: Low fill rates, low confidence scores, inconsistent extractions.

**Example**:
- ❌ Bad: "Get the date"
- ✅ Good: "The invoice issue date, found near the 'Invoice #' label at the top right. May be labeled as 'Invoice Date', 'Date', or 'Issued'. Format: MM/DD/YYYY."

### Rule 3: Testing Patterns (RECOMMENDED)

**Rule**: Always run both scale (1×N) and stability (N×1) tests before production deployment.

**Consequence of Violation**: Production failures due to edge cases or inconsistent extractions.

**Example**:
```bash
# Scale test: 100 documents
python tools/cu-analyzer-run/run.py --analyzer-id my-analyzer --input corpus/ --output results/scale/

# Stability test: 10 iterations
python tools/cu-analyzer-run/run.py --analyzer-id my-analyzer --input sample.pdf --iterations 10 --output results/stability/
```

### Rule 4: Error Handling (REQUIRED)

**Rule**: Always use try/except blocks and log errors with context.

**Consequence of Violation**: Silent failures, difficult debugging, lost error context.

**Example**:
```python
import logging

try:
    result = client.analyze_document(analyzer_id, document)
except ValueError as e:
    logging.error(f"Invalid input for {document}: {e}")
    raise
except TimeoutError as e:
    logging.error(f"Analysis timeout for {document}: {e}")
    raise
```

### Rule 5: File Path Handling (REQUIRED)

**Rule**: Use `pathlib.Path` for cross-platform compatibility. Accept both absolute and relative paths.

**Consequence of Violation**: Path failures on Windows vs Linux, broken file references.

**Example**:
```python
from pathlib import Path

input_path = Path(args.input).resolve()  # Convert to absolute
if not input_path.exists():
    raise ValueError(f"Input path does not exist: {input_path}")
```

---

## When to Update

### Add New Validation

**When**: Creating a new validation script for connectivity, schema, or service checks.

**Pattern**: Follow `cu_analyzer_validator.py` structure
- Use standard library only (no external dependencies)
- Return clear error messages with context
- Exit with non-zero status on failure
- Include usage examples in docstring

**Update Required**:
- Create script in `tools/cu-analyzer-validate/`
- Add to "Validate Setup" section in this file
- Update tool README

### Add New Helper

**When**: Creating a wrapper function or utility for the CU client.

**Pattern**: Extend `AzureContentUnderstandingClient` class
- Add method to client class
- Include error handling with try/except
- Add logging for debugging
- Document parameters and return values

**Update Required**:
- Update `tools/cu-client/content_understanding_client.py`
- Add to "API Rules & Correctness" section if it changes API behavior
- Update tool README

### Update Documentation

**When**: Repository structure changes, new tools added, or workflows modified.

**Update Required**:
- Update `README.md` for user-facing changes
- Update relevant tool READMEs
- Update this file (Agents.md) if repo map or commands change
- Update `.github/copilot-instructions.md` for AI behavior changes

### Add Example

**When**: Creating a new example project to demonstrate analyzer patterns.

**Pattern**: Copy `Issues/_TEMPLATE/` structure
- Create `Issues/<project>/` folder
- Add `samples/`, `schemas/`, `test_results/`, `reports/` subfolders
- Include project-specific README.md
- Document use case and field patterns

**Update Required**:
- Create project in `Issues/<project>/`
- Add reference in "Examples" section of this file
- Consider adding to README.md if notable pattern

### Add API Rules

**When**: Discovering new CU service behaviors, rate limits, or API patterns.

**Update Required**:
- Add to "API Rules & Correctness" section
- Include error codes and handling patterns
- Document consequences of violations
- Add examples demonstrating correct usage

---

## Definition of Done

Before finishing a change:

### 1. Tests Pass
- [ ] Core functionality works (run example commands)
- [ ] Schema validation succeeds (if applicable)
- [ ] No syntax errors in Python code

### 2. Tools Run
- [ ] Validation scripts execute successfully
- [ ] Analysis tools complete without errors
- [ ] Export tools produce valid output

### 3. Examples Work
- [ ] Relevant examples in Issues/ still function correctly
- [ ] Test commands from README work with new changes
- [ ] Example paths updated if structure changed

### 4. Documentation Updated
- [ ] README.md reflects changes (if user-facing)
- [ ] Tool READMEs updated (if tool-specific)
- [ ] This file (Agents.md) updated (if repo structure changed)
- [ ] Inline code comments added (if complex logic)

### 5. Report Created (for analyzer work)
- [ ] Schema validates successfully
- [ ] Fill rate >80% for critical fields (target, adjust per use case)
- [ ] Confidence >0.85 for critical fields (target, adjust per use case)
- [ ] Results exported to CSV
- [ ] Report documents tradeoffs and decisions

**For new analyzers specifically**:
- [ ] Schema follows design best practices (clear descriptions, location hints, alternative labels)
- [ ] Field extraction methods specified (extract/generate/classify)
- [ ] Tested on 3-5 representative samples minimum
- [ ] Grounding enabled for debugging (estimateSourceAndConfidence: true)

---

## Quick Reference

### File a Bug

**What to include**:
1. Clear description of expected vs actual behavior
2. Steps to reproduce (commands run, input files)
3. Error messages (full stack traces)
4. Environment details (Python version, OS)
5. Schema file (if relevant)
6. Sample document (if not sensitive)

**Where**: Use `.github/ISSUE_TEMPLATE.md` for structured reporting

### Get Help

**Resources**:
1. **README.md**: Overview and quick start
2. **GETTING_STARTED.md**: Step-by-step first analyzer walkthrough
3. **.github/TROUBLESHOOTING.md**: Common issues and solutions
4. **Tool READMEs**: Detailed tool-specific documentation
5. **.github/skills/**: Complete workflow guides

**Escalation Path**:
- Check TROUBLESHOOTING.md first
- Review relevant tool README
- Search Issues/ for similar examples
- Create GitHub issue with template

### Common Commands Cheat Sheet

```bash
# Validate schema (supports both field-extraction and classify-and-route schemas)
python tools/cu-analyzer-validate/cu_analyzer_validator.py schemas/my_schema.json

# Extract layout for schema development
python tools/cu-analyzer-run/run.py --layout --input samples/ --output layout/

# Create analyzer and test (field extraction)
python tools/cu-analyzer-run/create_and_test.py --schema schemas/v1.json --input samples/ --output results/

# Create analyzer and test (classify-and-route — see Issues/Carvana/review_app/test_classify_route.py)

# Run scale test
python tools/cu-analyzer-run/run.py --analyzer-id my-analyzer --input docs/ --output results/scale/

# Run stability test
python tools/cu-analyzer-run/run.py --analyzer-id my-analyzer --input doc.pdf --iterations 10 --output results/stability/

# Export to CSV (includes category column for classify-and-route results)
python tools/cu-results-export/export.py --input results/ --output results.csv
```

### Tool Paths

- **CU Client**: `tools/cu-client/content_understanding_client.py`
- **Analyzer Run**: `tools/cu-analyzer-run/run.py`
- **Create & Test**: `tools/cu-analyzer-run/create_and_test.py`
- **Validator**: `tools/cu-analyzer-validate/cu_analyzer_validator.py`
- **Exporter**: `tools/cu-results-export/export.py`
- **Reading Order Visualizer**: `tools/cu-reading-order-viz/visualize_reading_order.py`
- **Examples**: `Issues/_TEMPLATE/`, `Issues/WK_Runs/WK/`, `Issues/Crowne/`, `Issues/Carvana/`
- **Prompts**: `.github/prompts/*.prompt.md`
- **Skills**: `.github/skills/*.skill.md`

---

**End of Agents.md** (v1.2 - 2026-07-10)
