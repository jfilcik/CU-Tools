---
name: generate-analyzer
description: Creates and iterates Azure AI Content Understanding analyzer schemas for single document types using layout analysis, schema generation, validation, and test execution. Use when users ask to create, improve, validate, or test a CU analyzer for one document type, run layout extraction, or compare schema versions.
---

# Skill: Generate Analyzer

## Quick Start
Use this workflow for a single document type.
1. Gather 3-5 representative samples in one folder.
2. Run layout extraction.
3. Define fields and generate schema v1.
4. Validate schema.
5. Create analyzer and test.
6. Export results and iterate to v2 if needed.

If the request uses a preview API feature or agentic mode, load
`cu-preview-api.skill.md` first and pass its API version explicitly to validation,
creation, analysis, and evaluation commands. Never change the GA default globally.
Core commands:
python tools/cu-analyzer-run/run.py --layout --input {sample_folder} --output {project_folder}/layout_results
python tools/cu-analyzer-validate/cu_analyzer_validator.py {project_folder}/schemas/{name}_v1.json
python tools/cu-analyzer-run/create_and_test.py --schema {project_folder}/schemas/{name}_v1.json --input {sample_folder} --output {project_folder}/test_results/v1
python tools/cu-results-export/export.py --input {project_folder}/test_results/v1 --output {project_folder}/test_results/v1/results.csv

## Workflow
### 1) Gather Inputs
Checklist:
- Confirm this is a single-type workflow. If packets contain multiple document types, use generate-analyzer-classify-route.skill.md.
- Collect 3-5 files covering normal and edge-case layouts.
- Confirm environment variables are set: AZURE_AI_ENDPOINT and AZURE_AI_API_KEY.

### 2) Run Layout Analysis
Command:
python tools/cu-analyzer-run/run.py --layout --input {sample_folder} --output {project_folder}/layout_results
Review each .layout.md for labels, section anchors, and repeated patterns.

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
python tools/cu-analyzer-validate/cu_analyzer_validator.py {project_folder}/schemas/{name}_v1.json
Fix all errors before creating the analyzer.

For a preview schema, append `--api-version {preview_api_version}`. Preview-only
properties must fail validation unless the matching API contract is explicit.

### 5) Create and Test
python tools/cu-analyzer-run/create_and_test.py --schema {project_folder}/schemas/{name}_v1.json --input {sample_folder} --output {project_folder}/test_results/v1
Optional: add --keep-analyzer when you need to reuse the analyzer ID.

For agentic preview analyzers, process one input file per request, append
`--api-version 2026-06-01-preview`, start with a short compatibility sample, and
use the preview skill's cost and timeout gate before running a corpus.

### 6) Export and Evaluate
python tools/cu-results-export/export.py --input {project_folder}/test_results/v1 --output {project_folder}/test_results/v1/results.csv
Evaluate:
- Fill rate for key fields
- Confidence levels
- Common misses by field

### 7) Iterate to v2+
When quality is low:
- Tighten field descriptions with better labels and disambiguation.
- Add format examples.
- Retest with v2 schema and compare CSV output to v1.

## Output Structure
Issues/{project}/
- samples/
- layout_results/
- schemas/{name}_v1.json
- test_results/v1/
- reports/

## Success Criteria
- Layout extraction completed on representative samples.
- Schema validates cleanly.
- Analyzer test run completes successfully.
- Key fields trend toward usable quality (target: >80% fill for critical fields).
- Results exported for review and iteration decisions.

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
