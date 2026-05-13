
> **Note:** This repository includes AI-generated experimental tooling and workflows. Expect rapid iteration and breaking changes. See `.github/copilot-instructions.md` and `Agents.md` for Copilot agent behavior and workflow details.

# CU-Tools

A toolkit for building, testing, and evaluating Azure AI Content Understanding analyzers — from quick API exploration to eval-driven development with coding agents.

---

## What is Azure Content Understanding?

Azure Content Understanding analyzes documents, images, audio, and video — transforming them into structured, searchable data. It uses a three-stage pipeline of parsing, classifying, and extracting content based on custom schemas you define.

### CU Pipeline: Parse → Classify → Extract

| Input Type | Parse | Classify | Extract |
|-----------|-------|----------|---------|
| **Document** | OCR, layout detection | Form type, category | Tables, signatures, fields |
| **Image** | Object detection | Content category | Conditions, attributes |
| **Video** | Frames, transcription | Scene, event type | Objects, entities, timestamps |
| **Audio** | Transcription | Speaker, tone | Entities, intents, topics |

Each stage leverages modality-specific processing before your custom schema fields are extracted.

---

## 🚀 Quick Start

### Prerequisites

- **Microsoft Foundry** with Content Understanding enabled ([Setup Guide](docs/create_azure_ai_service.md))
- **Python 3.9+** (for Python tools)
- **VS Code** with REST Client extension (for `.http` files)

### Setup

```bash
# Clone repository
git clone https://github.com/jfilcik/CU-Tools.git
cd CU-Tools

# Install Python dependencies
pip install -r requirements.txt

# Configure Azure credentials
cp .env.sample .env
# Edit .env with your Azure AI endpoint and API key
```

---


## 🎯 Two Ways to Work

### 1. Copilot AI-Assisted Path (Recommended)

Use the built-in Copilot skills for a guided, eval-driven workflow. This path combines AI-powered schema generation, validation, and systematic testing using the Python tools:

#### Common Copilot Skills

- **Generate Analyzer Schema**
  ```
  /generate-analyzer-schema Create an analyzer for invoices from samples in my_samples/
  ```
  Walks through: layout extraction → field identification → schema generation → validation → testing.

- **Evaluate Analyzer (Evals)**
  ```
  /eval-cu Run a scale eval on my-analyzer with documents in test_data/
  ```
  Two modes:
    - **Scale (1×N)** — Many docs once for coverage and accuracy
    - **Stability (N×1)** — Same doc many times for consistency

📖 See `.github/skills/` for complete workflow guides.

#### Python Tools (used by Copilot and for manual runs)

```bash
# Extract layout to understand document structure
python tools/cu-analyzer-run/run.py --layout --input samples/ --output layout/

# Validate a schema
python tools/cu-analyzer-validate/cu_analyzer_validator.py schemas/my_schema.json

# Create analyzer and test
python tools/cu-analyzer-run/create_and_test.py \
  --schema schemas/my_schema.json \
  --input samples/ \
  --output test_results/

# Export results to CSV
python tools/cu-results-export/export.py --input test_results/ --output results.csv
```

---

### 2. HTTP REST Client (Quick Exploration)

Use the `.http` files for direct API exploration in VS Code:

```
# Open in VS Code with REST Client extension
CU_API_Testing/CU-API-Testing-Guide.http
```

Covers: content extraction, domain analyzers (invoice, receipt, etc.), RAG, custom analyzers, video analysis, and analyzer management.

---

## 📖 Tutorials

Step-by-step examples using public sample data:

| Tutorial | What You'll Learn |
|----------|-------------------|
| **[01-API-Testing](Examples/01-API-Testing/)** | Explore CU REST APIs with HTTP test files in VS Code |
| **[02-Invoice-Extraction](Examples/02-Invoice-Extraction/)** | Build a document analyzer using the agent-based workflow |
| **[03-Video-Analysis](Examples/03-Video-Analysis/)** | Build a video analyzer with keyframe-anchored timestamps |

Start with Tutorial 01 to explore the API, then follow 02 or 03 for the full agent-based workflow.

---

## 🛠️ Tools Reference

| Tool | Purpose | Command |
|------|---------|---------|
| **cu-analyzer-run** | Run analysis or extract layout | `python tools/cu-analyzer-run/run.py` |
| **create_and_test** | Create + validate + test (all-in-one) | `python tools/cu-analyzer-run/create_and_test.py` |
| **cu-analyzer-validate** | Check schema before creating | `python tools/cu-analyzer-validate/cu_analyzer_validator.py` |
| **cu-results-export** | Convert results to CSV/Excel | `python tools/cu-results-export/export.py` |
| **cu-segment-visualizer** | Annotate PDFs with segments | `python tools/cu-segment-visualizer/visualize_segments.py` |
| **cu-visualize** | HTML field viewer | Open `tools/cu-visualize/cuDocVisualizer.html` |
| **pii-redact** | Redact PII from PDFs | `python tools/pii-redact/redact_pii.py` |
| **tpm-manager** | Check/set TPM quotas | `python tools/tpm-manager/tpm_manager.py` |
| **pdf-to-images** | Convert PDF to PNG images | `python tools/pdf-to-images/pdf_to_images.py` |

---
## 🧪 Running Tests

```bash
# Run all tests for cu-analyzer-run
cd tools/cu-analyzer-run && python -m pytest tests/ -v

# Run export tests
cd tools/cu-results-export && python -m pytest tests/ -v
```

---
## 📂 Repository Structure

```
CU-Tools/
├── Examples/                          # 📖 Hands-on tutorials
│   ├── 01-API-Testing/                # Explore REST API with .http files
│   ├── 02-Invoice-Extraction/         # Document analyzer tutorial
│   └── 03-Video-Analysis/             # Video analyzer tutorial
│
├── CU_API_Testing/                    # HTTP REST Client test files (also in Examples)
│   ├── CU-API-Testing-Guide.http      # Complete API testing guide
│   ├── CU-API-Testing-Preview2.http   # Preview API features
│   └── custom-analyzer-with-replace.http
│
├── tools/
│   ├── cu-analyzer-run/               # Core: run analysis & extract layout
│   │   ├── run.py                     # Run with existing analyzer or layout
│   │   ├── create_and_test.py         # Create + validate + test workflow
│   │   └── tests/                     # Unit tests
│   ├── cu-analyzer-validate/          # Validate schemas before creating
│   │   └── cu_analyzer_validator.py
│   ├── cu-client/                     # Shared API client library
│   │   └── content_understanding_client.py
│   ├── cu-results-export/             # Export JSON results to CSV/Excel
│   │   ├── export.py
│   │   └── tests/
│   ├── cu-segment-visualizer/         # Annotate PDFs with segmentation
│   │   └── visualize_segments.py
│   ├── cu-visualize/                  # HTML field visualizer
│   │   └── cuDocVisualizer.html
│   ├── pii-redact/                    # PII redaction using Azure AI Language
│   │   └── redact_pii.py
│   ├── tpm-manager/                   # TPM quota management
│   │   └── tpm_manager.py
│   └── pdf-to-images/                 # Convert PDF pages to PNG
│       └── pdf_to_images.py
│
├── .github/
│   ├── prompts/                       # AI prompts for Copilot
│   │   ├── generate-analyzer-schema.prompt.md
│   │   ├── evaluate-analyzer.prompt.md
│   │   └── ...
│   └── skills/                        # Complete workflow guides
│       ├── generate-analyzer.skill.md     ⭐ Schema creation
│       ├── eval-cu.skill.md               ⭐ Evaluation workflow
│       ├── generate-analyzer-video.skill.md
│       └── iterate-schema.skill.md
│
├── analyzer_templates/                # Example analyzer configurations
├── schemas/                           # Example extraction schemas
├── Agents.md                          # Technical reference (source of truth)
└── requirements.txt                   # Python dependencies
```

---


## 📚 Resources

- [Azure Content Understanding Documentation](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/)
- [Content Understanding Studio](https://aka.ms/cu-studio)
- [REST API Reference](https://learn.microsoft.com/en-us/rest/api/contentunderstanding/operation-groups)
- [Quickstart: Use REST API](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/quickstart/use-rest-api)
