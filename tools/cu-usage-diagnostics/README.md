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
