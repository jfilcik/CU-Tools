# Manually match a CU analyze operation to Azure OpenAI usage logs

This walkthrough explains how to use the Azure portal to identify the Azure
OpenAI model calls that most likely belong to one Azure Content Understanding
(CU) `analyze` operation. It is intended as a manual investigation technique:
no scripts, SDKs, or log queries are required.

## What the matching can establish

Azure Monitor exposes two useful diagnostic-log categories for a
`Microsoft.CognitiveServices/accounts` resource:

- `RequestResponse` records resource requests, including CU requests.
- `AzureOpenAIRequestUsage` records Azure OpenAI model usage.

Both categories currently map to the `AzureDiagnostics` table when sent to a
Log Analytics workspace.

These records do **not** contain a documented shared identifier that joins a CU
operation to every Azure OpenAI call it caused. In particular, the
`correlationId` on an `AzureOpenAIRequestUsage` record identifies an individual
model-side call; it is not the CU operation ID and does not group all model
calls from one CU analysis.

The manual method is therefore an evidence-based time correlation. It is most
reliable when you run one CU request at a time, record its exact UTC start and
completion times, and avoid other activity on the same model deployment during
that interval.

## Before the test

In the Azure portal, open the Foundry or Cognitive Services resource that emits
the logs, then select **Monitoring > Diagnostic settings**. Create or edit a
diagnostic setting that sends these categories to the same Log Analytics
workspace:

- `RequestResponse`
- `AzureOpenAIRequestUsage`

If CU and the model deployment emit logs from different resources, configure
both resources to send their applicable categories to the same workspace.
Diagnostic settings only begin collecting after they are enabled; they do not
backfill earlier activity.

Allow for ingestion delay. Azure resource logs commonly take several minutes
to become queryable, so an empty portal view immediately after the test does
not prove that no model calls occurred.

## Four-step portal workflow

### 1. Run one isolated CU analysis

Submit one document to one analyzer. Record:

- The UTC time immediately before submission.
- The UTC time when the operation reaches its final state.
- The analyzer ID and API version.
- The operation ID from the `Operation-Location` URL.
- The client request ID, if one was supplied or returned.
- The model deployment expected to serve the analyzer.

CU analysis is asynchronous. Use the whole interval from submission through
final completion. The duration of the initial accepted request is not the
duration of the complete analysis.

For a clean investigation, do not submit another CU request or directly invoke
the same model deployment until this operation finishes.

### 2. Locate the CU request records

Open the destination Log Analytics workspace in the Azure portal and select
**Logs**. Use **Simple mode** if it is available:

1. Select the `AzureDiagnostics` table.
2. Set the portal time range to include several minutes before submission and
   after completion.
3. Filter `Category` to `RequestResponse`.
4. Filter `ResourceId` to the CU resource.
5. Sort by `TimeGenerated`.

Inspect the matching rows for the CU endpoint or operation. Useful common
resource-log fields include `OperationName`, `ResultType`, `ResultSignature`,
`DurationMs`, `CorrelationId`, and `ResourceId`. CU-specific request details can
appear in service-specific columns, the `properties` payload, or
`AdditionalFields`; inspect an actual row rather than assuming a fixed column
name.

Use these rows to confirm the resource, operation, response status, and request
boundary. Polling requests can produce additional `RequestResponse` rows.

### 3. Locate the candidate Azure OpenAI calls

Keep the same workspace and time range, then change the category filter to
`AzureOpenAIRequestUsage`. Filter to the resource that owns the model
deployment and sort the records chronologically.

Inspect the records whose event times fall between the CU submission and final
completion. The usage export consumed by CU-Tools has exposed these fields:

| Purpose | Fields to inspect |
|---------|-------------------|
| Event ordering | `TimeGenerated` in Log Analytics; `EnqueueTime` and `FluentdIngestTimestamp` in Storage exports |
| Resource and operation | `resourceId`, `operationName`, `category`, `location` |
| Individual model call | `correlationId` |
| Model identity | `modelDeploymentName`, `modelName`, `modelVersion` |
| Token usage | `promptTokens`, `cachedTokens`, `generatedTokens` |
| Latency details | `timeToFirstTokenMs`, `timeToLastTokenMs` |

The category is documented by Microsoft, but Microsoft does not currently
publish a field-by-field schema for all of its service-specific properties.
The model and token property names above are the customer-visible
`AzureOpenAIRequestUsage` export fields observed and consumed by
`cu-usage-diagnostics`. In Log Analytics, service-specific properties can be
flattened into typed columns or retained in a properties or
`AdditionalFields` payload, so inspect the actual record shape in your
workspace.

### 4. Decide whether the records are a credible match

Treat Azure OpenAI records as candidates for the CU operation when all of these
conditions are true:

- Their event times are inside the recorded CU processing interval.
- Their `resourceId` and `modelDeploymentName` identify the expected deployment.
- Their model name and version are consistent with the analyzer configuration.
- No unrelated request used that deployment during the interval.
- The number and sequence of records are plausible for the analyzer and input.

Record the matched rows, interval, resource IDs, deployment name, and any
ambiguity with the result. Sum token fields only after establishing this scope.
If unrelated activity overlaps the interval, the safe conclusion is
**inconclusive**, not an exact per-request cost.

## Timestamp interpretation

| Timestamp | Meaning |
|-----------|---------|
| `TimeGenerated` | Event time represented in the Log Analytics table and the primary time to use for portal matching. |
| `EnqueueTime` | Event time present in the observed Azure Storage export. CU-Tools treats a timezone-naive value as UTC because the adjacent ingestion timestamp is UTC. |
| `FluentdIngestTimestamp` | Later ingestion timestamp present in the observed Storage export. Useful as a consistency check, not as the model-call start time. |
| Azure Monitor ingestion time | When the record became queryable. This can be minutes after the event and should not replace the event timestamp for correlation. |

Use UTC throughout. Start with a wider discovery range to accommodate
ingestion delay, then narrow the candidate set using the event timestamps.

## What this does not prove

This process does not provide deterministic distributed tracing. It cannot
prove that every candidate model call came from the selected CU request when
other activity overlaps the same time window. The Azure OpenAI
`correlationId`, process ID, and thread ID are not substitutes for the CU
operation ID.

When available, CU result diagnostics can independently summarize completion
and embedding call counts and latency. They are useful corroborating evidence,
but the human-readable diagnostic message is not a stable token-accounting
schema and does not create a join to the Azure OpenAI usage records.

For repeated tests, run requests sequentially, preserve their submit and
completion times, and keep the window tight. The
[`cu-usage-diagnostics`](../tools/cu-usage-diagnostics/README.md) helper applies
the same limitation when grouping Storage-exported usage records.

## Microsoft Learn references

- [Diagnostic settings in Azure Monitor](https://learn.microsoft.com/en-us/azure/azure-monitor/data-collection/diagnostic-settings)
  explains how to route resource logs to Log Analytics or Storage.
- [Resource logs in Azure Monitor](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/resource-logs)
  describes resource-log collection and destinations.
- [Supported log categories for Microsoft.CognitiveServices/accounts](https://learn.microsoft.com/en-us/azure/azure-monitor/reference/supported-logs/microsoft-cognitiveservices-accounts-logs)
  lists `RequestResponse` and `AzureOpenAIRequestUsage` and their
  `AzureDiagnostics` destination table.
- [Azure resource log common schema](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/resource-logs-schema)
  defines common fields such as event time, resource ID, operation name,
  result, duration, correlation ID, and service-specific properties.
- [AzureDiagnostics table reference](https://learn.microsoft.com/en-us/azure/azure-monitor/reference/tables/azurediagnostics)
  describes the Log Analytics columns used to inspect the records.
- [Log data ingestion time in Azure Monitor](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/data-ingestion-time)
  explains `TimeGenerated`, ingestion time, and expected resource-log latency.
- [Monitoring data reference for Azure OpenAI](https://learn.microsoft.com/en-us/azure/foundry/openai/monitor-openai-reference)
  documents Azure OpenAI monitoring data and token and latency metrics.
- [Content Understanding Analyze REST API](https://learn.microsoft.com/en-us/rest/api/contentunderstanding/content-analyzers/analyze?view=rest-contentunderstanding-2025-11-01)
  documents the asynchronous analyze request, `Operation-Location`, and
  `x-ms-client-request-id`.
- [Retrieve Content Understanding diagnostics](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/how-to/retrieve-diagnostics)
  documents the optional `LLMStats` result information that can corroborate
  model-call count and latency.
