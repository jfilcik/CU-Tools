# CU usage diagnostics

Fetch and summarize **Azure Monitor diagnostic logs** for the
`AzureOpenAIRequestUsage` category exported to Azure Storage.

This tool reads the **standard customer-visible Azure Monitor diagnostic-log
export** path (`insights-logs-azureopenairequestusage` blobs).

Use this tool when you have:

- the Foundry/Cognitive Services **resource ID**,
- the diagnostic-log **storage account**,
- and a **time window** to inspect.

It downloads the hourly JSONL blobs, double-decodes each record's nested
`properties` payload, and extracts:

- `EnqueueTime`
- `correlationId`
- `modelDeploymentName`
- `modelName`
- `modelVersion`
- `promptTokens`
- `cachedTokens`
- `generatedTokens`

## Output modes

### 1) Raw aggregate summary

Returns total prompt, cached, and generated tokens for the requested window,
grouped by model.

```powershell
python C:\src\cu-tools\tools\cu-usage-diagnostics\usage_diagnostics.py `
  --resource-id /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<account> `
  --storage-account <storage-account> `
  --start 2026-09-12T20:00:00Z `
  --end 2026-09-12T21:00:00Z
```

### 2) Sequential per-request correlation

When CU requests were issued sequentially and you already know the expected
model-call count for each request, pass `--request-call-counts` in submission
order. The tool sorts diagnostic records by `EnqueueTime`, chunks them
sequentially, and prints per-request totals plus a cache-hit ratio
(`cachedTokens / promptTokens`).

```powershell
python C:\src\cu-tools\tools\cu-usage-diagnostics\usage_diagnostics.py `
  --resource-id /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<account> `
  --storage-account <storage-account> `
  --start 2026-09-12T20:00:00Z `
  --end 2026-09-12T21:00:00Z `
  --request-call-counts 4,4,6,6
```

If the requested group total is smaller than the available record count, the
tool prints a warning and includes an `unassigned` summary. If the requested
group total exceeds the available record count, the run fails fast.

## Limitations: no deterministic CU-request-to-LLM-call join key

The `AzureOpenAIRequestUsage` diagnostic record's full field set is:

- Top level: `EnqueueTime`, `FluentdIngestTimestamp`, `Tenant`, `category`,
  `correlationId`, `event`, `location`, `operationName`, `processID`,
  `properties`, `resourceId`, `threadID`.
- Nested `properties`: `cachedTokens`, `generatedTokens`,
  `modelDeploymentName`, `modelName`, `modelVersion`, `promptTokens`,
  `streamType`, `timeToFirstTokenMs`, `timeToLastTokenMs`.

**None of these match any ID Content Understanding returns to the caller**
(`operation-location`, `apim-request-id`, `x-ms-request-id`,
`x-ms-correlation-request-id`, `x-ms-client-request-id`). `correlationId`
looked like the obvious candidate but is not usable for this purpose:
verified against a known run where several CU requests each fanned out into
multiple model calls (CU's internal ~25-page chunking), every model call in
the same CU request had a **distinct** `correlationId` — it identifies one
AOAI-side model call, not the CU request that triggered it, and it does not
group a CU request's own chunk calls together either. `processID`/`threadID`
are worker-process identifiers reused across unrelated requests over time,
not usable as a request key.

Practical effect: this tool's `--request-call-counts` sequential-chunking
correlation (submission-order + expected call count) is currently the only
way to map these records back to specific CU requests. There is no shortcut
that would make that correlation exact/robust — keep the time window tight
around the known request timestamps (see Notes below) to avoid stray
records shifting the grouping.

## Notes

- The tool uses `DefaultAzureCredential`, so existing Azure CLI auth (`az login`)
  is enough in typical developer workflows.
- `--start` and `--end` must be explicit, timezone-aware ISO-8601 timestamps.
- `EnqueueTime` inside each diagnostic record is **naive** (no timezone suffix)
  in observed exports, but is UTC in practice (confirmed against the sibling
  `FluentdIngestTimestamp` field, which does carry a `Z` suffix and is only
  a few seconds later). The tool treats a naive `EnqueueTime` as UTC; it does
  not apply this leniency to `--start`/`--end`, which must be explicit.
- `--start` is inclusive and `--end` is exclusive.
- Blob lookup follows the Azure Monitor storage export convention for
  `AzureOpenAIRequestUsage`:
  `resourceId=/SUBSCRIPTIONS/.../y=YYYY/m=MM/d=DD/h=HH/m=00/PT1H.json`
- Unit tests cover only parsing/correlation logic; they do **not** perform live
  Azure calls.
