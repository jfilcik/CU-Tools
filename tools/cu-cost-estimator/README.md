# Offline CU cost estimation

These tools estimate costs from **explicit measured usage** or an
**explicit schema/volume scenario**. They make no service calls and require
only the Python standard library. All amounts are estimates using bundled
illustrative prices, **not actual spend or a current Azure billing quote**.
Check current model, deployment, region and contract rates before planning.

## Official CLI capture

Install/configure the official CLI using the [root README](../../README.md).
Capture analysis results with:

```powershell
cu analyze --source samples --analyzer ID --json --output-dir results --report-file batch-report.json --yes
```

The ordinary CLI result is native SDK analysis JSON, saved as
`<input filename including extension>.result.json` under the source-relative
path. Native output may have root `contents` or an LRO envelope with root
`id`, `status`, `result`, and `usage`, with `result.contents`. Both are native
formats; the envelope does not imply legacy output. The separate CLI report is
**status metadata**, not an analysis document.

**Public `cu-cli` 0.1.0b1 limitation:** `--usage` prints service usage separately
to stderr; native result/report JSON does not necessarily contain usage or
per-file timings. These tools do not parse undocumented human-readable
`LLMStats`/console telemetry, estimate tokens from extracted text, or make
another service request. Missing usage means unknown cost, not zero.

## Directory/experiment coverage

```powershell
python tools\cu-cost-estimator\generate_cost_summary.py results --json --output costs.json
python tools\cu-cost-estimator\generate_cost_summary.py experiment --model gpt-4.1 --output costs.txt
```

The shared offline loader in
[`cu-results-export`](../cu-results-export/README.md#offline-loader-contract)
recursively reads native results and already saved CU-Tools result envelopes,
once per file. It keeps analyzer/trial-relative paths, including repeated
basenames. Reports, manifests, schemas, comparisons, and generated summaries
are excluded, including experiment `run.json` execution state and per-batch
`native-report.json`. Explicit metadata inputs and malformed result files fail rather
than silently disappearing.

JSON output includes:

- `batch_summary.total_documents`: **all discovered analysis result files**,
  including empty/failed files and files without usage.
- Recorded succeeded/failed/unknown-status counts; no success is inferred from
  the mere presence of JSON fields.
- `coverage`: measured-usage and priceable-result counts/percentages.
- `cost_breakdown`, `cost_per_document`, `cost_per_page`: null unless the
  complete discovered batch has usable usage and applicable model prices.
  A per-page rate is null for zero measured pages.
- `covered_cost_breakdown`: separately labelled estimate for the covered
  subset, never presented as a full-batch estimate.
- `usage_summary`: full-batch totals or null; `covered_usage_summary`: measured
  subset totals. Known zero remains zero.
- `documents`: each relative result identity, recorded status, measured usage,
  estimated cost or null, and the reason for unavailable usage/pricing.

Reports/manifests are not synthesized into analysis files. Therefore
report-only failures or attempted inputs with no result file are **outside**
this loader's denominator. Consult the experiment manifest/native report for
attempted-input coverage. Costs incurred by missing or unmeasured results are
unknown. No timing or accuracy measurements are invented.

Without `--model`, pricing is selected only when measured token keys identify
one model. An unknown/unpriced model, mismatched override, or multiple measured
models produces an explicit per-result pricing error and null total. Mixed
models must be priced separately; counts are never silently priced as a
default model. PTU per-token scenario costs exclude capacity charges.

## Estimate from structured usage

```powershell
python tools\cu-cost-estimator\cu_cost_estimator.py estimate-usage --cu-output results\invoice.pdf.result.json --json
```

Accepted structured locations are `usage` at the direct native result root, at
the native LRO or saved CU-Tools envelope root, or in `result.usage`. Example:

```json
{
  "contents": [],
  "usage": {
    "documentPagesStandard": 2,
    "contextualizationToken": 2000,
    "tokens": {
      "gpt-4.1-input": 10400,
      "gpt-4.1-output": 360
    }
  }
}
```

Usage validation requires:

- Explicit input **and** output counts (zero is valid). Model-keyed
  `tokens: {"<model>-input": N, "<model>-output": N}`, unprefixed `input`/
  `output`, or saved `inputTokens`/`outputTokens` and
  `promptTokens`/`completionTokens` pairs are supported.
- Explicit `contextualizationToken`; historical plural
  `contextualizationTokens` is accepted. Conflicting aliases are an error.
- At least one measured page/minute counter:
  `documentPagesMinimal`, `documentPagesBasic`, `documentPagesStandard`,
  `audioMinutes`, or `videoMinutes`. Omitted alternative dimensions are assumed
  unused only after an explicit measured dimension is present.
- Nonnegative finite quantities, with integer token/page counts. Null, strings,
  booleans, missing directions and unrecognized token keys are rejected.

`embeddingTokens` is also retained when present. Absent/incomplete usage fails
`estimate-usage` nonzero; a directory summary instead records unknown usage
coverage. This is deliberately stricter than guessing missing counters as zero.

Explicit counts avoid any dependency on result capture:

```powershell
python tools\cu-cost-estimator\cu_cost_estimator.py estimate-usage --input-tokens 10400 --output-tokens 360 --ctx-tokens 2000 --pages 2 --model gpt-4.1 --json
python tools\cu-cost-estimator\cu_cost_estimator.py estimate-usage --input-tokens 10400 --output-tokens 360 --ctx-tokens 2000 --pages 2 --model gpt-4.1 --scale-to 1000
```

With explicit token arguments, `--ctx-tokens`, `--pages`, and `--model` are
required. Use explicit zero only when known. Scaling from zero measured pages
is rejected. JSON commands emit only JSON on stdout.

Python API (add this tool directory to your import path):

```python
from cu_cost_estimator import (
    CostEstimator, ProcessingRequest, UsageData,
    extract_usage_from_cu_output, usage_data_from_extracted,
)

measured = extract_usage_from_cu_output("invoice.pdf.result.json")
usage = usage_data_from_extracted(measured)
request = ProcessingRequest(
    file_type="document",
    quantity=measured["document_pages"],
    model_name="gpt-4.1",
    usage_data=usage,
)
estimate = CostEstimator().estimate_from_usage(request)
```

`extract_usage_from_result(dict)` is the equivalent for a native or normalized
in-memory result. Direct `UsageData(...)` construction remains available:
optional counters default to zero as an **explicit caller scenario assumption**.
File readers do not assume missing required counters are zero.

## Schema/volume planning (no measured usage)

```powershell
python tools\cu-cost-estimator\cu_cost_estimator.py estimate --file-type document --quantity 1000 --model gpt-4.1 --schema-fields 10 --schema-complexity moderate --source-grounding --json
```

`SchemaConfig` models field count, complexity, grounding/confidence,
extractive mode, training examples and segmentation/categorization. These
estimates are rough scenarios, not observed token counts. `estimate` without
schema options uses the bundled default token assumptions.

Legacy `analyze --results-file explicit-usage.json` accepts a list with
`pages`, `actual_input_tokens`, `actual_output_tokens`, and `model_name` per
record. Missing counts/prices fail explicitly. That legacy report estimates
**content and field extraction components only**, excluding contextualization,
embeddings and PTU capacity charges. Prefer the recursive result summary for
saved analysis JSON.

## Pricing and tests

`CostEstimator(custom_config)` accepts an explicit pricing configuration with
the same structure as `PRICING_CONFIG`. Built-in rates and schema token
assumptions are illustrative snapshots; never label their estimates billed
spend. No network lookup or automatic price update occurs.

Run separately from other suites to avoid historical module-name collisions:

```powershell
python -m pytest tools\cu-cost-estimator\tests -q --basetemp tools\cu-cost-estimator\tests\.test-work -o cache_dir=tools\cu-cost-estimator\tests\.pytest-cache -o "markers=unit: offline unit tests"
```
