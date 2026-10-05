# Standard vs. Agentic obligation golden set

This example compares Content Understanding Standard and Agentic extraction on
the same ten short contracts and the same 34-field schema. Unlike CUAD's
category-level clause labels, the reviewed golden set targets broad atomic
contractual obligations.

## What the example demonstrates

1. Select ten complete, obligation-bearing CUAD contracts under 1,000 words.
2. Independently annotate parties and every express atomic obligation.
3. Run the GA Standard analyzer first.
4. Run the preview Agentic analyzer against the identical documents and fields.
5. Score both modes fail-closed for discovery, role and type accuracy,
   groundedness, duplicates, latency, and token usage.
6. Generate a new comparison report and inspect the same flow in a Python notebook.

The comparison does not assume Agentic wins. The evaluator applies the same
readiness criteria to both modes and flags preview reliability, cost, or quality
limits when observed.

[`REPORT.md`](REPORT.md), `evaluation/qualitative_review.*`, and saved
`test_results/{standard,agentic}` / `evaluation/output/*_metrics.json` are
**historical evidence**, collected before the native CLI workflow below.
They are not rewritten or attributed to these new commands.

## Test matrix

| Mode | API | Model | Workflow |
|---|---|---|---|
| Standard | `2025-11-01` | `gpt-4.1` | Standard |
| Agentic | `2026-06-01-preview` | `gpt-5.2` | `Agentic` |

The recorded benchmark ran in Southeast Asia with identical `fieldSchema`
content. To reproduce it, use your own authorized resource with both modes and
the required model deployments available; no particular test account is required.
This is a product-mode comparison, not an isolated model
ablation: the API and completion model necessarily change with the mode.

## Prepare

Install and configure the official CLI as described in the repository
[`README.md`](../../README.md). The commands below use the public
`cu 0.1.0b1` dialect; verify `cu --version` and `cu analyze --help`.
The notebook prefers the repository virtual environment's executable, or an
explicit `CU_GOLDEN_CLI` path, rather than an incompatible global installation.
Authentication belongs to the CLI's selected profile / `CU_*` configuration.
These helpers do not load `.env`, obtain credentials, or change model defaults.

Download the public CUAD fixture through example 05 if it is not already present,
then materialize the checksum-pinned selection. No private evaluation framework
or private dataset is required:

```powershell
python examples\05-Agentic-Contract-Obligations\scripts\download_cuad.py
python examples\06-Contract-Obligation-Golden-Set\scripts\prepare_dataset.py `
  --output examples\06-Contract-Obligation-Golden-Set\samples\cli_inputs `
  --manifest-output examples\06-Contract-Obligation-Golden-Set\samples\cli_inputs.manifest.json
python examples\06-Contract-Obligation-Golden-Set\scripts\build_schemas.py
```

Validate both schemas:

```powershell
cu analyzer validate `
  examples\06-Contract-Obligation-Golden-Set\schemas\contract_obligations_standard_v1.json `
  --api-version 2025-11-01

cu analyzer validate `
  examples\06-Contract-Obligation-Golden-Set\schemas\contract_obligations_agentic_v1.json `
  --api-version 2026-06-01-preview
```

## Plan and run

Use new versioned analyzer IDs and a unique output directory. Run from the
repository root. The dedicated `samples\cli_inputs` directory contains only
the ten source contracts; the provenance manifest is outside it. Do not point
the CLI at the historical `samples\downloaded` directory, which also contains a
JSON manifest that would be analyzed as an eleventh document. This workflow
does not rely on `--pattern` filtering in the pinned CLI release.
First inspect both **local, no-service** plans:

```powershell
$example = (Resolve-Path examples\06-Contract-Obligation-Golden-Set).Path
$run = "cli_" + (Get-Date -Format "yyyyMMdd_HHmmss") + "_" + ([guid]::NewGuid().ToString("N").Substring(0, 8))
$standardId = "golden_standard_" + $run
$agenticId = "golden_agentic_" + $run
$newResults = Join-Path $example "test_results\$run"
$samples = Join-Path $example "samples\cli_inputs"

cu analyze --source $samples --recursive --analyzer $standardId `
  --json --output-dir "$newResults\standard" --report-file "$newResults\standard\report.json" `
  --api-version 2025-11-01 --concurrency 5 --on-existing error --usage --time --dry-run
if ($LASTEXITCODE -ne 0) { throw "Standard plan failed" }

cu analyze --source $samples --recursive --analyzer $agenticId `
  --json --output-dir "$newResults\agentic" --report-file "$newResults\agentic\report.json" `
  --api-version 2026-06-01-preview --concurrency 5 --on-existing error --usage --time --dry-run
if ($LASTEXITCODE -ne 0) { throw "Agentic plan failed" }
```

Only after approving the cost of all 20 analyses, create and analyze Standard,
then Agentic. The two batches are separate CLI invocations, not a matrix or
repeat service wrapper. Keep stderr logs as usage/timing evidence:

```powershell
New-Item -ItemType Directory -Path $newResults -ErrorAction Stop | Out-Null

cu analyzer create --name $standardId `
  --schema "$example\schemas\contract_obligations_standard_v1.json" --api-version 2025-11-01
if ($LASTEXITCODE -ne 0) { throw "Standard creation failed" }
cu analyzer show $standardId --api-version 2025-11-01 > "$newResults\standard.schema.json"
if ($LASTEXITCODE -ne 0) { throw "Standard schema capture failed" }
cu analyze --source $samples --recursive --analyzer $standardId `
  --json --output-dir "$newResults\standard" --report-file "$newResults\standard\report.json" `
  --api-version 2025-11-01 --concurrency 5 --on-existing error --usage --time `
  2> "$newResults\standard.stderr.log"
if ($LASTEXITCODE -ne 0) { throw "Standard batch failed; inspect report.json before evaluating" }

cu analyzer create --name $agenticId `
  --schema "$example\schemas\contract_obligations_agentic_v1.json" --api-version 2026-06-01-preview
if ($LASTEXITCODE -ne 0) { throw "Agentic creation failed" }
cu analyzer show $agenticId --api-version 2026-06-01-preview > "$newResults\agentic.schema.json"
if ($LASTEXITCODE -ne 0) { throw "Agentic schema capture failed" }
cu analyze --source $samples --recursive --analyzer $agenticId `
  --json --output-dir "$newResults\agentic" --report-file "$newResults\agentic\report.json" `
  --api-version 2026-06-01-preview --concurrency 5 --on-existing error --usage --time `
  2> "$newResults\agentic.stderr.log"
if ($LASTEXITCODE -ne 0) { throw "Agentic batch failed; inspect report.json before evaluating" }
```

Agentic calls are paid, slow, and token-intensive even for short contracts. Do
not add stability repetitions without a separate cost decision. The CLI retains
the new analyzers; delete only the IDs you intentionally created when finished.
Never delete/recreate existing analyzer IDs as an incidental update.
Use `--yes` only after explicit cost approval; it bypasses discovery confirmation.
No resource/account or region is automatically selected by this example.

## Evaluate

```powershell
python examples\06-Contract-Obligation-Golden-Set\evaluation\evaluate.py `
  --standard-results "$newResults\standard" `
  --agentic-results "$newResults\agentic" `
  --samples $samples `
  --output "$example\evaluation\output\$run"
```

The evaluator writes row-level JSON and a **new** `REPORT.md` in the output
directory. If `--output` is omitted, it chooses a unique directory under
`evaluation/output/`. Existing report/metric files are never overwritten.
Pass each mode's directory, not their common parent. An empty directory is a
valid all-missing run; a nonexistent directory is an error.

Native outputs such as `subfolder/contract.txt.result.json` retain the full
source-relative identity, including the input extension. Root `contents`,
typed fields, and older `result.contents` envelopes are supported through the
shared offline result loader. No CLI/SDK modules are imported by evaluation.
`report.json` in each run is read automatically; use `--standard-report` /
`--agentic-report` for custom report locations. Report input/output paths must
resolve inside the supplied source/result roots; moved absolute-path reports
need explicit path correction, not basename matching.

For a legacy comparison, pass the saved `test_results\standard` and
`test_results\agentic` directories instead, keeping the **new** output
directory. Legacy `metadata.json` supplies recorded status, source identity,
timing, and token counts; no manifest or historical output is rewritten.

The native CLI status report does not guarantee per-result numeric usage or
latency. `--usage` and `--time` preserve console evidence, not a structured
measurement contract. Missing numbers remain `null` / **unknown**, never zero
or cost-free. Totals require coverage of every expected document; separately
named observed token sums and measurement-coverage counts expose partial data.
No dollar cost is inferred.

## Notebook

Open
[`notebooks/standard_vs_agentic.ipynb`](notebooks/standard_vs_agentic.ipynb).
It is safe by default: schema validation and CLI dry-run plans are offline.
It can evaluate available historical results without replacing their reports;
edited cells have no saved outputs attributed to the new workflow. Set
`CU_GOLDEN_RUN_LIVE=1` before launching Jupyter only when you intentionally want
to approve and rerun all 20 paid analyses. Every CLI nonzero exit raises an
error and retains its logs; evaluation of partial runs is a separate deliberate
step using the new result directories.

## Scoring contract

- Evidence spans are matched one-to-one at a normalized quote threshold of
  `0.55`.
- Missing, failed, and skipped documents retain all expected obligations and receive zero
  predictions.
- Unrelated or duplicate source identities, malformed intended result files,
  conflicting manifests, and unrecognized result shapes/statuses fail closed.
  Metadata/report/schema files are not predictions.
- Source identities are matched against the gold set (`source_file` when
  present, otherwise `doc_id + ".txt"`); nested paths never collapse to stems.
- Native valid payloads may lack a service status; evaluation completion is
  inferred from a valid expected result, while `service_status` stays null.
- Discovery precision, recall, and F1 are separated from field accuracy.
- Matched obligations are checked for obligor, obligees, type, nature, required
  details, quote alignment, and summary similarity.
- All predicted evidence is checked against source text.
- Exact duplicate summaries/evidence are reported separately.

The gold set is model-assisted and independently adjudicated. Qualified
legal-human review is required before external or high-stakes use.

## Offline tests

```powershell
python -m pytest examples\06-Contract-Obligation-Golden-Set\evaluation\tests -q
```

The original fixture checks read the checksum-pinned public CUAD copy from
example 05. Native result/report fixtures and notebook execution are local;
the tests do not create analyzers or call Azure.

## Folder map

- `dataset/` - pinned curated selection and provenance
- `ground_truth/` - reviewed atomic obligation annotations
- `schemas/` - paired Standard and Agentic schemas
- `scripts/` - deterministic dataset and schema preparation
- `evaluation/` - fail-closed comparison and tests
- `notebooks/` - executable walkthrough
- `samples/`, `test_results/`, `evaluation/output/` - ignored local artifacts
