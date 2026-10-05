# Standard vs. Agentic contract-obligation benchmark

**Result:** Agentic does not yet reach the 70% obligation-discovery F1 readiness bar for this curated use case.

## Benchmark design

- Test resource region: Southeast Asia.
- Standard run: `run_20260805_175210_contract` (2025-11-01).
- Agentic run: `run_20260805_175428_contract` (2026-06-01-preview).
- Golden set: 10 independently annotated short CUAD contracts.
- Gold obligations: 97.
- Standard: GA API with `gpt-4.1` and no Agentic workflow selector.
- Agentic: `2026-06-01-preview`, `gpt-5.2`, and `config.workflow: "Agentic"`.
- The field schema, source documents, matching threshold, and fail-closed scoring are identical.
- Failed documents retain all gold obligations and contribute zero predictions.

### Golden-set composition

| Contract type | Words | Gold obligations |
|---|---:|---:|
| Web Hosting Agreement | 223 | 6 |
| Content License Agreement | 342 | 9 |
| Sponsorship Agreement | 682 | 6 |
| Completion and Liquidity Maintenance Agreement | 742 | 4 |
| Intellectual Property Agreement | 739 | 2 |
| Franchise Agreement | 805 | 7 |
| Strategic Alliance Agreement | 875 | 15 |
| Supply Agreement | 903 | 16 |
| Services Agreement | 880 | 11 |
| Distributor Agreement | 970 | 21 |

The adjudicator finalized 97 obligations, removing 39, adding 1, and materially correcting 14 first-pass records. All hashes, offsets, IDs, references, enumerations, and duplicate checks passed.

## Headline comparison

| Metric | Standard | Agentic | Agentic delta |
|---|---:|---:|---:|
| Completion rate | 100.0% | 100.0% | +0.0% |
| Precision | 78.2% | 55.8% | -22.4% |
| Recall | 44.3% | 74.2% | +29.9% |
| Obligation F1 | 56.6% | 63.7% | +7.1% |
| Quote groundedness | 100.0% | 98.2% | -1.8% |
| Obligor accuracy | 88.4% | 83.3% | -5.0% |
| Obligee accuracy | 65.1% | 62.5% | -2.6% |
| Post-termination accuracy | 95.3% | 5.6% | -89.8% |
| Post-termination field coverage | 100.0% | 5.6% | -94.4% |
| Type accuracy | 81.4% | 79.2% | -2.2% |
| Nature accuracy | 48.8% | 68.1% | +19.2% |
| Required-detail accuracy | 28.6% | 33.1% | +4.6% |

Agentic obligation-F1 delta: **+7.1%**.

## Cost and latency

| Metric | Standard | Agentic |
|---|---:|---:|
| Completed documents | 10/10 | 10/10 |
| Mean latency | 19.7 s | 272.2 s |
| P95 latency | 27.0 s | 468.8 s |
| Active execution time | 3.3 min | 45.4 min |
| Input tokens | 42,470 | 1,466,452 |
| Output tokens | 14,298 | 303,768 |
| Duplicate obligations | 0 | 0 |
| Agentic latency multiplier | - | 13.8x |
| Agentic token multiplier | - | 31.2x |

Dollar cost is intentionally not estimated because the repository's cost model does not define a verified `gpt-5.2` preview price.

## Per-contract discovery

| Contract | Gold | Standard matched/predicted | Agentic matched/predicted | Standard F1 | Agentic F1 |
|---|---:|---:|---:|---:|---:|
| `galacticommtechnologiesinc-11-07-1997-ex-10-46-w-288e261b` | 6 | 3/4 | 4/7 | 60.0% | 61.5% |
| `watchitmediainc-20061201-8-k-ex-10-1-4148672-ex--ba668c47` | 9 | 8/10 | 9/12 | 84.2% | 85.7% |
| `pacificsystemscontroltechnologyinc-08-24-2000-ex-4c46375e` | 6 | 4/6 | 5/7 | 66.7% | 76.9% |
| `primeenergyresourcescorp-04-02-2007-ex-10-28-com-762f17ca` | 4 | 4/4 | 4/8 | 100.0% | 66.7% |
| `versotechnologiesinc-12-28-2007-ex-99-3-intellec-9630dd45` | 2 | 1/2 | 1/2 | 50.0% | 50.0% |
| `rgcresourcesinc-20151216-8-k-ex-10-3-9372751-ex--f744ccc2` | 7 | 3/3 | 5/6 | 60.0% | 76.9% |
| `xlitechnologies-inc-12-02-2015-ex-10-02-strategi-a37346f8` | 15 | 3/6 | 10/22 | 28.6% | 54.1% |
| `gridironbionutrients-inc-02-05-2020-ex-10-3-supp-b90c3016` | 16 | 5/6 | 10/21 | 45.5% | 54.1% |
| `transmontaignepartnersllc-03-13-2020-ex-10-9-ser-8509116d` | 11 | 4/5 | 7/18 | 50.0% | 48.3% |
| `precheckhealthservicesinc-20200320-8-k-ex-99-2-1-4594891a` | 21 | 8/9 | 17/26 | 53.3% | 72.3% |

## Readiness gates

| Gate | Target | Agentic result | Status |
|---|---:|---:|---|
| Completion | >=80% | 100.0% | PASS |
| Obligation discovery F1 | >=70% | 63.7% | FAIL |
| Quote groundedness | >=90% | 98.2% | PASS |
| Material gain over Standard | >=10 points F1 | +7.1% | FAIL |

These are demo-readiness gates for this example, not service SLAs or universal legal-extraction thresholds.

## Error profile

- Standard missed 54 gold obligations and emitted 12 unmatched predictions.
- Agentic missed 25 gold obligations and emitted 57 unmatched predictions.
- Standard required-detail accuracy was 28.6%; Agentic required-detail accuracy was 33.1%.

## Independent qualitative review

**Agentic materially improves recall and practical clause discovery, but it does not deliver a compelling balanced-quality or production-readiness win on this run.**

- Demo: Reasonable as a candid recall-oriented demo with side-by-side evidence and human review. Not reasonable if presented as broadly superior, inexpensive, fast, or production ready.
- Production: Neither mode is a standalone production approach for a complete atomic obligation register. Standard is too incomplete; Agentic is too noisy, slow, token-heavy, and schema-incomplete: IsPostTermination is populated on only 5.6% of matched outputs.

- Standard is not a total failure: it is fast (19.7 s mean), 78.2% precise, and 100% quote-grounded, but 44.3% atomic recall makes it unsuitable for exhaustive obligation inventories.
- Agentic raises atomic recall from 44.3% to 74.2% and reduces true source-content misses from 33 to 5, a material discovery improvement.
- Balanced quality improves modestly: F1 moves from 56.6% to 63.7% (+7.1 points), below the evaluator's 10-point material-advantage threshold.
- Of 25 Agentic false negatives, 20 are one-to-one/atomicity non-matches with 1.0 quote support in an already-matched prediction; only 5 are true unrepresented duties.
- Of 57 Agentic unmatched predictions, 41 are genuine rights/options/grants/facts/legal effects, 8 are valid alternate atomization, 5 are duplicate fragments, 3 are quote/evaluator artifacts, and 0 are high-confidence gold omissions.
- Deterministic 55.8% precision is conservative for source-supported usefulness but directionally fair for raw atomic output: reviewed useful yield is roughly 61-64%, or 67% if redundant fragments count.
- Agentic quote groundedness is effectively strong: the reported 98.2% reflects three Prime quotes differing only by an extra trailing quotation mark, not invented substantive text.
- Agentic has a material schema-completeness failure: IsPostTermination effective accuracy and coverage are both 5.6% (4/72 present and correct), versus Standard 95.3% accuracy and 100% coverage (43/43 present).
- Agentic costs are large: 13.8x mean latency, 17.4x p95 latency, and 31.2x total tokens versus Standard.
- The next evidence-producing step should test a stricter obligation ontology/atomic schema and improved matching, then separately test a Standard-first Agentic-fallback cascade; no improvement from those unrun changes is claimed.

See [`evaluation/qualitative_review.md`](evaluation/qualitative_review.md) for the source-level review of every Agentic miss and unmatched prediction.

## Interpretation

This benchmark measures broad atomic obligations, not CUAD's narrower 31-category clause taxonomy. Evidence overlap drives one-to-one discovery matching; party, type, nature, details, duplicates, source groundedness, latency, and token usage are reported separately.

The comparison is a product-mode comparison, not an isolated model ablation: Standard uses the supported GA model/API combination while Agentic uses the verified preview model/API combination.

### Annotation limitations

- Galacticomm: passive no-additional-fees and Florida-forum sentences were excluded because they do not clearly identify the performing party.
- Pacific: passive media-approval and display-delivery clauses were attributed to the Sponsor from surrounding party-specific context.
- PrimeEnergy: severe OCR corruption and conflicting $25,000,000/$21,000,000 liquidity text are preserved in quotations.
- XLI: the purchase-order/payment condition in the third-party Product-access prohibition is grammatically ambiguous and preserved without repair; passive pricing text was excluded.
- Gridiron: TCH, my facsimile, and other source wording are preserved; product specifications were treated as descriptors of one sale duty.
- PreCheck: the discount remains the source placeholder ¨%; future-facing licensing and professional-service language in the Distributor description was treated as operative, while present factual representations were excluded.

The golden set is model-assisted and independently adjudicated, but it still requires qualified legal-human review before use as an external or contractual benchmark.
