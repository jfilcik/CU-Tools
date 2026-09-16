
> **Note:** This repository includes AI-generated experimental tooling and workflows. Expect rapid iteration and breaking changes. See `.github/copilot-instructions.md` and `Agents.md` for Copilot agent behavior and workflow details.

# CU-Tools

A toolkit for turning customer reproductions into evidence-based Azure AI
Content Understanding analyzer improvements — evaluating quality and cost at
each iteration, toward safe straight-through processing.

**Start with the official [CU CLI](https://github.com/Azure/content-understanding-toolkit/tree/main/cu-cli).**
Use `cu` directly for routine CU operations. Add CU-Tools for repeated testing,
usage diagnostics, evaluation, and CSV/Excel reports. You do not need to clone
this repository just to use CU.

## From reproduction to a supported decision

1. **Describe the problem:** expected versus actual behavior, impact, defects,
   and measurable goals.
2. **Establish a baseline:** freeze document/schema inputs and version the
   evaluator, reviewed truth, and acceptance criteria.
3. **Run numbered experiments:** `001`, `002`, ... each preserve a hypothesis,
   exact execution details, raw output, derived evaluation, and report links.
4. **Account for every iteration's cost:** distinguish estimated from measured
   charges; missing cost stays unknown, never zero.
5. **Promote only with evidence:** compare correctness, regressions, review
   rate, false accepts, holdout coverage, latency, and cost. Field fill and
   confidence alone do not demonstrate straight-through processing.

Start from [examples/_TEMPLATE](examples/_TEMPLATE/) and the
[canonical v1 iteration-workspace guide](docs/iteration-workspaces.md).
Each case has a root `manifest.json`; every numbered iteration has its own
manifest, schema/input snapshots or immutable input references, raw output,
evaluation, and `report.md`. Repeated trials (`--iterations 10`) belong inside
one experiment, not ten numbered iterations.

**Public library, private cases:** keep reusable examples and generic tools
here; keep customer repros/data in a restricted workspace outside public
CU-Tools. The template can be copied manually without a customer repository
or browser. Existing examples and legacy run bundles remain usable; do not
move or overwrite their evidence when adding iteration navigation.

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
- **Python 3.10+** (required by the official CLI)
- **Azure CLI** (`az`) for Entra ID sign-in; alternatively use an API key
- **VS Code** with REST Client extension only if using `.http` files

### Install or update the official CU CLI

Use a virtual environment to avoid conflicts with system Python. In
**PowerShell**, starting in a directory of your choice:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade --pre cu-cli
cu --version
cu --help
```

On macOS/Linux, activate with `source .venv/bin/activate` instead. On macOS,
use `cu-cli` in place of `cu` to avoid the built-in UUCP command.
If PowerShell activation is blocked, use `.\.venv\Scripts\python.exe` and
`.\.venv\Scripts\cu.exe` directly; no execution-policy change is needed.

**Updates:** rerun `python -m pip install --upgrade --pre cu-cli` in the same
environment. As of September 15, 2026, PyPI's latest release is `0.1.0b3`;
`--pre` opts into preview releases, including newer betas. For stable-only
updates once stable releases are available, omit `--pre`.
`cu upgrade --check` checks PyPI without installing; `cu upgrade` offers an
interactive upgrade, but use the explicit pip command for the preview channel.

No toolkit source checkout or CU-Tools dependencies are needed for this path.
For reproducible automation, pin a tested version instead of upgrading on
every run.

<details>
<summary>Developer option: use the local toolkit checkout instead of PyPI</summary>

For the checkout at `C:\src\cu-cli` (the package is in its `cu-cli` subdirectory):

```powershell
python -m pip install -e C:\src\cu-cli\cu-cli
cu --version

# Update deliberately; --ff-only will not merge diverged branches
git -C C:\src\cu-cli pull --ff-only
python -m pip install -e C:\src\cu-cli\cu-cli
```

An editable installation follows that checkout, not the latest PyPI release.
Do not use `cu upgrade` to update the checkout. To switch back to PyPI, use
a fresh virtual environment and the release-install command above.

</details>

### Configure an existing CU resource

Entra ID avoids putting API keys in command history:

```powershell
az login
cu config set endpoint https://YOUR-RESOURCE.services.ai.azure.com/
cu config set auth entra
cu config set api_version 2025-11-01
cu doctor
```

Your identity must have access to the resource. For API-key authentication,
provide `CU_ENDPOINT` and `CU_API_KEY` through your shell or secret manager.
Do not pass secrets as `--api-key` arguments or commit them to files.
Environment variables override saved configuration; clear stale
`CU_API_KEY`/`CU_AUTH_MODE` values when switching to Entra ID.

`cu doctor` checks an existing setup; it does not provision resources or deploy
models. For a new resource, follow the
[official setup guide](https://github.com/Azure/content-understanding-toolkit/blob/main/cu-cli/README.md#2-setup).

### Add CU-Tools for advanced workflows

Clone this repository only when you need its testing and reporting tools.
Keep using your activated environment:

```powershell
git clone https://github.com/jfilcik/CU-Tools.git
Set-Location CU-Tools
python -m pip install -r requirements.txt
Copy-Item .env.sample .env
# Edit .env locally with AZURE_AI_ENDPOINT and AZURE_AI_API_KEY
```

The official CLI uses `CU_*` environment variables or its saved config.
Existing Python runners load the repository `.env` and use
`AZURE_AI_ENDPOINT` / `AZURE_AI_API_KEY`; they do not read `cu config`.
Conversely, `cu` does not automatically load this repository's `.env`.
Both support `CU_API_VERSION`. If the legacy variables are already in your
shell, reuse them without copying keys into commands:

```powershell
$env:CU_ENDPOINT = $env:AZURE_AI_ENDPOINT
$env:CU_API_KEY = $env:AZURE_AI_API_KEY
```

Installing `requirements.txt` does not install or upgrade the official CLI.
Keep its installation explicit so users can choose release or source.

---


## Choose the simplest tool

| Task | Use |
|------|-----|
| Check connectivity, inspect/create/delete an analyzer, update model defaults | Official `cu` |
| Extract layout, analyze a file, or process a folder concurrently | Official `cu analyze` |
| Repeat a document N times, capture CU diagnostics, or preserve CU-Tools run metadata/results | `tools/cu-analyzer-run/run.py` |
| Validate + create + test + clean up, or orchestrate classify-and-route dependencies | `tools/cu-analyzer-run/create_and_test.py` |
| Evaluate results, export CSV/Excel, inspect costs or prompt-cache telemetry | CU-Tools reporting/evaluation tools |

### 1. Routine operations: call `cu` directly

Run from the repository root (or outside the repo), not from `tools/cu-cli`:

```powershell
cu doctor
cu analyzer list
cu analyzer show prebuilt-layout

# Local validation and creation; use your own schema file
cu analyzer validate .\schemas\my_analyzer_v1.json --api-version 2025-11-01
cu analyzer create --id my_analyzer_v1 --schema .\schemas\my_analyzer_v1.json --api-version 2025-11-01

# Layout from a checked-in sample; custom field extraction
cu analyze .\examples\02-Invoice-Extraction\samples\invoice.pdf --analyzer prebuilt-layout --out .\layout
cu analyze .\examples\02-Invoice-Extraction\samples\invoice.pdf --analyzer my_analyzer_v1 --output json --out .\cli_results

# Ordinary batches do not require run.py
cu analyze .\samples --analyzer my_analyzer_v1 --output json --out .\cli_results --concurrency 3 --skip-existing

# Inspect resource-wide defaults; apply only the mapping requested
cu defaults get
cu defaults set --no-from-config --model gpt-4.1=YOUR-EXISTING-DEPLOYMENT

# Destructive: run only when you intend to remove this analyzer
cu analyzer delete my_analyzer_v1
```

These are examples, not a script to run wholesale. Analysis incurs CU charges.
`--skip-existing` preserves outputs; `--force` re-analyzes and bills again.
Defaults affect the entire resource; avoid `--replace` unless replacing the
whole mapping is intentional.

**Analyzer updates:** CU does not support in-place replacement. Prefer
creating `my_analyzer_v2`, testing it, and updating consumers. Only delete and
recreate the same ID when explicitly intended; that causes an availability gap.
Custom IDs use letters, digits, and underscores, not hyphens.

**Output compatibility:** CLI `*.result.json` / `*.result.md` outputs are not
the CU-Tools run bundle (`metadata.json`, result envelope, usage summaries).
Keep `run.py` when downstream evaluation/export depends on that bundle or on
diagnostic headers. The installed CLI currently supports local files, not URL
inputs; do not assume every legacy wrapper option exists in `cu`.

### 2. Advanced workflows and Copilot assistance

Use the built-in Copilot skills for guided, eval-driven workflows. Use `cu`
for simple individual operations, while keeping the Python runners when the
workflow needs their orchestration or result format.

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

```powershell
# Repeated testing with diagnostic infos and CU-Tools results
python tools\cu-analyzer-run\run.py --analyzer-id my_analyzer_v1 --input .\samples\invoice.pdf --output .\test_results --iterations 10 --max-workers 3 --diagnostics

# CU-Tools-specific schema quality checks
python tools\cu-analyzer-validate\cu_analyzer_validator.py .\schemas\my_schema.json

# Create analyzer and test
python tools\cu-analyzer-run\create_and_test.py --schema .\schemas\my_schema.json --input .\samples --output .\test_results\v2

# Export the runner's results to CSV
python tools\cu-results-export\export.py --input .\test_results\v2 --output .\results.csv

# Estimate cost from actual CU usage
python tools\cu-cost-estimator\cu_cost_estimator.py estimate-usage --cu-output .\test_results\sample.json --model gpt-4.1-mini
```

---

### 3. HTTP REST Client (optional exploration)

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
| **[05-Agentic-Contract-Obligations](examples/05-Agentic-Contract-Obligations/)** | Build and evaluate a quote-grounded agentic contract analyzer with the preview API |
| **[06-Contract-Obligation-Golden-Set](examples/06-Contract-Obligation-Golden-Set/)** | Compare Standard and Agentic obligation extraction against ten reviewed short contracts |

Start with Tutorial 01 to explore the API, then follow 02 or 03 for the full agent-based workflow.

---

## 🛠️ Tools Reference

| Tool | Purpose | Command |
|------|---------|---------|
| **[Official CU CLI](https://github.com/Azure/content-understanding-toolkit/tree/main/cu-cli)** | Default for routine CU operations and ordinary batches | `cu --help` |
| **cu-analyzer-run** | Advanced testing, diagnostics, and CU-Tools result bundles | `python tools/cu-analyzer-run/run.py` |
| **create_and_test** | Create + validate + test (all-in-one) | `python tools/cu-analyzer-run/create_and_test.py` |
| **[Local compatibility layer](tools/cu-cli/README.md)** | Internal legacy operations used by runners; not the official CLI | Used by existing scripts; no separate install |
| **cu-analyzer-validate** | Check schema before creating | `python tools/cu-analyzer-validate/cu_analyzer_validator.py` |
| **cu-results-export** | Convert results to CSV/Excel | `python tools/cu-results-export/export.py` |
| **cu-cost-estimator** | Estimate and summarize CU processing costs | `python tools/cu-cost-estimator/cu_cost_estimator.py` |
| **[cu-prompt-cache](tools/cu-prompt-cache/README.md)** | Correlate model telemetry and measure token-weighted cache reuse | `python tools/cu-prompt-cache/prompt_cache.py` |
| **cu-segment-visualizer** | Annotate PDFs with segments | `python tools/cu-segment-visualizer/visualize_segments.py` |
| **cu-visualize** | HTML field viewer | Open `tools/cu-visualize/cuDocVisualizer.html` |
| **pii-redact** | Redact PII from PDFs | `python tools/pii-redact/redact_pii.py` |
| **tpm-manager** | Check/set TPM quotas | `python tools/tpm-manager/tpm_manager.py` |
| **pdf-to-images** | Convert PDF to PNG images | `python tools/pdf-to-images/pdf_to_images.py` |

---
## 🧪 Running Tests

Run from the repository root. These commands exclude the compatibility layer's
live smoke tests:

```powershell
# Run all tests for cu-analyzer-run
python -m pytest tools\cu-analyzer-run\tests -v

# Run the local compatibility layer's unit tests
python -m pytest tools\cu-cli\tests -m "not integration" -v

# Run export tests
python -m pytest tools\cu-results-export\tests -v

# Run cost-estimator tests
python -m pytest tools\cu-cost-estimator\tests -v
```

See the [compatibility-layer guide](tools/cu-cli/README.md#tests) for explicit,
billable live smoke tests. Those test the legacy runner backend, not the
official CLI.

---
## 📂 Repository Structure

```
CU-Tools/
├── examples/                          # Public tutorials; no customer data
│   ├── _TEMPLATE/                    # Case + numbered-iteration manifests
│   ├── 01-API-Testing/                # Explore REST API with .http files
│   ├── 02-Invoice-Extraction/         # Document analyzer tutorial
│   ├── 03-Video-Analysis/             # Video analyzer tutorial
│   ├── 05-Agentic-Contract-Obligations/
│   └── 06-Contract-Obligation-Golden-Set/
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
│   ├── cu-cli/                        # Compatibility layer, NOT official cu-cli
│   │   ├── cu_cli/operations.py       # create/analyze/classify/delete + poll
│   │   ├── cu_cli/cli.py              # Legacy entry point, not for new use
│   │   └── tests/
│   ├── cu-results-export/             # Export JSON results to CSV/Excel
│   │   ├── export.py
│   │   └── tests/
│   ├── cu-cost-estimator/             # Estimate costs from schemas or actual usage
│   │   ├── cu_cost_estimator.py
│   │   ├── generate_cost_summary.py
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
├── docs/iteration-workspaces.md       # Canonical v1 workspace contract
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
