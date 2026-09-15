# CU prompt-cache telemetry

Correlate CU experiment runs with underlying model calls, then measure **token-weighted**
prompt-cache utilization. Standard-library Python; no additional dependencies.

This tool processes **metadata only**: correlation IDs, timestamps, model/workflow
names, call status, and token counts. Keep exports, real mappings, run manifests,
and reports in the private investigation repository, **not in public CU-Tools**.
It does not inspect prompts, documents, generated answers, or response headers.

## Run manifest

Save a JSON array with a unique `run_id` for each CU analyze submission:

```json
[
  {
    "run_id": "ga-routed-warm-1",
    "request_id": "request-1",
    "operation_id": "operation-1",
    "api_version": "2025-11-01",
    "variant": "routed"
  }
]
```

At least one of `request_id` or `operation_id` is required. Use IDs captured from
the submit response and operation location, not an analyzer ID, poll-request ID,
resource ID, URL, or SAS query. `api_version` and `variant` are optional labels.
`phase`, `iteration`, and `request_index` may also label a run. Optional
`correlation_ids` can supply up to eight additional, verified submission IDs.
IDs may contain ASCII letters, digits, `_`, `.`, `:`, and `-`, starting with a
letter/digit. A correlation ID cannot belong to multiple runs. Maximum: 100 runs.

### Use an existing experiment runner's `requests.json`

All three commands accept `--requests-file .\requests.json` instead of `--runs`.
The file must be a JSON array with one **completed** record per CU submission:

```json
[
  {
    "variant": "native-segment-classifier",
    "api_version": "2025-11-01",
    "phase": "same-document-repeat",
    "iteration": 1,
    "started_at": "2026-01-01T00:10:00Z",
    "completed_at": "2026-01-01T00:11:00Z",
    "operation_id": "operation-1",
    "response_headers": {
      "apim-request-id": "request-1"
    }
  }
]
```

The adapter assigns stable-by-array-position IDs (`request-000001`, etc.) and
preserves the zero-based `request_index`, variant, API version, phase, and
iteration in run summaries. An explicit `run_id` is also supported. Do not reorder
or replace the requests array between fetching telemetry and summarizing it.

It uses `operation_id`, `apim-request-id`, and `x-ms-request-id` (header names
are case-insensitive). Client/correlation headers are deliberately not automatic
join keys because they can be shared across submissions. Other fields—including
sample names, analyzer IDs, raw usage, LLMStats, result paths, and document
content—are ignored. It never derives cached-token counts from CU aggregate usage.

For `fetch`/`query`, omission of **both** `--start` and `--end` derives the window
from the earliest `started_at` through the latest `completed_at`, with five
minutes of padding on each side. Change padding with
`--window-padding-seconds` (0–3600), or explicitly supply both time bounds.
The maximum 24-hour window still applies. Incomplete records, reversed times,
missing IDs, or IDs shared across runs fail; records are never silently dropped.

```powershell
python C:\src\cu-tools\tools\cu-prompt-cache\prompt_cache.py fetch `
  --cluster https://YOUR-CLUSTER.REGION.kusto.windows.net --database YOUR_DATABASE `
  --mapping .\mapping.json --requests-file .\requests.json --output .\telemetry.json
python C:\src\cu-tools\tools\cu-prompt-cache\prompt_cache.py summarize `
  --input .\telemetry.json --requests-file .\requests.json --output .\cache-summary.json
```

## Offline export contract

`summarize` accepts an array of normalized rows or the primary table of a Kusto
**v1** `Tables` response whose columns have these names:

```json
[
  {
    "run_id": "ga-routed-warm-1",
    "request_id": "engine-request-1",
    "call_id": "trace-1:span-1",
    "timestamp": "2026-01-01T00:00:00Z",
    "model": "model-a",
    "status": "success",
    "prompt_tokens": 10000,
    "completion_tokens": 100,
    "cached_input_tokens": 8000,
    "cache_metric_source": "provider_reported",
    "workflow": "classification"
  }
]
```

- `request_id` is the correlated engine request; it can differ from the client ID.
  The exporter must establish the `run_id` link. Offline mode validates identities
  and expected-run coverage; it cannot independently verify that exported link.
- `call_id` must identify an individual model attempt, preferably `trace_id:span_id`.
  Distinct spans retain fan-out/retry calls. Identical duplicate rows are removed;
  conflicting observations of the same identity fail. Provider-internal retries
  without individual telemetry are **not** inferable.
- `prompt_tokens` includes cached input, not just uncached input.
- Token metrics must be nonnegative signed-64-bit integers (or decimal integer
  strings). Fractional, nonfinite, negative, and overflowing metrics fail.
  Cached input cannot exceed prompt input.
- All three token keys are required. Use explicit `null` for unavailable cached
  input. For `failed`, `retry`, or `unknown` status, both prompt and completion may
  be `null`; these calls remain visible and make aggregate usage incomplete.
  Successful calls require model, prompt, and completion.
- Declare `cache_metric_source` honestly:
  - `provider_reported`: an explicitly present zero is a measured cache miss;
    `null` is unknown.
  - `normalized_zero_default`: the producer substitutes zero for absent provider
    cache data. **Zero is ambiguous**, retained as
    `reported_cached_input_tokens: 0`, but excluded from known cache totals.
    A positive count is still evidence of a cache read.
- `workflow` is optional. Unknown extra input properties are not copied to reports.

```powershell
python C:\src\cu-tools\tools\cu-prompt-cache\prompt_cache.py summarize `
  --input .\telemetry.json --runs .\runs.json --output .\cache-summary.json
```

Output includes per-call, per-engine-request, per-run, per-model, and total
summaries. `cache_ratio = sum(cached input) / sum(prompt input)`, never an average
of per-call ratios. It is `null` when cache/usage data is incomplete or input is
zero. `known_cache_ratio` uses only calls with known cache metrics and has a
different denominator; inspect `cache_metric_prompt_coverage` alongside it.
`known_*` totals are **subtotals**, not estimates of missing data.
When total usage is known, `cache_ratio_lower_bound` treats unknown cache counts
as zero and `cache_ratio_upper_bound` treats their entire prompt as cached. These
are mathematical bounds over the exported calls, not predicted cache behavior.

## Schema-checked Kusto query and live collection

No internal cluster/table names or customer mapping are bundled. Obtain a mapping
from authorized service documentation and actual telemetry, then verify the table
with `YourTable | getschema`. Dynamic attribute names and their semantics must
also be checked against actual metadata/source: `getschema` cannot establish them.

Example **synthetic** mapping (not a deployable service schema):

```json
{
  "table": "Telemetry",
  "timestamp": "Timestamp",
  "request_id": "RequestId",
  "operation_id": "OperationId",
  "client_request_id": "ClientRequestId",
  "span_name": "SpanName",
  "trace_id": "TraceId",
  "call_id": "SpanId",
  "attributes": "Attributes",
  "span_names": ["model_call"],
  "cache_metric_source": "normalized_zero_default",
  "fields": {
    "model": "model",
    "status": "status",
    "prompt_tokens": "usage.input",
    "completion_tokens": "usage.output",
    "cached_input_tokens": "usage.cached",
    "workflow": "workflow"
  }
}
```

All column mappings are literal column names, not KQL expressions. Attribute
names address **literal JSON object keys**, including dots; they are not nested
JSON paths. The timestamp column must be `datetime`, attributes `string` or
`dynamic`, and other mapped columns `string`.

**Include failed attempts.** Some services route successful spans to one table
and error spans to another. Add `"additional_tables": ["TelemetryErrors"]` to
the mapping in that case (at most four additional tables). Every table must have
the mapped columns and pass schema validation; no inaccessible or missing table
is silently skipped. The query uses a strict union with an early time filter in
every branch. A mapping containing only success telemetry cannot measure retries.

Generate a query without contacting a service:

```powershell
python C:\src\cu-tools\tools\cu-prompt-cache\prompt_cache.py query `
  --mapping .\mapping.json --schema .\schema.json --runs .\runs.json `
  --start 2026-01-01T00:00:00Z --end 2026-01-01T01:00:00Z `
  --output .\cache-query.kql
```

`schema.json` is a `getschema` JSON export, either normalized rows with
`ColumnName`/`ColumnType`, or a Kusto v1 response. For live collection:

```powershell
python C:\src\cu-tools\tools\cu-prompt-cache\prompt_cache.py fetch `
  --cluster https://YOUR-CLUSTER.REGION.kusto.windows.net --database YOUR_DATABASE `
  --mapping .\mapping.json --runs .\runs.json `
  --start 2026-01-01T00:00:00Z --end 2026-01-01T01:00:00Z `
  --output .\telemetry.json
```

Live mode uses **existing Azure CLI authentication**, performs `getschema`, then
runs a read-only query. It never logs in, changes permissions, falls back to
another environment, or treats an access/query error as success.

For offline query generation with multiple tables, wrap the individual schema
exports as `{"schemas": {"Telemetry": [...], "TelemetryErrors": [...]}}`.
Live mode retrieves and checks every configured table's schema automatically.

Both modes:

1. Match manifest IDs against request, operation, and client-request columns,
   then materialize their engine request IDs.
2. Select every configured model-call span for those engine requests, including
   failed/retried calls, and join them to their run.
3. Project only allowlisted metadata, never full attributes or content.

Time bounds are timezone-required, start-inclusive/end-exclusive, and at most
24 hours. Choose bounds that include submission through completion, plus observed
telemetry lag. Default row cap is 10,000 (maximum 100,000); the query asks for one
extra row so `fetch` can detect truncation and fail. If manually exporting a
generated query, **check that its extra sentinel row was not reached** before
offline analysis: the offline checker cannot prove an export was untruncated.

Missing runs, ambiguous correlation, malformed metrics, missing schemas, query
errors (including partial failures), and live row-limit overflow fail explicitly.
Output files are written only after validation. An existing old output file is
not deleted on failure: always check the exit status before consuming an artifact.
Empty telemetry is not evidence of zero usage or a cache miss.
Missing-run errors identify the unmatched manifest run IDs so recent ingestion
lag can be distinguished from missing historical coverage without dropping runs.

## Optional explicit-price estimate

Use a JSON object keyed by the **exact returned model identity**, with all rates
in the same currency per million tokens:

```json
{
  "model-a": {
    "input_per_million": "2.00",
    "cached_input_per_million": "1.00",
    "output_per_million": "8.00"
  }
}
```

Add `--prices .\prices.json` to `summarize`. The tool uses decimal arithmetic:

```text
uncached baseline = (prompt × input price + completion × output price) / 1,000,000
cached discount   = cached input × (input price − cached price) / 1,000,000
cache-adjusted    = baseline − discount
```

Unknown models fail rather than inheriting another model's prices. Incomplete
cache data produces a known-discount subtotal and `cache_adjusted: null`.
No prices, deployment discounts, or caching guarantees are assumed. These are
**model-token scenarios, not invoices**: end-customer savings require verifying
which deployment/account is charged and its actual meter/rate contract. Cache
telemetry alone may reflect only backend utilization. Page/contextualization and
other charges are excluded. `customer_metered_savings_verified` remains false.

The current [Content Understanding pricing explainer](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/pricing-explainer)
states that CU uses the customer's supplied Foundry model deployment: LLM and
embedding token billing appears on that **Foundry deployment, not CU meters**.
Therefore, apply any supported cached-input discount to model input only, and
add CU content-extraction/layout and contextualization charges separately.
For otherwise matched analyzer work, model prompt caching does **not** discount
those CU page/contextualization charges. Compare their measured usage and the
resolved standard/advanced workflow rather than assuming every API variant has
the same contextualization rate.

The existing `cu-cost-estimator` remains useful for CU page/contextualization
costs. Its `UsageData` collapses model-specific input/output and has no cache
provenance; it is deliberately not used to infer cache savings here. Analysis
submission remains in `cu-client`/existing runners; this tool issues no CU calls.

## Tests

```powershell
python -m unittest discover -s C:\src\cu-tools\tools\cu-prompt-cache\tests -v
```

All tests are synthetic and run offline without writing temporary files.
