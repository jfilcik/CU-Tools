# Preview agentic API: latency and quality report

**Overall status: FAIL**

Only **3/20 (15.0%)** contracts completed. This analyzer is not ready for broad production use on long contracts.

## Scope

This report evaluates one workload: Content Understanding preview API `2026-06-01-preview`, `gpt-5.2`, `config.workflow: Agentic`, the Southeast Asia test resource, this contract-obligation schema, 20 long held-out CUAD contracts, and three concurrent requests. It does not characterize other CU APIs, models, regions, schemas, or shorter inputs.

## Run configuration

| Setting | Value |
|---|---|
| Run ID | `run_20260721_163517_contract` |
| Analyzer | `contractobligationheldout20260721` |
| Region | `southeastasia` |
| API version | `2026-06-01-preview` |
| Model | `gpt-5.2` |
| Documents | 20 held-out CUAD contracts |
| Parallel requests | 3 |
| Per-document timeout | 1,800 seconds |
| End-to-end wall time | 17.33 hours |

## Content Understanding request IDs

These are the top-level Content Understanding asynchronous operation IDs
returned in the API `id` field. They are distinct from downstream Azure model
resource request IDs reported inside `innererror`.

| Outcome | CU request ID |
|---|---|
| Rate-limit failure | `c30802e0-5640-4e0e-9970-ab137a0c9cdc` |
| Rate-limit failure | `489f5bf4-f240-4797-b9c2-04cef1c6b914` |
| Rate-limit failure | `0c65a425-967a-4e26-a6d0-6c0f27e112e2` |
| Rate-limit failure | `c8c1d1a7-71c6-4116-9994-b5e8c21e8a6d` |
| Rate-limit failure | `02f487a6-107f-415b-bddd-1955b68c1950` |
| Rate-limit failure | `12c6c53f-72ee-4210-a942-b85b0e2e00a7` |
| Succeeded | `9f4034de-ec67-46f8-bc01-36d8e65ddcd5` |
| Succeeded | `f788c3c5-5e73-477d-8f3e-d3878fb1d38f` |
| Succeeded | `a1cfd04d-8830-4471-8323-6ef677720733` |

CU request IDs were not persisted for the nine client-side timeouts or two
connection resets. The current runner saves an operation ID only when a final
service result is returned, so those eleven requests cannot be correlated from
the retained artifacts. This observability gap is included in the bug report.

## API latency and reliability

| Metric | Result |
|---|---:|
| Successful | 3/20 (15.0%) |
| Failed | 17/20 (85.0%) |
| Timeouts | 9 |
| Request failures | 6 (the service log identified these as 429 rate-limit failures) |
| Connection resets | 2 |
| Mean completed latency | 18.4 minutes |
| P50 completed latency | 18.2 minutes |
| Max completed latency | 19.5 minutes |
| End-to-end wall time | 17.33 hours |

### Why the run took 17 hours

1. **Agentic work was token-intensive.** Each completed contract used an average of 615,930 input and 138,291 output tokens. The schema asks the model to discover, atomize, classify, relate, and quote every obligation in long legal text.
2. **Successful calls were already slow.** The three completions took 17.6-19.5 minutes each before queueing and failures are considered.
3. **Nine operations occupied capacity until the 30-minute analysis timeout.** With three workers, long-running calls held worker slots and later documents waited in the local queue.
4. **Three-way concurrency exceeded available quota.** Six operations failed with service-reported HTTP 429 token/request rate limits.
5. **Two network connections reset.** The client uses Requests calls without connect/read timeouts. Its 1,800-second operation deadline is checked between polling calls, so stalled HTTP I/O can extend wall time beyond the nominal analysis timeout.
6. **Document size was not the only cause.** A 26.9 KB contract timed out while successful contracts ranged from 62.8 KB to 177.0 KB. Service capacity, generated obligation volume, and transport behavior also materially affected latency.

## Overall observed API quality

| Dimension | Observed result | Assessment |
|---|---:|---|
| Completion reliability | 15.0% | Fail |
| Completed-call mean latency | 18.4 min | Too high |
| Timeout rate | 45.0% | Fail |
| Rate-limit failure rate | 30.0% | Fail |
| Connection-reset rate | 10.0% | Fail |
| End-to-end clause F1 | 4.4% | Fail |
| Survivor-only clause F1 | 13.6% | Fail |
| Exact quote groundedness | 98.2% | Strong on completed calls |
| Type accuracy on matches | 63.3% | Needs improvement |

## Extraction quality

Discovery is calculated across all 20 contracts. Failed documents contribute their CUAD clauses to the denominator and zero predictions, so the result fails closed rather than measuring only survivors.

| Metric | Result |
|---|---:|
| Clause discovery precision | 10.2% |
| Clause discovery recall | 2.8% |
| Clause discovery F1 | 4.4% |
| Survivor-only clause discovery F1 | 13.6% |
| Type accuracy on matched clauses | 63.3% |
| Exact quote groundedness (completed only) | 98.2% |
| Obligations with evidence (completed only) | 100.0% |
| Mean evidence-to-gold overlap | 84.9% |

Party-role accuracy and obligation completeness are **not scored** because the six-contract atomic gold set still requires human verification.

## Token diagnostics

The three completed contracts reported **1,847,791 input**, **414,872 output**, and **132,000 contextualization tokens** (**2,394,663 total reported tokens**). These totals are a lower bound because failed requests do not report complete token usage.

## Interpretation

Across all 20 contracts, the analyzer matched **30/1061** mapped CUAD clauses while producing **293** obligations from the three completed contracts. Operational failures dominate the 4.4% end-to-end F1, but survivor-only F1 remains low, so reliability is not the sole quality issue.

Evidence behavior was the strongest result: **327/333** quotes were found in source text and every completed obligation had evidence. The remaining weakness is finding the same obligation-bearing clauses as CUAD without over-producing loosely aligned obligations.

## Recommendation

Do not proceed to stability testing or production rollout with this shape. Before any future API test, add explicit HTTP connect/read timeouts and structured 429 retry/backoff, reduce concurrency to one, secure sufficient model quota, and bound input size through contract segmentation or a narrower obligation scope. Then rerun the same pinned manifest and complete second-reviewed atomic gold before publishing the weighted overall score.

## Per-contract results

| Contract | Status | Error | Minutes | Predicted | Gold clauses | Matched | F1 |
|---|---|---|---:|---:|---:|---:|---:|
| `aimmunetherapeuticsinc-20200205-8-k-ex-10-3-1196-daa14554` | failed | request_failed | 0.0 | 0 | 43 | 0 | 0.0% |
| `array-biopharma-inc-license-development-and-comm-a0e14c30` | failed | request_failed | 0.0 | 0 | 54 | 0 | 0.0% |
| `aurasystemsinc-06-16-2010-ex-10-25-strategic-all-8f073bd5` | failed | request_failed | 0.0 | 0 | 30 | 0 | 0.0% |
| `babcock-wilcoxenterprises-inc-08-04-2015-ex-10-1-7eb54db0` | failed | request_failed | 0.0 | 0 | 46 | 0 | 0.0% |
| `buffalowildwingsinc-06-05-1998-ex-10-3-franchise-d3ecacf8` | success | - | 17.6 | 79 | 74 | 19 | 24.8% |
| `cardlyticsinc-20180112-s-1-ex-10-16-11002987-ex--d108d8a9` | failed | request_failed | 0.0 | 0 | 82 | 0 | 0.0% |
| `coherusbiosciencesinc-20200227-10-k-ex-10-29-120-3b993cba` | failed | request_failed | 0.0 | 0 | 44 | 0 | 0.0% |
| `corioinc-07-20-2000-ex-10-5-license-and-hosting--9425f23a` | success | - | 19.5 | 63 | 38 | 5 | 9.9% |
| `dovapharmaceuticalsinc-20181108-10-q-ex-10-2-114-93a7191f` | success | - | 18.2 | 151 | 37 | 6 | 6.4% |
| `ehaveinc-20190515-20-f-ex-4-44-11678816-ex-4-44--ce6f3372` | failed | timeout | 0.0 | 0 | 46 | 0 | 0.0% |
| `gentechholdingsinc-20190808-1-a-ex1a-6-mat-ctrct-946f0758` | failed | timeout | 0.0 | 0 | 13 | 0 | 0.0% |
| `gooseheadinsurance-inc-04-02-2018-ex-10-6-franch-c9222751` | failed | timeout | 0.0 | 0 | 79 | 0 | 0.0% |
| `harpoontherapeuticsinc-20200312-10-k-ex-10-18-12-e3e3aa71` | failed | timeout | 0.0 | 0 | 59 | 0 | 0.0% |
| `healthgatedatacorp-11-24-1999-ex-10-1-hosting-an-c72abcf3` | failed | timeout | 0.0 | 0 | 36 | 0 | 0.0% |
| `jointcorp-09-19-2014-ex-10-15-franchise-agreemen-464a6b22` | failed | connection_reset | 0.0 | 0 | 69 | 0 | 0.0% |
| `monsanto-company-second-a-r-exclusive-agency-and-412f6a03` | failed | timeout | 0.0 | 0 | 79 | 0 | 0.0% |
| `mrsfieldsoriginalcookiesinc-01-29-1998-ex-10-fra-7714bf63` | failed | connection_reset | 0.0 | 0 | 63 | 0 | 0.0% |
| `playboyenterprisesinc-20090220-10-qa-ex-10-2-409-0ec4ad16` | failed | timeout | 0.0 | 0 | 58 | 0 | 0.0% |
| `ritterpharmaceuticalsinc-20200313-s-4a-ex-10-54--3e241e19` | failed | timeout | 0.0 | 0 | 39 | 0 | 0.0% |
| `upjohninc-20200121-10-12g-ex-2-6-11948692-ex-2-6-66e33fbe` | failed | timeout | 0.0 | 0 | 72 | 0 | 0.0% |

Machine-readable details are in the adjacent JSON and CSV artifacts.
