# Implementation guide: agentic contract obligations

## Objective

Extract contract metadata, contracting parties, and atomic `obligor -> duty -> obligee` records. Require exact, contiguous evidence quotes and native CU source details. Exclude playbook deviation, fulfillment status, and generalized risk scoring.

## Preview setup

Use your own authorized Azure AI resource with access to the preview API and
completion model below. Confirm availability and quota in your selected region.
If using Studio, create the project and any required storage in subscriptions
and resource groups you are authorized to use; no shared test environment is a
prerequisite.

Follow the repository README for official `cu` installation/authentication and the preview API
workflow in `.github/skills/cu-preview-api.skill.md`. Do not persist keys, tokens,
or SAS URLs in schemas, reports, or source control.

## API contract and compatibility

The schema requires:

```json
{
  "models": {"completion": "gpt-5.2"},
  "config": {"workflow": "Agentic"}
}
```

Pass `--api-version 2026-06-01-preview` to every validator, creation, and analysis command. The GA default is intentionally unchanged. The contract was verified with a successful create/analyze/delete cycle in Southeast Asia. Long-document latency remains a material risk; test short input first and use one file per request.

## Schema

`schemas/contract_obligations_agentic_v1.json` has three outputs:

1. `ContractMetadata` - title, type, effective/expiration date, governing law.
2. `Parties[]` - stable PartyId, legal name, aliases, and contract role.
3. `Obligations[]` - stable ID, obligor/obligees, controlled type and nature, summary, exact evidence, trigger, timing, amount, exceptions, survival flag, and relationships.

Descriptions require atomization, supported parties only, explicit qualifiers, deduplication, empty values instead of speculation, and at least one exact quote per obligation. Generated source references are convenience labels; CU grounding is authoritative.

## CUAD acquisition

The official archive is pinned by repository revision and SHA-256 in `dataset/cuad_manifest.json`. `download_cuad.py` verifies the checksum, requires the expected three files, and rejects absolute paths, traversal, backslashes, missing entries, and unexpected entries.

`prepare_cuad_eval.py` applies the obligation mapping and deterministic category-coverage selection:

- 5 development contracts.
- 20 held-out contracts.
- 6 held-out contracts selected for manual atomic annotation.

Raw text, exact clause spans, and generated selection files remain local and gitignored. Review CUAD licensing before redistribution.

## Annotation

CUAD measures clause discovery and evidence alignment but does not label complete atomic roles. Follow `ground_truth/annotation_guidelines.md` for the six-contract set. A second reviewer must verify every party, atomization decision, and exact quote.

## Standalone evaluation

The EvalLens integration has been removed because its package/repository was
not publicly available. No private checkout, authenticated package install,
registry plugin, or fallback implementation is used. Its dataset builder,
configuration, runner, seven registered evaluators, and weighted accuracy report
are no longer part of this example.

The existing standalone reports use only the Python standard library:

- `generate_broad_quality_report.py` matches broad obligation evidence to mapped
  CUAD clauses and reports discovery, matched type accuracy, quote grounding,
  latency, failures, and standard returned token usage.
- `generate_clause_span_report.py` matches category-specific exact spans against
  official CUAD annotations and reports per-category and per-document quality.
- `contract_eval_common.py` and the pure `canonicalize_result` helper retain
  shared matching and native CU `valueArray` / `valueObject` normalization.

Both reporters read official CLI status reports plus saved `--json` SDK results
and generated CUAD manifests/gold, and emit Markdown, JSON, and CSV. Save the
status report as `analyze-report.json` inside the results directory or pass
`--run-report`. Previously saved `metadata.json` bundles remain readable offline.
They do not invoke Azure or an LLM judge.
Analysis payloads are validated and normalized by the shared offline
`tools/cu-results-export/cu_result_io.py` reader. The status report and expected
benchmark manifest remain authoritative for missing, skipped, and failed
documents; discovering saved files alone cannot establish completion.
Failed or missing documents contribute gold spans and zero predictions; empty
selections fail. A successful report command means artifacts were generated,
not that quality passed. The broad report's completion status is separate from
its quality metrics.

Neither report consumes atomic annotations or scores atomic party roles,
completeness, duplicate control, or the retired weighted total. Retain manual
annotations as review evidence, not as an automatically scored result.
Missing analyses or unverified annotations are gaps, never passing scores.

Retain any actually recorded latency, standard returned usage, failures, API
version, model, region, and schema revision. Native CLI status reports omit
timing, usage, model/region, and API-version metadata. The reporters mark missing
measurements as `null`/blank/`not recorded`, never zero, and do not scrape
`--usage` or `--time` stderr output. The broad report does not assume a test resource. Keep
new outputs under ignored `test_results/` rather than overwriting the reviewed
historical measurements in `reports/`.

## Commands

```powershell
python scripts\download_cuad.py
python scripts\prepare_cuad_eval.py --clean
python ..\..\tools\cu-analyzer-validate\cu_analyzer_validator.py `
  schemas\contract_obligations_agentic_v1.json `
  --api-version 2026-06-01-preview

python scripts\prepare_clause_span_benchmark.py
python -m pytest evaluation\tests `
  --basetemp test_results\pytest-offline -p no:cacheprovider
```

After producing CU results:

```powershell
python evaluation\generate_broad_quality_report.py `
  --results test_results\<held-out-run> `
  --run-report test_results\<held-out-run>\analyze-report.json `
  --output-prefix test_results\broad-quality\quality
python evaluation\generate_clause_span_report.py `
  --results test_results\<clause-span-run> `
  --run-report test_results\<clause-span-run>\analyze-report.json `
  --output test_results\clause-span-report\quality.md
```

Use the explicit `cu analyzer create`, `cu analyze`, and
`cu analyzer delete ... --yes` sequences in this example's README for paid
service operations. They use unique IDs, native batch concurrency, fresh result
directories, and a saved status report. The official CLI has no `--timeout`
option; do not translate former runner flags mechanically.

## Security and cost

- Never commit `.env`, keys, tokens, SAS URLs, raw contracts, generated quotations, or service output.
- Use public or approved non-sensitive contracts.
- Delete smoke-test analyzers unless reuse is intentional.
- Confirm paid scale and stability cost before execution.
- Retain standard returned token usage and measured client latency; internal
  telemetry and diagnostic headers are not required.

## Definition of done

- Preview schema validates with zero errors and warnings.
- A short create/analyze/delete cycle succeeds on your authorized preview-capable resource.
- Every emitted obligation has at least one grounded exact quote.
- Downloader checksum and ZIP safety tests pass.
- Selection is deterministic from a clean checkout.
- Offline normalization, scoring, downloader, and report tests pass without private dependencies.
- Held-out and clause-span reports are reproducible from saved results.
- Quality metrics and failed/missing documents are traceable per contract.
- Any claimed manual atomic assessment has second-review verification; do not
  claim the unsupported weighted evaluation passed.
