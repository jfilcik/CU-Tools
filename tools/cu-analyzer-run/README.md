# CU Analyzer Run Tools

> **Status**: ✅ IMPLEMENTED  
> **Last Updated**: 2026-01-28

Two complementary tools for Content Understanding analysis:

## Quick Decision Guide

**Use `create_and_test.py` when:**
- ✅ You have a schema file to test
- ✅ You're developing/iterating on a schema
- ✅ You want automatic schema validation before creating analyzer
- ✅ You want automatic cleanup (delete analyzer after testing)

**Use `run.py` when:**
- ✅ You have an existing analyzer ID
- ✅ You need layout extraction only (first step before schema development)
- ✅ You're running production batch processing
- ✅ You need fine-grained control over operations

---

## Tool 1: `create_and_test.py` - Schema Development Workflow

**Purpose**: Create analyzer from schema, validate, test, and optionally clean up.

**Best for**: Schema development and testing

**Features**:
- ✅ Automatic schema validation before creating analyzer (catches errors early)
- ✅ Creates analyzer from schema file
- ✅ Runs analysis on samples
- ✅ Optional cleanup (delete analyzer after)
- ✅ Perfect for iterative schema development

### Usage Examples

```bash
# Basic: Create analyzer, test, and clean up
python create_and_test.py \
  --schema schemas/invoice_v2.json \
  --input samples/ \
  --output test_results/v2/

# With parallel processing (3 documents at once - faster!)
python create_and_test.py \
  --schema schemas/invoice_v2.json \
  --input samples/ \
  --output test_results/v2/ \
  --max-workers 3

# Stability test (10 iterations per document)
python create_and_test.py \
  --schema schemas/invoice_v2.json \
  --input samples/ \
  --output test_results/v2_stability/ \
  --iterations 10

# Keep analyzer after testing (don't delete)
python create_and_test.py \
  --schema schemas/invoice_v2.json \
  --input samples/ \
  --output test_results/v2/ \
  --keep-analyzer
```

### CLI Options

| Option | Description |
|--------|-------------|
| `--schema`, `-s` | Path to analyzer schema JSON file (required) |
| `--input`, `-i` | Input file or directory (required) |
| `--output`, `-o` | Output directory for results (required) |
| `--analyzer-id` | Custom analyzer ID (auto-generated if not provided) |
| `--iterations` | Number of iterations per document (default: 1) |
| `--timeout` | Analysis timeout in seconds (default: 180) |
| `--keep-analyzer` | Keep analyzer after testing (don't delete) |
| `--api-version` | CU API version (default: from env or 2025-11-01) |
| `--diagnostics` | Send `x-ms-diagnostics: true` on analyze and result-polling requests |
| `--max-workers` | Number of parallel workers (default: 1, recommended: 3-5 for large batches) |

---

## Tool 2: `run.py` - Production Operations

**Purpose**: Run analysis with existing analyzers or extract layout

**Best for**: Production use, layout extraction, and when you already have an analyzer ID

**Features**:
- ✅ Run analysis on existing analyzer (by ID)
- ✅ Extract layout without field extraction (`--layout` flag)
- ✅ Batch processing
- ✅ Stability testing
- ✅ More control and flexibility

### Usage Examples

## Installation

```bash
cd tools/cu-analyzer-run
pip install -r requirements.txt
```

## Configuration

Set environment variables in `.env` at the repository root:
```
AZURE_AI_ENDPOINT=https://your-resource.services.ai.azure.com/
AZURE_AI_API_KEY=your-api-key
CU_API_VERSION=2024-12-01-preview
```

```bash
# MOST COMMON: Extract layout (first step before creating schema)
python run.py \
  --layout \
  --input samples/ \
  --output layout_results/

# Use existing analyzer for single document
python run.py \
  --analyzer-id invoice-v1 \
  --input samples/invoice_001.pdf \
  --output test_results/single/

# Request diagnostic infos such as LLMStats
python run.py \
  --analyzer-id prebuilt-invoice \
  --input samples/invoice_001.pdf \
  --output test_results/invoice_diagnostics/ \
  --api-version 2025-11-01 \
  --diagnostics

# Batch analysis with parallel processing (5 documents at once)
python run.py \
  --analyzer-id invoice-v1 \
  --input samples/invoices/ \
  --output test_results/batch_001/ \
  --max-workers 5

# Stability test (10 iterations) with existing analyzer
python run.py \
  --analyzer-id invoice-v1 \
  --input samples/invoice_001.pdf \
  --iterations 10 \
  --output test_results/stability/
```

### CLI Options

| Option | Description |
|--------|-------------|
| `--input`, `-i` | Input file or directory (required) |
| `--output`, `-o` | Output directory for results (required) |
| `--analyzer-id`, `-a` | Analyzer ID to use (required unless `--layout`) |
| `--layout` | Run prebuilt-layout analysis instead of custom analyzer |
| `--iterations`, `-n` | Number of iterations per document (default: 1) |
| `--timeout`, `-t` | Timeout in seconds per analysis (default: 180) |
| `--run-id` | Custom run ID (auto-generated if not specified) |
| `--api-version` | CU API version (default: from env or 2025-11-01) |
| `--diagnostics` | Send `x-ms-diagnostics: true` on analyze and result-polling requests |
| `--max-workers` | Number of parallel workers (default: 1, recommended: 3-5 for large batches) |

For `2025-11-01`, use `--diagnostics` to opt in to diagnostic `infos`. The
header must be present when retrieving `analyzerResults/{id}`; CU-Tools sends it
on both the initial analyze request and every polling request. The
`2026-06-01-preview` service may return diagnostic `infos` without the flag.
Messages such as `LLMStats` are human-readable diagnostics and should not be
parsed as a stable telemetry schema.

---

## Output Structure

```
output_folder/
├── metadata.json           # Run configuration and summary
└── results/
    ├── document_001.json   # Results for each document
    ├── document_002.json
    └── ...
```

For stability tests with iterations:
```
output_folder/
├── metadata.json
└── results/
    ├── document_001.json       # Iteration 1
    ├── document_001_iter002.json
    ├── document_001_iter003.json
    └── ...
```

For layout extraction:
```
output_folder/
├── metadata.json
├── document_001.layout.json    # Full layout result
├── document_001.layout.md      # Markdown representation
└── ...
```

---

## PDF Protection Detection

Both tools automatically detect protected PDFs and skip them before making API calls. This prevents wasted API costs and provides clear error messages.

### Detected Protection Types

1. **Password-protected PDFs** - Requires password to open
2. **Encrypted PDFs** - Standard PDF encryption
3. **Microsoft Office protected PDFs** - Content renders but shows only a protection message

### Example Output

```
⚠️  Found 3 protected/encrypted PDF(s) - these will be skipped:
   - document1.pdf: Content-protected (Microsoft Office protection)
   - document2.pdf: Password-protected (requires password)
   - document3.pdf: Encrypted: decryption failed

Found 7 processable document(s) (3 skipped)
```

### Metadata

Skipped files are recorded in `metadata.json`:
```json
{
  "skipped_protected_files": [
    {"file": "document1.pdf", "reason": "Content-protected (Microsoft Office protection)"},
    {"file": "document2.pdf", "reason": "Password-protected (requires password)"}
  ]
}
```

### Dependencies

PDF protection detection requires PyPDF2:
```bash
pip install PyPDF2>=3.0.0
```

If PyPDF2 is not installed, protection detection is skipped and files are processed normally (which may result in empty extraction results for protected files).

---

## Typical Workflow

### First Time (Schema Development)

1. **Extract layout** to understand document structure:
   ```bash
   python run.py --layout --input samples/ --output layout/
   ```

2. **Review layout files** (`.layout.md`) to understand structure

3. **Create schema** based on layout (see `.github/prompts/generate-analyzer-schema.prompt.md`)

4. **Test schema** with validation and analysis:
   ```bash
   python create_and_test.py --schema schema.json --input samples/ --output results/
   ```

5. **Iterate** on schema based on results (repeat step 4)

6. **Keep final analyzer** when satisfied:
   ```bash
   python create_and_test.py --schema schema.json --input samples/ --output results/ --keep-analyzer
   ```

### Production Use (With Existing Analyzer)

1. **Run batch processing**:
   ```bash
   python run.py --analyzer-id prod-invoice --input invoices/ --output results/
   ```

2. **Export results** to CSV for analysis:
   ```bash
   python ../cu-results-export/export.py --input results/ --output results.csv
   ```

## Related Tools

- `cu-analyzer-validate` - Standalone schema validation (used automatically by `create_and_test.py`)
- `cu-results-export` - Export results to CSV/Excel
- `cu-client` - Python client library for CU API

## Related Skills

- `.github/skills/generate-analyzer.skill.md` - Complete workflow from samples to schema
- `.github/skills/eval-cu.skill.md` - Evaluation and testing workflows

### Single Document
```json
{
  "document": "invoice_001.pdf",
  "analyzer_id": "invoice-v1",
  "timestamp": "2025-01-24T10:30:00Z",
  "fields": {
    "VendorName": {
      "value": "Acme Corp",
      "confidence": 0.95,
      "boundingBox": [...]
    }
  }
}
```

### Batch Run
```
runs/batch_001/
  ├── metadata.json        # Run configuration
  ├── results/
  │   ├── invoice_001.json
  │   ├── invoice_002.json
  │   └── ...
  ├── summary.json         # Aggregated stats
  └── errors.log           # Any errors
```

## Dependencies

See `requirements.txt`:
- requests
- python-dotenv
- azure-identity (for AAD auth)
- tqdm (progress bars)

## Implementation Status

- [x] README and structure
- [ ] validate_schema.py
- [ ] create_analyzer.py
- [ ] run.py
- [ ] requirements.txt
- [ ] Example .env.sample

## Related Skills

- `.github/skills/run_cu_analysis.skill.md` - Complete workflow using this tool
