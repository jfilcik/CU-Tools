# Examples

Hands-on tutorials for Azure Content Understanding — from raw API exploration to AI-assisted analyzer development.

| Tutorial | What You'll Learn | Time |
|----------|-------------------|------|
| [01-API-Testing](01-API-Testing/) | Explore the CU REST API with HTTP test files in VS Code | 10 min |
| [02-Invoice-Extraction](02-Invoice-Extraction/) | Build a document analyzer using the agent-based workflow | 15 min |
| [03-Video-Analysis](03-Video-Analysis/) | Build a video analyzer with keyframe-anchored timestamps | 15 min |

## Recipes

Focused, self-contained fixes for specific problems:

| Recipe | Problem it solves |
|--------|-------------------|
| [fillable-form-annot-ocr-fix](04-fillable-form-annot-ocr-fix/) | Fillable-form (`/Annot` widget) values getting OCR-misread — flatten them into the content stream so CU reads them as digital text |

## Prerequisites

All tutorials require:
- **Azure AI Foundry** with Content Understanding enabled ([Setup Guide](../docs/create_azure_ai_service.md))
- A configured `.env` file (copy from `.env.sample` at repo root)

Tutorials 02 and 03 additionally require:
- **Python 3.9+** with dependencies installed (`pip install -r requirements.txt`)
- **GitHub Copilot** (recommended — the tutorials walk through the agent-assisted workflow)

## Folder Structure

Each Python tutorial follows the same project structure:

```
ExampleName/
├── README.md           # Tutorial walkthrough
├── samples/            # Source documents or videos
├── schemas/            # Analyzer schemas (versioned)
├── layout_results/     # Layout extraction output (documents only)
├── test_results/       # Analysis results by run
└── reports/            # Summary reports and exports
```

This matches the project template pattern used for production work. See the `generate-analyzer` skill (`.github/skills/generate-analyzer.skill.md`) for the full workflow reference.
