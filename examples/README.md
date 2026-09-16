# Examples

Public tutorials for turning reproductions into evidence-based Content
Understanding analyzer improvements, with quality and cost evaluated at each
iteration toward safe straight-through processing.

**Start a new case:** copy [_TEMPLATE](_TEMPLATE/) and follow the
[canonical v1 workspace guide](../docs/iteration-workspaces.md). Keep customer
data in a private workspace outside this library. Manual copying works; a
customer repository or issue browser is optional.

| Tutorial | What You'll Learn | Time |
|----------|-------------------|------|
| [01-API-Testing](01-API-Testing/) | Explore the CU REST API with HTTP test files in VS Code | 10 min |
| [02-Invoice-Extraction](02-Invoice-Extraction/) | Build a document analyzer using the agent-based workflow | 15 min |
| [03-Video-Analysis](03-Video-Analysis/) | Build a video analyzer with keyframe-anchored timestamps | 15 min |
| [05-Agentic-Contract-Obligations](05-Agentic-Contract-Obligations/) | Extract quote-grounded atomic obligations with the agentic preview API and evaluate against CUAD | 30+ min |
| [06-Contract-Obligation-Golden-Set](06-Contract-Obligation-Golden-Set/) | Compare Standard and Agentic extraction against reviewed atomic obligations | See tutorial |

## Recipes

Focused, self-contained fixes for specific problems:

| Recipe | Problem it solves |
|--------|-------------------|
| [fillable-form-annot-ocr-fix](04-fillable-form-annot-ocr-fix/) | Fillable-form (`/Annot` widget) values getting OCR-misread — flatten them into the content stream so CU reads them as digital text |

## Prerequisites

Live CU operations require a configured resource and credentials; see the
[root Quick Start](../README.md#-quick-start). Copying the template and
reviewing local evidence require no API calls.

For execution:
- Use the official `cu` executable for routine operations (Python 3.10+).
- Advanced runner-based tutorials additionally require CU-Tools dependencies
  and their `AZURE_AI_*` configuration. The runners load the root `.env`;
  official `cu` uses `CU_*`/saved config and does not load that file.
- **GitHub Copilot** (recommended — the tutorials walk through the agent-assisted workflow)
- Obtain explicit cost approval for paid scale/stability work.

## Folder Structure

New cases use numbered experiments:

```text
case/
├── manifest.json
├── README.md
├── inputs/documents/             # Or an existing immutable samples/ corpus
└── iterations/001/
    ├── manifest.json
    ├── inputs/schemas/
    ├── outputs/raw/
    ├── outputs/evaluation/
    └── report.md
```

Each manifest links the inputs, hypothesis, evidence, report, decision, and
cost. New hypotheses/configurations/datasets/metrics get new numbers; repeated
trials (`--iterations N`) stay within an experiment. Global fill/confidence is
not STP evidence; record correctness, holdout scope, false accepts, and review.

**Compatibility:** existing tutorials may retain `samples/`, `schemas/`,
`layout_results/`, `test_results/`, and `reports/`. Do not move their evidence.
[Invoice iteration 001](02-Invoice-Extraction/iterations/001/manifest.json)
adds navigation to existing public sample/schema inputs only: it is **planned,
not run**, with no claimed results or cost measurement.
