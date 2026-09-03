# Implementation guide: agentic contract obligations

## Objective

Extract contract metadata, contracting parties, and atomic `obligor -> duty -> obligee` records. Require exact, contiguous evidence quotes and native CU source details. Exclude playbook deviation, fulfillment status, and generalized risk scoring.

## Preview setup

Use the CU Studio bug-bash flow in `.github/skills/cu-preview-api.skill.md`. Select the Southeast Asia resource `mmi-southeastasia-resource` in `MMI - Dev 01` / `mmi-usw3-studiotest`. For Studio project storage use `MMI - Dev 02` / `mmi-eft-infra` / `mmicustudiotestwus3` / `bugbash`.

Do not persist keys, tokens, or SAS URLs. Use a user-identifiable Studio project name.

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

## EvalLens

Local development uses EvalLens 0.2.0 at `C:\src\EvalLens`. The verified local revision is `7b1c5b45bcb4c492115854c955c6552c4ac24ba2`.

For a portable authenticated installation:

```powershell
pip install "evallens @ git+https://github.com/mcaps-microsoft/EvalLens.git@7b1c5b45bcb4c492115854c955c6552c4ac24ba2"
```

The project has one `contract_obligations` module joined by `doc_id`. The CU normalizer unwraps native `valueArray` / `valueObject` nodes. Seven `CUSTOM_CODE` evaluators measure discovery, type, party roles, groundedness, alignment, completeness, and duplicates without an LLM judge.

## Score and report

The report computes:

`overall = .30 discovery + .15 type + .20 party roles + .10 groundedness + .15 alignment + .05 completeness + .05 duplicate control`

`generate_accuracy_report.py` emits Markdown, JSON, and per-contract CSV. Keep latency, token usage, failures, API version, model, region, and schema revision with run metadata. Missing credentials, missing atomic annotations, and preview timeouts are execution gaps rather than passing scores.

## Commands

```powershell
python scripts\download_cuad.py
python scripts\prepare_cuad_eval.py --clean
python ..\..\tools\cu-analyzer-validate\cu_analyzer_validator.py `
  schemas\contract_obligations_agentic_v1.json `
  --api-version 2026-06-01-preview

$env:PYTHONPATH = "C:\src\EvalLens"
python -m pytest evaluation\tests
cd evaluation
python -m evallens validate --config config.yml
```

After producing CU results:

```powershell
python scripts\build_evallens_dataset.py --results test_results\<run>
python evaluation\run_evaluation.py --results test_results\<run> --run-id <run-id>
```

## Security and cost

- Never commit `.env`, keys, tokens, SAS URLs, raw contracts, generated quotations, or service output.
- Use public or approved non-sensitive contracts.
- Delete smoke-test analyzers unless reuse is intentional.
- Confirm paid scale and stability cost before execution.
- Treat agentic token and latency diagnostics as required report fields.

## Definition of done

- Preview schema validates with zero errors and warnings.
- A short Southeast Asia create/analyze/delete cycle succeeds.
- Every emitted obligation has at least one grounded exact quote.
- Downloader checksum and ZIP safety tests pass.
- Selection is deterministic from a clean checkout.
- Six atomic documents receive second-review verification.
- EvalLens config validates and evaluator tests pass.
- Development, held-out, and stability reports are reproducible.
- Weighted and component scores are traceable per contract.
