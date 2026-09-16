# CU-Tools

Turn a Content Understanding reproduction into a better analyzer: freeze the
inputs, test a hypothesis, measure correctness and cost, and keep the evidence
for each numbered iteration. The goal is safe straight-through processing,
not just a successful API response.

**The official [CU CLI](https://github.com/Azure/content-understanding-toolkit/tree/main/cu-cli)
performs every CU service operation.** This repository adds small experiment,
schema-planning, evaluation, and reporting tools. It does not maintain another
CU client, authentication stack, polling loop, or general-purpose CLI wrapper.
You do not need this repository just to use CU.

## Quick Start

### Install or update the official CLI

Use Python 3.10+ and a fresh virtual environment. In PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade --pre cu-cli
cu --version
cu --help
```

Rerun the install command in that environment to pick up the latest release;
`--pre` includes beta releases. Pin a tested version for reproducible automation.
The command examples here were checked against public `cu-cli 0.1.0b1`;
upstream `main` can document features not yet published to PyPI. Check the
installed command's `--help` rather than mixing flags from older installations.

If PowerShell activation is blocked, invoke `.\.venv\Scripts\python.exe` and
`.\.venv\Scripts\cu.exe` directly; no execution-policy change is needed.
On macOS/Linux use the environment's activation script; on macOS use the
`cu-cli` executable to avoid the system UUCP command named `cu`.

A toolkit source checkout is **not required**. Developers who deliberately
install from source should follow the
[upstream development instructions](https://github.com/Azure/content-understanding-toolkit/tree/main/cu-cli).
Do not automatically pull or overwrite a shared, dirty checkout when updating.

### Configure your resource

For Entra ID, sign in using Azure CLI and configure the official CLI profile:

```powershell
az login
cu profile set endpoint https://YOUR-RESOURCE.services.ai.azure.com/
cu profile set auth_mode login
cu profile set api_version 2025-11-01
cu doctor
```

Use your own authorized resource and model deployments. `cu doctor` checks
configuration; it does not provision them. See the
[official setup guide](https://github.com/Azure/content-understanding-toolkit/blob/main/cu-cli/README.md).

For API-key authentication, provide `CU_ENDPOINT`, `CU_AUTH_MODE=key`, and
`CU_API_KEY` through your shell or secret manager. Never put credentials in
command arguments, logs, committed files, or manifests. Clear stale
environment overrides when switching profiles or authentication modes.
The official CLI does **not** automatically load the repository's `.env`.

### Perform operations directly

These are individual examples, not a script to execute wholesale.
**Analysis is billable.**

```powershell
cu analyzer list --json
cu analyzer show prebuilt-layout

# Validate locally, then create a new version when ready.
cu analyzer validate .\schemas\my_analyzer_v1.json --api-version 2025-11-01
cu analyzer create --name my_analyzer_v1 --schema .\schemas\my_analyzer_v1.json --api-version 2025-11-01

# Capture the deployed definition; show already emits JSON.
cu analyzer show my_analyzer_v1 > .\analyzer-snapshot.json

# Layout as markdown; extracted fields as JSON.
cu analyze .\invoice.pdf --analyzer prebuilt-layout --output-dir .\layout --on-existing error
cu analyze .\invoice.pdf --analyzer my_analyzer_v1 --json --output-dir .\results --report-file .\status.json --on-existing error

# One analyzer, many documents: let the CLI schedule requests.
cu analyze --source .\samples --recursive --analyzer my_analyzer_v1 --json --output-dir .\batch --report-file .\batch-status.json --concurrency 5 --on-existing error

# Defaults affect the whole resource: inspect first, merge only the requested mapping.
cu defaults show
cu defaults set --model gpt-4.1=YOUR-EXISTING-DEPLOYMENT
```

Use `--dry-run` to inspect a local analysis plan without service calls. Use
`--yes` only after reviewing the scope and approving the charge; it bypasses
the CLI discovery confirmation. `--on-existing skip` preserves existing
outputs; `--on-existing reanalyze` incurs another charge. Fresh output paths
are preferable for experiments.
Keep only intended inputs in source directories; store manifests, schemas,
and outputs elsewhere. Use repeated `--file` options for an explicit selection.

Prefer new analyzer IDs such as `my_analyzer_v2`. Deleting and recreating an
existing ID is destructive and creates an availability gap. Only run
`cu analyzer delete ID` for explicitly authorized cleanup. Custom IDs use
letters, digits, and underscores, up to 64 characters.

## Add CU-Tools when you need more

In the same environment:

```powershell
git clone https://github.com/jfilcik/CU-Tools.git
Set-Location CU-Tools
python -m pip install -r requirements.txt
```

The requirements include the official CLI and dependencies for local reporting
and customer-visible usage exports. CU configuration still belongs exclusively
to the official CLI. There is no second set of CU credentials to configure.

| Need | Simplest tool |
|------|---------------|
| Connectivity, analyzer lifecycle, model defaults, file/folder analysis | Official `cu` |
| Five/ten repeated trials or comparisons across analyzers | [cu-experiments](tools/cu-experiments/README.md): frozen inputs + native CLI batches |
| Local schema descriptions/quality checks | [cu-analyzer-validate](tools/cu-analyzer-validate/README.md) |
| Classify-and-route dependency ordering and versioned snapshots | [cu-schema-plan](tools/cu-schema-plan/README.md): offline plan, then explicit `cu` commands |
| Upgrade exported analyzer definitions | [CU GA Migration](CU%20GA%20Migration/README.md): offline conversion, then explicit `cu` commands |
| CSV/Excel and field diagnostics | [cu-results-export](tools/cu-results-export/README.md) |
| Explicit-usage/schema cost estimates | [cu-cost-estimator](tools/cu-cost-estimator/README.md) |
| Your own Azure Monitor usage-export blobs | [cu-usage-diagnostics](tools/cu-usage-diagnostics/README.md) |
| Layout/field inspection or local PDF rendering | [Reading order](tools/cu-reading-order-viz/README.md), [field viewer](tools/cu-visualize/cuDocVisualizer.html), [PDF images](tools/pdf-to-images/) |

### Repetitions and analyzer comparisons

The native CLI runs **one analyzer per invocation**, with concurrency from
1 to 32. It has no repetition or multi-analyzer matrix option in the verified
release. The experiment helper supplies only that missing coordination:

```powershell
# Offline: freeze one document into ten distinct trial inputs for each analyzer.
python tools\cu-experiments\experiment.py plan `
  --input .\invoice.pdf `
  --analyzer invoice_v1 --analyzer invoice_v2 `
  --iterations 10 --concurrency 5 `
  --api-version 2025-11-01 `
  --output .\case\iterations\002\outputs\experiment

# Review the planned 20 analyses and their cost before executing.
python tools\cu-experiments\experiment.py run `
  .\case\iterations\002\outputs\experiment --confirm-cost
```

For five parallel trials of one analyzer, specify it once and use
`--iterations 5 --concurrency 5`. Inputs are explicit files, not directories;
ordinary folder batches go directly through `cu analyze`.

The helper partitions a **global concurrency budget** among native CLI
processes. The CLI still owns request scheduling, polling, retries, and result
serialization. Plans retain the full expected matrix; failed or missing
outputs cannot silently become successful tests. There is no automatic
analyzer creation/deletion, rerun, or rebilling.

`experiment.json` is the immutable input/job plan; `run.json` records execution
state and outcomes separately. Each analyzer batch retains its native status
report, raw results, stdout, and stderr. Analyzer IDs alone do not freeze remote
schema identity: capture definitions with `cu analyzer show` and link those
snapshots in the enclosing iteration before comparing versions.

### Local planning and reporting

```powershell
python tools\cu-analyzer-validate\cu_analyzer_validator.py .\schemas\invoice.json

# Offline: schemas reference each other by the supplied aliases.
python tools\cu-schema-plan\schema_plan.py `
  --schema invoice=.\schemas\invoice.json `
  --schema packet=.\schemas\packet.json `
  --id-prefix case001_v1 --output .\deployment-plan

python tools\cu-results-export\export.py --input .\results --output .\results.csv
```

The deployment plan freezes schemas, rewrites local dependencies, and emits
ordered official CLI argument arrays. Review and execute these separately;
planning is not proof that a resource/model/dependency exists in Azure.

**Results and cost:** reporting tools accept native CLI `*.result.json`
results as well as supported saved legacy result envelopes. Native results
can have root-level `contents` or an LRO `result.contents` envelope, with typed
field values. Status reports are
not extraction results. `--usage` and `--time` expose additional console
evidence, but do not guarantee machine-readable per-document token counts or
latency in the saved JSON. Missing usage, prices, or timing remains **unknown**,
not zero. Tokens multiplied by prices are estimates, not actual charges.

## Reproducible cases and iterations

Copy [examples/_TEMPLATE](examples/_TEMPLATE/) and follow the
[iteration-workspace contract](docs/iteration-workspaces.md). Each case has a
root manifest with customer/problem metadata, expected versus actual behavior,
tracking bugs, and an iteration index. Each numbered iteration preserves its
title/hypothesis, inputs/schema snapshots, raw output, evaluation, cost, and
report links. Repeated trials belong inside one numbered experiment.

Freeze reviewed truth and evaluation criteria before comparing versions.
Promote only with evidence of correctness, regressions, false accepts, human
review, holdout coverage, latency, and cost. Fill rate and confidence alone do
not demonstrate straight-through processing.

**Public tools, private cases:** customer documents, reports, manifests,
browser indexes, and site publishing belong in a restricted customer workspace,
not public CU-Tools. This repository supplies reusable templates and guidance;
it does not host customer cases. Preserve historical evidence when adding
navigation or changing execution tools.

Use the [skills](.github/skills/) and [prompts](.github/prompts/) for guided
schema generation, evaluation, video timestamps, and classify-and-route.
[Agents.md](Agents.md) is the technical source of truth.

## Examples

| Example | Focus |
|---------|-------|
| [01-API-Testing](examples/01-API-Testing/) | Explore CU with official CLI commands |
| [02-Invoice-Extraction](examples/02-Invoice-Extraction/) | Document analyzer development and numbered evidence |
| [03-Video-Analysis](examples/03-Video-Analysis/) | Video schemas with keyframe-anchored timestamps |
| [05-Agentic-Contract-Obligations](examples/05-Agentic-Contract-Obligations/) | Public CUAD preparation and standalone quality reports |
| [06-Contract-Obligation-Golden-Set](examples/06-Contract-Obligation-Golden-Set/) | Reviewed ten-contract Standard/Agentic comparison |

## Compatibility boundaries

This is a breaking simplification: the former general-purpose runners, local
CLI compatibility package, and REST client are removed. Capture new results
with the official CLI; keep old saved evidence for comparison. No new legacy
metadata envelopes or internal diagnostic headers are generated.

Service-side telemetry tooling, internal test-resource defaults, and private
evaluation-framework dependencies are not included. Customer-accessible Azure
Monitor exports remain supported; they are not a service-internal tracing API.

Legacy service-generated artifact downloads, reference uploads, and protected
input recovery are not advertised as equivalent CLI features. Check official
CLI support for your installed release; use the existing local PDF rendering
tool when images are all that is needed. Do not silently substitute a different
operation or add an undocumented REST fallback.

## Offline checks

Install the test dependencies only when developing, then run the relevant
tool's suite. The viewer's JavaScript checks additionally require Node.js 18+.
These checks do not require CU credentials or make paid calls:

```powershell
python -m pip install pytest
python -m pytest tools\cu-schema-plan\tests tools\cu-analyzer-validate\tests -q
python -m pytest tools\cu-experiments\tests -q
python -m pytest tools\cu-results-export\tests tools\cu-cost-estimator\tests -q
python -m pytest tests tools\cu-reading-order-viz\tests -q
node --test tools\cu-visualize\tests\run_files.test.js tools\cu-visualize\tests\browser_loader.test.js
```

Live analysis requires a separately approved scope and cost on your own
resource. A local validator, CLI dry-run, or passing unit suite is not live
service validation.
