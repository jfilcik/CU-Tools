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
6. Generate `REPORT.md` and inspect the same flow in a Python notebook.

The comparison does not assume Agentic wins. The report applies the same
readiness criteria to both modes and flags preview reliability, cost, or quality
limits when observed.

## Test matrix

| Mode | API | Model | Workflow |
|---|---|---|---|
| Standard | `2025-11-01` | `gpt-4.1` | Standard |
| Agentic | `2026-06-01-preview` | `gpt-5.2` | `Agentic` |

Both modes use the Southeast Asia test resource and identical `fieldSchema`
content. This is a supported product-mode comparison, not an isolated model
ablation: the API and completion model necessarily change with the mode.

## Prepare

Download CUAD through example 05, then materialize the pinned selection:

```powershell
python examples\05-Agentic-Contract-Obligations\scripts\download_cuad.py
python examples\06-Contract-Obligation-Golden-Set\scripts\prepare_dataset.py
python examples\06-Contract-Obligation-Golden-Set\scripts\build_schemas.py
```

Validate both schemas:

```powershell
python tools\cu-analyzer-validate\cu_analyzer_validator.py `
  examples\06-Contract-Obligation-Golden-Set\schemas\contract_obligations_standard_v1.json

python tools\cu-analyzer-validate\cu_analyzer_validator.py `
  examples\06-Contract-Obligation-Golden-Set\schemas\contract_obligations_agentic_v1.json `
  --api-version 2026-06-01-preview
```

## Run

Run Standard first. The runner deletes its temporary analyzer before returning:

```powershell
$env:PYTHONUTF8 = "1"
python tools\cu-analyzer-run\create_and_test.py `
  --schema examples\06-Contract-Obligation-Golden-Set\schemas\contract_obligations_standard_v1.json `
  --input examples\06-Contract-Obligation-Golden-Set\samples\downloaded `
  --output examples\06-Contract-Obligation-Golden-Set\test_results\standard `
  --api-version 2025-11-01 `
  --timeout 900 `
  --max-workers 2
```

Then run Agentic sequentially to reduce throttling and abandoned polling:

```powershell
$env:PYTHONUTF8 = "1"
python tools\cu-analyzer-run\create_and_test.py `
  --schema examples\06-Contract-Obligation-Golden-Set\schemas\contract_obligations_agentic_v1.json `
  --input examples\06-Contract-Obligation-Golden-Set\samples\downloaded `
  --output examples\06-Contract-Obligation-Golden-Set\test_results\agentic `
  --api-version 2026-06-01-preview `
  --timeout 1800 `
  --max-workers 1
```

Agentic calls are paid, slow, and token-intensive even for short contracts. Do
not add stability repetitions without a separate cost decision.

## Evaluate

```powershell
python examples\06-Contract-Obligation-Golden-Set\evaluation\evaluate.py `
  --standard-results examples\06-Contract-Obligation-Golden-Set\test_results\standard `
  --agentic-results examples\06-Contract-Obligation-Golden-Set\test_results\agentic
```

The evaluator writes ignored row-level JSON under `evaluation/output/` and the
versioned comparison to [`REPORT.md`](REPORT.md).

## Notebook

Open
[`notebooks/standard_vs_agentic.ipynb`](notebooks/standard_vs_agentic.ipynb).
It is safe by default and loads existing results. Set
`CU_GOLDEN_RUN_LIVE=1` before launching Jupyter only when you intentionally want
to rerun all 20 paid analyses.

## Scoring contract

- Evidence spans are matched one-to-one at a normalized quote threshold of
  `0.55`.
- Failed documents retain all expected obligations and receive zero
  predictions.
- Discovery precision, recall, and F1 are separated from field accuracy.
- Matched obligations are checked for obligor, obligees, type, nature, required
  details, quote alignment, and summary similarity.
- All predicted evidence is checked against source text.
- Exact duplicate summaries/evidence are reported separately.

The gold set is model-assisted and independently adjudicated. Qualified
legal-human review is required before external or high-stakes use.

## Folder map

- `dataset/` - pinned curated selection and provenance
- `ground_truth/` - reviewed atomic obligation annotations
- `schemas/` - paired Standard and Agentic schemas
- `scripts/` - deterministic dataset and schema preparation
- `evaluation/` - fail-closed comparison and tests
- `notebooks/` - executable walkthrough
- `samples/`, `test_results/`, `evaluation/output/` - ignored local artifacts
