# Agents.md - CU Analyzer Testing Lab

## Purpose and sources of truth

Turn customer reproductions into evidence-based Content Understanding analyzer
improvements. Evaluate correctness and cost at each numbered iteration,
progressing toward safe straight-through processing (STP).

This file is authoritative for CU workflow boundaries and analyzer correctness.
[docs/iteration-workspaces.md](docs/iteration-workspaces.md) defines case and
iteration manifests, evidence, cost, and STP gates.
`.github/copilot-instructions.md` contains behavior and routing, not duplicate
technical specifications. `README.md` owns installation instructions.

## Repo map

| Surface | Responsibility |
|---------|----------------|
| Official `cu` executable | All CU service operations, authentication, discovery, scheduling, polling, retries, result serialization |
| `tools/cu-experiments/experiment.py` | Freeze a repeat/comparison matrix, invoke native CLI batches within one global concurrency budget, reconcile outcomes |
| `tools/cu-schema-plan/schema_plan.py` | Offline schema validation, dependency ordering, reference rewriting, immutable deployment snapshots and CLI command plans |
| `tools/cu-analyzer-validate/cu_analyzer_validator.py` | Offline schema quality and preview-contract checks |
| `tools/cu-results-export/export.py` | CSV/Excel and field diagnostics from saved native/legacy results |
| `tools/cu-cost-estimator/` | Explicit-usage/schema estimates and result-cost summaries |
| `tools/cu-usage-diagnostics/usage_diagnostics.py` | Customer-visible Azure Monitor usage exports in the caller's Storage account |
| `CU GA Migration/` | Offline inventory and conversion of exported analyzer definitions |
| `tools/cu-reading-order-viz/`, `tools/cu-segment-visualizer/`, `tools/cu-visualize/` | Local result/layout inspection |
| `tools/pdf-to-images/` | Local PDF rendering |
| `tools/pii-redact/` | Separate Azure Language-assisted PII workflow, not a CU execution backend |
| `.github/skills/`, `.github/prompts/` | Guided analyzer development and evaluation |
| `examples/_TEMPLATE/` | Copyable public-safe case and planned iteration |
| `examples/01-API-Testing/` | Official CLI exploration |
| `examples/02-Invoice-Extraction/`, `examples/03-Video-Analysis/` | Document/video tutorials |
| `examples/05-Agentic-Contract-Obligations/` | Public CUAD preparation and standalone quality reports |
| `examples/06-Contract-Obligation-Golden-Set/` | Reviewed ten-contract Standard/Agentic comparison |

There is no local CU REST client or compatibility package. Never import
`cu_cli`/`cu_cli_core` implementation modules from shipped helpers; the supported
execution boundary is the official executable.

## Commands

### CLI-only operation routing

Use `cu` directly for connectivity, analyzer list/show/validate/create/delete,
model defaults, layout, and file/folder analysis. Use the installed version's
`--help`; do not translate flags from deleted tools mechanically. The documented
contract was checked against public `cu-cli 0.1.0b1`.

The official CLI owns profiles and `CU_*` environment settings. It does not
load this repository's `.env`. No helper should maintain a second CU
credential/configuration path or put credentials in command arguments.

```powershell
cu doctor
cu analyzer list --json
cu analyzer validate .\schemas\invoice_v1.json --api-version 2025-11-01
cu analyzer create --name invoice_v1 --schema .\schemas\invoice_v1.json --api-version 2025-11-01
cu analyzer show invoice_v1 > .\invoice_v1-deployed.json

cu analyze .\invoice.pdf --analyzer prebuilt-layout --output-dir .\layout --on-existing error
cu analyze --source .\samples --recursive --analyzer invoice_v1 --json --output-dir .\results --report-file .\status.json --concurrency 5 --on-existing error
```

Analysis is billable. Review discovery with `--dry-run`; supply `--yes` only
after approving the scope and charge. The CLI's `--on-existing skip` avoids
reanalyzing existing outputs; `reanalyze` bills again. Experiments use new paths
and must not mix stale output with new evidence.

Custom analyzer IDs use letters, digits, and underscores (maximum 64
characters). Prefer a new version rather than deleting/recreating an existing
ID. There is no implicit replace operation. Cleanup requires explicit intent
and must target only resources actually created/owned by the experiment.
Inspect resource-wide defaults with `cu defaults show`; merge only the
requested mapping using `cu defaults set --model MODEL=DEPLOYMENT`. Do not
use `--replace` incidentally.

### Narrow local helpers

The existing validator is offline and uses the standard library:

```powershell
python tools\cu-analyzer-validate\cu_analyzer_validator.py .\schemas\invoice_v1.json
```

For dependency graphs, plan locally before executing any service operations:

```powershell
python tools\cu-schema-plan\schema_plan.py `
  --schema invoice=.\schemas\invoice.json `
  --schema packet=.\schemas\packet.json `
  --id-prefix case001_v1 --output .\deployment-plan `
  --api-version 2025-11-01
```

Source aliases in `baseAnalyzerId` and `contentCategories.*.analyzerId` become
versioned IDs. Undeclared external references, cycles, collisions, or invalid
schemas fail planning. `plan.json` contains source/snapshot hashes and
dependency-first create argument arrays. Review and execute these from the
plan directory using the official CLI; planning never checks Azure or deploys
anything. Cleanup arrays are suggestions, not proof every analyzer was created.

For repeated trials/comparisons:

```powershell
python tools\cu-experiments\experiment.py plan `
  --input .\invoice.pdf --analyzer invoice_v1 --analyzer invoice_v2 `
  --iterations 10 --concurrency 5 --output .\experiment `
  --api-version 2025-11-01

# Only after scope/cost approval:
python tools\cu-experiments\experiment.py run .\experiment --confirm-cost
```

The CLI has one analyzer per invocation and per-batch concurrency of 1..32.
It has no native repeat/multi-analyzer matrix option in the verified release.
The helper freezes distinct trial files and divides one global analysis budget
among CLI processes. It does not reimplement per-document service calls,
polling, or retries. Expected jobs must reconcile with native reports/results;
missing, failed, malformed, or unexpected output is not success. Preserve
partial evidence and use a new plan for an explicitly approved retry.
The immutable `experiment.json` and changing `run.json` are separate contracts.
Capture deployed schema definitions explicitly; the helper's analyzer IDs are
not proof of immutable remote schema identity.

### Issue and iteration workspaces

Select the case and numbered iteration before generating artifacts. Follow
the [canonical guide](docs/iteration-workspaces.md), not a competing layout.
Keep customer cases private and preserve historical inputs/results in place.
New configuration, hypothesis, dataset, or metric changes require a new
iteration; repeated trials belong inside that iteration.

Freeze input/schema inventories, evaluator/truth versions, commands and CLI
version, API version, analyzer IDs, raw results, evaluation, cost basis, report,
and decision. Synchronize the root index from iteration manifests.
Record verified tracking bugs at issue and directly relevant iteration levels,
separately from local defect IDs. Never guess bug status, links, or resource
identity. Keep published issue IDs/share slugs stable.

## API rules and correctness

### 4.1 Authentication

Prefer official CLI profiles and Entra ID sign-in with `az login`.
Alternatively inject `CU_API_KEY` securely and select key authentication.
Clear conflicting environment overrides when switching identities/resources.
Do not record keys, bearer tokens, connection strings, or signed URLs in
schemas, manifests, logs, screenshots, or committed files.

Only use resources and customer-visible telemetry the caller is authorized to
access. Internal resource defaults, service-internal telemetry queries, and
private evaluation framework dependencies do not belong in this project.

### 4.2 Rate limits, polling, and retries

CU analysis is asynchronous except where the official CLI explicitly offers
synchronous preview behavior. The CLI owns submission, polling, backoff, and
timeouts. Do not copy the deleted client's retry counts or timeout defaults
into new helpers. The verified CLI has no `analyze --timeout` option.

HTTP 429 indicates throttling; choose concurrency appropriate to your resource.
The experiment helper's concurrency is a global budget, not a budget per
analyzer. Do not blindly rerun a failed command: requests may already have been
accepted and billed. Inspect retained reports and errors first.

### 4.3 Discovery and output contracts

Let the official CLI handle service inventory/pagination. `cu analyzer show ID`
already emits JSON; capture stdout for a definition snapshot. Do not pass
unsupported show output-format flags or write a second pagination client.

Native JSON results can contain root-level `contents` or an LRO
`result.contents` envelope, also used in older saved results. Typed fields use properties such as `valueString`,
`valueNumber`, `valueObject`, and `valueArray`. Preserve raw bytes and use the
offline result reader for derived export/cost work instead of rewriting
evidence into an invented legacy envelope.

CLI filenames preserve input extensions, e.g. `invoice.pdf.result.json`, and
source-relative paths. Keep analyzer/trial/source-relative identity when
recursively aggregating results. Status reports, manifests, schemas, and usage
summaries are not extraction results. Reconcile against the planned input
inventory; present skipped/failed/missing documents in denominators.

### 4.4 Errors and evidence

- Invalid input/configuration must produce actionable errors and nonzero exit.
- HTTP 401/403 indicates authentication/authorization problems.
- HTTP 429 indicates rate limiting; other 4xx errors require checking the request.
- Service errors/timeouts must remain distinguishable from valid empty extraction.

Use contextual logging and preserve CLI exit codes, stdout/stderr, reports,
and request IDs when exposed. Never catch broadly and return success-shaped
empty results. A completed process is not proof every planned document
succeeded; inspect per-input outcomes too.

Local plans/validation/dry-runs are not live validation. No tool should claim a
deployed resource exists, a schema works on service, or an operation was free
without evidence.

### 4.5 Document content and field descriptions

For document extraction, reason from the extracted text/layout before writing
field descriptions. Use text labels, section structure, alternative labels,
and format examples rather than color, font, boldness, or visual position alone.
Do not assume a text-oriented extraction workflow receives original images.
Use the video skill for modality-specific frame/timestamp guidance.

```json
{
  "invoiceDate": {
    "type": "string",
    "method": "extract",
    "description": "The invoice issue date near the invoice number. May be labeled Invoice Date, Issued, or Billing Date. Return the issue date rather than the payment deadline. Examples: 01/15/2024 or January 15, 2024."
  }
}
```

### 4.6 Schema design

Every field needs an appropriate type, explicit method (`extract`, `generate`,
or `classify`), and useful description. Describe what to extract, text-based
location/alternative labels, output format, and disambiguation. Match the
document language. Avoid vague instructions, styling cues, and contradictory
rules. Enable source/confidence where supported for inspection.

Start with 3-5 representative, approved samples. Inspect layout, create a
versioned schema, validate locally, and test before scaling. Local quality
checks complement official CLI structural/spec validation; neither replaces
service acceptance or reviewed extraction correctness.

### 4.7 Classify-and-route (contentCategories)

Use a standard single analyzer when documents share fields/structure.
Classify-and-route is for mixed packets with multiple document types.

```json
{
  "description": "Classify a mixed invoice and receipt packet.",
  "baseAnalyzerId": "prebuilt-document",
  "config": {
    "enableSegment": true,
    "contentCategories": {
      "invoice": {
        "description": "Invoice heading, invoice number, priced line items and amount due.",
        "analyzerId": "case001_v1_invoice"
      },
      "receipt": {
        "description": "Receipt heading, completed purchase details and paid amount.",
        "analyzerId": "case001_v1_receipt"
      },
      "other": {
        "description": "A document that does not match the invoice or receipt criteria."
      }
    },
    "omitContent": true
  },
  "models": {"completion": "gpt-4.1"}
}
```

The outer analyzer does not need `fieldSchema`: specialized inner analyzers
perform extraction. `enableSegment: true` enables multi-page segmentation.
Categories without `analyzerId` are classification-only. Descriptions use text
anchors, not styling. Inner analyzers must exist first; test them individually,
then test classification/segmentation before judging routed extraction.

Use the offline schema planner when dependencies need versioned IDs and
ordering. Otherwise create inner analyzers directly with `cu`, reference their
actual IDs, then create the outer analyzer. Inspect per-segment `category` and
`fields` in result `contents`. Keep classification errors separate from
extraction errors. See `.github/skills/generate-analyzer-classify-route.skill.md`.

### 4.8 Evaluation

Scale tests (1 x N documents) measure coverage across variations; stability
tests (N x 1 document) measure repeated-run consistency. Both are useful before
production, subject to explicit paid-run approval.

Export derived results to CSV and compare schema versions. Report reviewed
correctness and denominators, failures/retries, holdout scope, false accepts,
human review, and regressions. Fill rate, confidence, and non-null fields are
diagnostics, not correctness or STP. Fix/version ground truth and evaluator
alongside schemas; changing metrics requires a new comparison iteration.

### 4.9 Cost and tokens

Every iteration records cost status, amount or `null`, currency, basis, and
coverage. Tokens multiplied by a price sheet are **estimated cost**, not
actual charges. Missing usage/pricing remains unknown, never zero.

Native CLI `--usage` and `--time` may expose console evidence without stable
per-document numeric fields in result/report JSON. Preserve that evidence;
do not parse undocumented console text as a guaranteed data contract or invent
usage/timing. Include paid failures, retries, repeated trials, and evaluation
calls where measurable; explicitly state gaps.

Customer-visible Azure Monitor usage exports remain supported by
`cu-usage-diagnostics`. Sequential grouping is approximate and needs known
call counts and isolated windows; it is not deterministic CU request tracing.
See its README before attributing model calls to documents.

### 4.10 Preview agentic API

The examples use API `2026-06-01-preview`, model `gpt-5.2`,
`config.workflow: "Agentic"`, and one file per request. GA stays
`2025-11-01`. Pass the preview API version explicitly to validation, planning,
creation, and analysis. The local validator rejects `config.workflow` without
this explicit contract and accepts only the case-sensitive value `Agentic`.

Use your own authorized resource with available preview features/deployments;
there is no required internal account or fixed region. Start with an approved
short, non-sensitive smoke cycle before a corpus. Agentic work can have much
higher latency and token use; timeout does not itself mean the schema was
rejected. See `.github/skills/cu-preview-api.skill.md`.

## Code and documentation changes

Keep helpers narrow, modular, and testable. Use `pathlib.Path`, explicit
validation/errors, and standard-library-only offline validation where
possible. Reject ambiguous collisions and unsafe overwrites; preserve input
bytes, snapshots, and historical evidence.

Before adding code, check whether official CLI already covers the operation.
Do not add a general-purpose execution abstraction or import its internal
implementation packages. Unsupported CLI capabilities must be stated
explicitly, not silently replaced with different behavior or a REST fallback.
The former protected-input recovery, reference uploads, and service-generated
artifact downloads are not claimed as equivalent CLI capabilities. Local PDF
rendering remains available where appropriate.

Update affected tool READMEs, root navigation, skills/prompts, and examples.
Put technical rules here; put workspace format in the canonical guide. Public
examples start from `examples/_TEMPLATE/`; customer material stays outside this
repository. Never add internal subscriptions/resources, signed samples, or
private package/clone requirements.

## Definition of done

- Relevant offline tests pass; new logic has regression coverage.
- Command examples match the installed public CLI contract.
- No new direct CU HTTP/SDK path, duplicated polling/authentication, or internal
  service dependency was introduced.
- Native and supported historical results remain distinguishable and usable;
  missing evidence cannot be reported as success or zero cost.
- Documentation and public example navigation match the implementation.

For analyzer work, additionally preserve schema/input hashes, exact commands,
CLI/API versions, expected job inventory, raw evidence, reviewed truth and
evaluator versions, CSV/report links, metric denominators, cost coverage,
baseline comparison, and accept/reject/inconclusive decision. Synchronize the
root manifest without overwriting completed iterations.

For planned/documentation-only work, report **not run**, empty measured
metrics, unknown/null cost, and remaining prerequisites. Live validation
requires actual approved service evidence. STP claims require the stronger
case-level gates in the workspace guide, not fill/confidence targets.
