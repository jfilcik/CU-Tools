---
name: generate-analyzer
description: Creates and iterates Azure AI Content Understanding analyzer schemas for single document types using layout analysis, schema generation, validation, and test execution. Use when users ask to create, improve, validate, or test a CU analyzer for one document type, run layout extraction, or compare schema versions.
---

# Skill: Generate Analyzer

## Quick Start
Use this workflow for a single document type.
1. Select a case and numbered iteration; freeze 3-5 representative samples.
2. Run layout extraction.
3. Define fields and generate schema v1.
4. Validate schema.
5. Create analyzer and test.
6. Evaluate correctness and cost, report evidence, and start a new iteration if needed.

## Workspace first

Use [the v1 workspace guide](../../docs/iteration-workspaces.md) and
[generic template](../../examples/_TEMPLATE/). Keep customer work private.
`{case_folder}` is the selected case; `{iteration_folder}` is its
`iterations/001` (or next number), not a new shared results folder. Record the
hypothesis, defects, baseline, input inventory/hashes, and evaluator/truth
versions before execution. Preserve old evidence; new
hypothesis/configuration/dataset/metric changes get a new number.
Link verified product bugs in the root and relevant iteration `bugs` arrays,
separately from local defects; follow [tracking bugs](../../docs/iteration-workspaces.md#tracking-bugs).

Use official `cu` for routine calls. Keep `create_and_test.py` below for the
integrated lifecycle and compatible run bundle; it still uses the legacy REST
backend. See `Agents.md` CLI-first routing for separate CLI/runner credentials.

If the request uses a preview API feature or agentic mode, load
`cu-preview-api.skill.md` first and pass its API version explicitly to validation,
creation, analysis, and evaluation commands. Never change the GA default globally.
Core command templates (substitute real paths):
```powershell
cu analyze "{sample_folder}" --analyzer prebuilt-layout --out "{iteration_folder}\outputs\raw\layout"
python tools\cu-analyzer-validate\cu_analyzer_validator.py "{iteration_folder}\inputs\schemas\{name}_v1.json"
python tools\cu-analyzer-run\create_and_test.py --schema "{iteration_folder}\inputs\schemas\{name}_v1.json" --input "{sample_folder}" --output "{iteration_folder}\outputs\raw\analysis"
python tools\cu-results-export\export.py --input "{iteration_folder}\outputs\raw\analysis" --output "{iteration_folder}\outputs\evaluation\results.csv"
```

## Workflow
### 1) Gather Inputs
Checklist:
- Confirm this is a single-type workflow. If packets contain multiple document types, use generate-analyzer-classify-route.skill.md.
- Collect 3-5 files covering normal and edge-case layouts.
- Inventory/hash selected files from immutable case inputs or existing samples.
- Confirm the CLI and runner target the same intended resource; use `CU_*`
  or saved config for `cu`, `AZURE_AI_*` for the runners.

### 2) Run Layout Analysis
Use the `cu analyze` layout command above. Review its markdown/JSON for labels,
section anchors, and repeated patterns. Use `run.py --layout` only when
downstream tools require its `.layout.md`/CU-Tools bundle, with output still
under `{iteration_folder}/outputs/raw/layout`. Do not rename CLI output to
pretend it is a runner bundle.

### 3) Define Fields and Draft Schema
For each field, specify:
- Name (PascalCase)
- Type (string, number, boolean, array, object)
- Method (extract, generate, classify)
- Description with text-based anchors and alternate labels
Critical rule: CU is two-stage. Describe text and structure, not visual styling.

> **🎬 Video analyzers**: For video analysis with timestamps, use the dedicated
> `generate-analyzer-video.skill.md` skill instead. Video schemas require specific patterns
> (string timestamps in `hh:mm:ss.ms`, keyframe anchoring) that differ from document schemas.

> ⚠️ **Edge-case flag:** `enableSegmentation` and related config options are **not** supported in
> GA API 2025-11-01. If you need video segmentation, see **Edge Cases & Workarounds** at the end of this skill.

### 4) Validate Schema Before Creation
Run the local quality validator above against the iteration-local schema
snapshot (routine CLI validation is also available via `cu analyzer validate`).
Fix all errors before creating the analyzer.

For a preview schema, append `--api-version {preview_api_version}`. Preview-only
properties must fail validation unless the matching API contract is explicit.

### 5) Create and Test
Run the integrated `create_and_test.py` command above against the frozen
schema and selected inputs, after any required cost approval.
Optional: add --keep-analyzer when you need to reuse the analyzer ID.

For agentic preview analyzers, process one input file per request, append
`--api-version 2026-06-01-preview`, start with a short compatibility sample, and
use the preview skill's cost and timeout gate before running a corpus.

### 6) Export and Evaluate
Use the export command above, keeping derived artifacts out of `outputs/raw/`.
Evaluate:
- Correctness against reviewed truth, with denominators and source links
- Fill rate for key fields
- Confidence levels
- Common misses by field
- Failures/retries, latency, usage, and cost for this iteration

Update `manifest.json` and `report.md` with the sanitized command, versions,
run identifiers, evidence links, comparison, limitations, cost basis/status,
and decision. Missing cost is unknown/null, not zero. Fill/confidence alone
cannot establish STP; apply the case-level acceptance/holdout/review gates in
the workspace guide. Synchronize the root iteration index.

### 7) Iterate to v2+
When quality is low:
- Tighten field descriptions with better labels and disambiguation.
- Add format examples.
- Create the next numbered experiment, snapshot v2 there, link the baseline,
  retest on the controlled corpus, and compare with v1 without overwriting it.

## Output Structure
```text
{case_folder}/
├── manifest.json
├── README.md
├── inputs/documents/             # Or existing immutable samples/
└── iterations/001/
    ├── manifest.json
    ├── inputs/schemas/
    ├── outputs/raw/              # Layout and analysis subdirectories
    ├── outputs/evaluation/
    └── report.md
```

## Success Criteria
- Layout extraction completed on representative samples.
- Schema validates cleanly.
- Analyzer test run completes successfully.
- Critical-field correctness meets the predeclared gate; fill is diagnostic.
- Results/cost are recorded with evidence and limits, not assumed.
- Report and manifests support the iteration decision; raw evidence is immutable.

## Edge Cases & Workarounds

Consult this section only when the inline flags above apply. The happy path covers standard single-type document analyzers.

### Video segmentation (GA API 2025-11-01)
The config options `enableSegmentation`, `segmentationMode`, and `segmentationDefinition` are
**NOT supported** in the GA API (2025-11-01). For video segmentation, use `contentCategories`
with `enableSegment: true` — the same classify-and-route pattern used for documents.
See `generate-analyzer-classify-route.skill.md` and `Agents.md` section 4.7 for details.

## Related Resources
- Video analyzer with timestamps: generate-analyzer-video.skill.md
- Advanced mixed-packet routing: generate-analyzer-classify-route.skill.md
- Prompt support: .github/prompts/analyze-document-structure.prompt.md
- Prompt support: .github/prompts/generate-analyzer-schema.prompt.md
- Technical rules: Agents.md section 4.5 and section 4.6
- Preview and agentic API workflow: cu-preview-api.skill.md
