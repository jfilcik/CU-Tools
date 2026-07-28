# Agentic contract obligation extraction

This example creates a single Content Understanding analyzer that extracts contract metadata, parties, and atomic obligations. Every obligation requires exact source quotations and is evaluated with deterministic metrics.

## Verified preview contract

| Setting | Value |
|---|---|
| Region | Southeast Asia |
| API version | `2026-06-01-preview` |
| Model | `gpt-5.2` |
| Agentic selector | `config.workflow: "Agentic"` |
| Input | One file per analysis request |

The GA default remains `2025-11-01`; every command in this example passes the preview API explicitly.

Two versioned schemas are available:

- `contract_obligations_agentic_v1.json` discovers broad atomic obligations.
- `cuad_clause_spans_agentic_v1.json` extracts exact spans for the 31 mapped
  CUAD categories and aligns directly with official CUAD ground truth.

## Quick start

```powershell
cd examples\05-Agentic-Contract-Obligations
python scripts\download_cuad.py
python scripts\prepare_cuad_eval.py
# Optional: prepare the same held-out selection as original PDFs.
python scripts\download_cuad_pdfs.py

python ..\..\tools\cu-analyzer-validate\cu_analyzer_validator.py `
  schemas\contract_obligations_agentic_v1.json `
  --api-version 2026-06-01-preview
```

Run one development contract first:

```powershell
python ..\..\tools\cu-analyzer-run\create_and_test.py `
  --schema schemas\contract_obligations_agentic_v1.json `
  --input samples\downloaded\<one-contract>.txt `
  --output test_results\development\<contract-id> `
  --api-version 2026-06-01-preview `
  --timeout 600
```

Agentic analysis can be expensive and slow. A short compatibility contract completed in about 79 seconds and used approximately 36,000 tokens during validation; a long CUAD contract exceeded a 600-second timeout. Obtain cost approval before running all 20 held-out contracts or stability repetitions.

Prepare and run the deterministic 15-document clause-span benchmark:

```powershell
python scripts\prepare_clause_span_benchmark.py
python ..\..\tools\cu-analyzer-run\create_and_test.py `
  --schema schemas\cuad_clause_spans_agentic_v1.json `
  --input test_results\clause-span-15-input `
  --output test_results\clause-span-15 `
  --api-version 2026-06-01-preview `
  --timeout 1800 `
  --max-workers 1

python evaluation\generate_clause_span_report.py `
  --results test_results\clause-span-15
```

## Evaluate

Manually verify the six atomic annotation documents listed in `dataset/selection_manifest.json`, then build and run:

```powershell
python scripts\build_evallens_dataset.py --results test_results\development
$env:PYTHONPATH = "C:\src\EvalLens"
cd evaluation
python -m evallens validate --config config.yml
python -m evallens run --run-id contract_obligations_v1 --config config.yml
python generate_accuracy_report.py --input output\local_results\contract_obligations_v1\<result.json>
```

The weighted score is: discovery 30%; type 15%; party roles 20%; quote groundedness 10%; quote alignment 15%; completeness 5%; duplicate control 5%.

## Broad preview result

The first 20-contract held-out run is documented in
[`reports/heldout_20_quality.md`](reports/heldout_20_quality.md). It is a
fail-closed assessment of API latency, reliability, token usage, clause
discovery, taxonomy accuracy, and evidence grounding. No additional API runs
should be started from that result without first addressing the report's quota,
transport-timeout, segmentation, and scope recommendations.

[`reports/heldout_20_successes.md`](reports/heldout_20_successes.md) isolates
the three completed contracts. It documents strong evidence grounding but poor
survivor-only discovery, explains why the three-worker run still took 17.33
hours, and records the original-PDF follow-up dataset.

[`reports/pdf_5_quality.md`](reports/pdf_5_quality.md) evaluates five original
CUAD PDFs. Four completed, but fail-closed clause F1 remained 14.8%; the paired
text/PDF results did not show a consistent format advantage.

## Local grounding viewer

Build an ignored, local-only HTML viewer that renders the source PDFs and
highlights each obligation's exact evidence using native CU word polygons:

```powershell
python scripts\build_grounding_viewer.py `
  --pdf-dir test_results\pdf-5-input `
  --result-dir test_results\pdf-5-final `
  --output test_results\grounding-viewer

Start-Process test_results\grounding-viewer\index.html
```

Repeat `--pdf-dir` and `--result-dir` to include additional local runs. The
viewer copies source PDFs and rendered pages into its output directory, so keep
the output beneath ignored `test_results/` when contracts are not intended for
source control.

## Folder map

- `schemas/` - versioned agentic analyzer
- `dataset/` - pinned CUAD checksum, mapping, and generated selection manifest
- `ground_truth/` - annotation contract and locally generated gold JSONL
- `scripts/` - safe downloader, deterministic selector, and EvalLens dataset builder
- `evaluation/` - canonical preprocessor, seven deterministic evaluators, tests, and report generator
- `samples/`, `test_results/`, `reports/` - generated local artifacts

See `IMPLEMENTATION_GUIDE.md` for the transferable end-to-end design.
