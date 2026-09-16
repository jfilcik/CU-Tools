# Agentic contract obligation extraction

This example creates a single Content Understanding analyzer that extracts contract metadata, parties, and atomic obligations. Every obligation requires exact source quotations. Standalone offline reports evaluate mapped CUAD clause discovery, evidence, and returned usage; they do not measure complete atomic-obligation accuracy.

## Verified preview contract

| Setting | Value |
|---|---|
| Historical validation region | Southeast Asia |
| API version | `2026-06-01-preview` |
| Model | `gpt-5.2` |
| Agentic selector | `config.workflow: "Agentic"` |
| Input | One file per analysis request |

Use your own authorized Azure AI resource with access to the listed preview API
and model. No particular subscription, resource group, storage account, or
region is required by this example. Verify preview availability in your chosen
region before any paid analysis. Install and configure the official `cu`
executable using the repository README; do not copy another environment's
credentials. All CU service operations below use that executable.

The GA default remains `2025-11-01`; every analyzer command in this example passes the preview API explicitly.

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

Run one development contract first. Each example uses a new analyzer ID and
separates creation, analysis, and deletion:

```powershell
$selection = Get-Content dataset\selection_manifest.json -Raw | ConvertFrom-Json
$sample = ($selection.documents | Where-Object split -eq "development" | Select-Object -First 1).doc_id
$analyzer = "cuad_obligations_v1_" + [guid]::NewGuid().ToString("N")
$runDir = Join-Path "test_results\development" $analyzer

cu analyzer create --name $analyzer `
  --schema schemas\contract_obligations_agentic_v1.json `
  --api-version 2026-06-01-preview
if ($LASTEXITCODE -ne 0) { throw "Analyzer creation failed; do not analyze." }
try {
  cu analyze --file "samples\downloaded\$sample.txt" --analyzer $analyzer `
    --json --output-dir $runDir --report-file "$runDir\analyze-report.json" `
    --concurrency 1 --api-version 2026-06-01-preview --yes --on-existing error
  if ($LASTEXITCODE -ne 0) { Write-Warning "Analysis failed; inspect the saved status report." }
}
finally {
  cu analyzer delete $analyzer --api-version 2026-06-01-preview --yes
}
```

Agentic analysis can be expensive and slow. Historically, a short compatibility
contract completed in about 79 seconds and used approximately 36,000 tokens;
a long CUAD contract exceeded the former runner's 600-second timeout. The
official CLI has no `--timeout` option. Obtain cost approval before any corpus
batch or stability repetitions. Check deletion output and rerun that explicit
delete command if cleanup fails; never delete an analyzer from another run.

Prepare and run the deterministic 15-document clause-span benchmark:

```powershell
python scripts\prepare_clause_span_benchmark.py
if ($LASTEXITCODE -ne 0) { throw "Benchmark preparation failed; do not analyze." }
$analyzer = "cuad_spans_v1_" + [guid]::NewGuid().ToString("N")
$runDir = Join-Path "test_results\clause-span-15" $analyzer

cu analyzer create --name $analyzer `
  --schema schemas\cuad_clause_spans_agentic_v1.json `
  --api-version 2026-06-01-preview
if ($LASTEXITCODE -ne 0) { throw "Analyzer creation failed; do not analyze." }
try {
  cu analyze --source test_results\clause-span-15-input --recursive `
    --analyzer $analyzer --json --output-dir $runDir `
    --report-file "$runDir\analyze-report.json" --concurrency 1 `
    --api-version 2026-06-01-preview --yes --on-existing error
  if ($LASTEXITCODE -ne 0) { Write-Warning "Some analyses failed; include them in the offline report." }
}
finally {
  cu analyzer delete $analyzer --api-version 2026-06-01-preview --yes
}

python evaluation\generate_clause_span_report.py `
  --results $runDir --run-report "$runDir\analyze-report.json" `
  --output "$runDir\quality.md"
```

## Evaluate

The existing report scripts run locally using only the Python standard library.
They consume the official CLI's `cu-cli/analyze-report/v1` status report,
saved `--json` SDK results, and the generated CUAD selection/ground truth.
Use `--run-report` for the status report, or save it as `analyze-report.json`
inside the result directory. Previously saved CU-Tools `metadata.json` bundles
remain readable offline; no legacy runner or service client is needed.
They do not call Azure or require internal telemetry, special diagnostic
headers, or an evaluation service.
Analysis JSON validation and native-result normalization use the shared offline
`tools/cu-results-export/cu_result_io.py` loader. Malformed expected result files
stop reporting with an error; they are not silently skipped.

```powershell
# Broad obligations: score all held-out documents in the selection manifest.
python evaluation\generate_broad_quality_report.py `
  --results test_results\<held-out-run> `
  --run-report test_results\<held-out-run>\analyze-report.json `
  --output-prefix test_results\broad-quality\quality

# Category-specific exact spans: use the prepared benchmark selection.
python evaluation\generate_clause_span_report.py `
  --results test_results\clause-span-15\<run-id> `
  --run-report test_results\clause-span-15\<run-id>\analyze-report.json `
  --output test_results\clause-span-report\quality.md

# Offline regression tests; no service credentials required.
python -m pytest evaluation\tests `
  --basetemp test_results\pytest-offline -p no:cacheprovider
```

Both reports write Markdown, JSON, and CSV. Failed or missing analyses remain in
the quality denominator; an empty selection is an error. Broad-report
`Completion status: PASS` means every selected analysis completed, not that
quality passed. Report model and region come from run metadata when recorded,
otherwise they are explicitly unknown. Failed, skipped, and missing outputs
are never treated as successful evaluation.

Native CLI status reports do not contain per-document latency, run timestamps,
model/region, or structured usage totals. Missing measurements remain `null` in
JSON, blank in CSV, and `not recorded` in Markdown—not zero. CLI `--usage` and
`--time` print separately to stderr; these reporters do not parse that console
output or invent missing measurements. Keep raw results and the original status
report together, and do not overwrite results from a previous run.

The former **EvalLens integration has been removed** because it depended on a
non-public repository/package. Its configuration, dataset builder, evaluator
plugins, runner, and seven-component weighted accuracy report are no longer
available. The retained reports do **not** score atomic party roles,
completeness, duplicate control, or a weighted atomic-obligation total.
`ground_truth/annotation_guidelines.md` and the six-contract annotation selection
remain useful for manual review; skipped or unverified atomic evaluation must
not be reported as passing.

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
- `scripts/` - safe public-data downloaders, deterministic selectors, and local grounding viewer
- `evaluation/` - pure CU normalization, matching helpers, standalone quality reports, and offline tests
- `samples/`, `test_results/` - generated local artifacts
- `reports/` - reviewed historical measurements; keep new reports under ignored `test_results/`

See `IMPLEMENTATION_GUIDE.md` for the transferable end-to-end design.
