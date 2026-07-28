# Agentic preview: five-PDF quality report

**Overall verdict: mixed operational improvement, but extraction quality is
still not good enough.**

Four of five original CUAD PDFs completed. Exact evidence grounding remained
strong, but clause discovery and type classification remained weak. The PDF
format did not consistently improve quality over the prior text inputs.

## Scope

This run used the Content Understanding `2026-06-01-preview` API, `gpt-5.2`,
`config.workflow: Agentic`, and the existing contract-obligation schema. Inputs
were five original PDFs from the pinned Hugging Face CUAD revision
`a3c393f5d103fd0c516374e4fdff676c8176dcb1`.

The selection contained the three prior text successes plus one prior
service-reported 429 failure and one prior timeout:

- Array BioPharma
- Buffalo Wild Wings
- Corio
- Dova Pharmaceuticals
- Ehave

## Result summary

| Metric | Result | Assessment |
|---|---:|---|
| Completed | 4/5 (80.0%) | Improved, not fully reliable |
| Failed/over-time | 1/5 (20.0%) | Dova remained running beyond 35 minutes |
| Fail-closed clause precision | 13.2% | Poor |
| Fail-closed clause recall | 16.9% | Poor |
| Fail-closed clause F1 | 14.8% | Poor |
| Survivor-only clause F1 | 15.8% | Poor |
| Type accuracy on matched clauses | 61.9% | Needs improvement |
| Exact quote groundedness | 96.7% | Strong |
| Obligations with evidence | 100.0% | Strong |
| Matched clauses | 42/249 | Low |
| Predicted obligations | 319 | High relative to matches |

The direct answer is **no: the completed PDF outputs are not broadly good
yet**. They are well grounded in source quotations, but they still miss most
mapped CUAD clauses and produce many obligations that do not align to a mapped
gold clause.

## Per-document quality

| Contract | Status | Pages | Predicted | Gold | Matched | F1 | Type accuracy | Quote groundedness |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Array BioPharma | Success | 107 | 101 | 54 | 5 | 6.5% | 80.0% | 95.0% |
| Buffalo Wild Wings | Success | 29 | 16 | 74 | 5 | 11.1% | 100.0% | 95.2% |
| Corio | Success | 13 | 61 | 38 | 13 | 26.3% | 46.2% | 97.0% |
| Dova Pharmaceuticals | Over-time | - | 0 | 37 | 0 | 0.0% | - | - |
| Ehave | Success | 27 | 141 | 46 | 19 | 20.3% | 57.9% | 97.9% |

Corio was the strongest PDF result at 26.3% F1. Array BioPharma completed but
matched only five of 54 mapped clauses. Ehave found 19 mapped clauses but
produced 141 obligations, indicating substantial over-production or granularity
mismatch.

## PDF versus prior text

Only Buffalo Wild Wings and Corio completed in both formats.

| Contract | Text F1 | PDF F1 | Change |
|---|---:|---:|---:|
| Buffalo Wild Wings | 24.8% | 11.1% | -13.7 points |
| Corio | 9.9% | 26.3% | +16.4 points |

The direction is inconsistent: PDF was materially worse for Buffalo Wild Wings
and materially better for Corio. Array BioPharma and Ehave changed from failed
text runs to successful PDF runs, while Dova changed from a successful text run
to an over-time PDF operation. Five documents are insufficient to claim that
PDF is generally better or worse.

The benchmark also has a target mismatch: CUAD labels review clauses in 32
mapped categories, while this analyzer extracts every atomic obligation across
a broader taxonomy. A valid atomic obligation can lack a CUAD counterpart, and
one CUAD clause can split into several predictions. This can depress precision,
but it does not explain the low recall.

## Latency and recovery behavior

The intended run was sequential with one worker. The first PDF, Array
BioPharma, completed in **26.0 minutes**. During polling of the second PDF,
local DNS resolution for the Azure endpoint failed. The operation itself later
completed and was recovered by CU request ID.

The three remaining retry submissions also lost DNS during polling. Because
each poll failed immediately, the sequential runner moved to the next document,
so Corio, Dova, and Ehave ultimately ran concurrently in the service despite
the one-worker configuration. Existing operations were recovered rather than
resubmitted:

- Corio was observed succeeded about 10.7 minutes after the retry began.
- Ehave was observed succeeded about 23.1 minutes after the retry began.
- Dova remained `Running` more than 35 minutes after submission and was counted
  as failed at the benchmark deadline.

Buffalo's exact service latency cannot be reconstructed because DNS failed
before the runner recorded completion timing. The overall attempt and recovery
window was approximately 80 minutes. These timings combine service work and
client-side DNS disruption and should not be treated as clean service latency
measurements.

## Token and page usage

The four completed PDFs reported:

| Usage | Total |
|---|---:|
| Document pages | 176 |
| Input tokens | 3,115,317 |
| Output tokens | 585,179 |
| Contextualization tokens | 176,000 |
| Total reported tokens | 3,876,496 |

That averages 778,829 input tokens and 146,295 output tokens per successful
PDF. Array BioPharma alone consumed 1,218,451 input and 231,203 output tokens
for 107 pages. Failed or still-running Dova usage was unavailable, so totals are
a lower bound.

## Content Understanding request IDs

| Contract | CU request ID | Final benchmark status |
|---|---|---|
| Array BioPharma | `a6b00fad-3535-4c7b-b0cd-7ddca8ef0a67` | Succeeded |
| Buffalo Wild Wings | `267a9697-7a38-4fbf-a972-1af7ad3ef1a8` | Succeeded |
| Corio | `0b82af8e-04f5-41cf-b99b-0c551a1bb41e` | Succeeded |
| Dova Pharmaceuticals | `ca30606a-4663-4a29-b4be-88d42692d66a` | Over-time (`Running`) |
| Ehave | `09cdf4ea-56d1-4de1-a46e-b7441157e27b` | Succeeded |

## Recommendation

Do not conclude that original PDFs solve the quality or latency problem.
Evidence grounding is consistently strong, but discovery, taxonomy accuracy,
latency, and token cost remain unsuitable for this broad all-obligations shape.
Before another paid run:

1. Add explicit HTTP connect/read timeouts and retry transient DNS failures
   without abandoning an already-submitted CU operation.
2. Persist CU operation IDs immediately and support resuming polling.
3. Narrow the obligation scope or segment contracts.
4. Build human-verified atomic gold aligned to the analyzer's output rather
   than relying only on CUAD clause labels.
5. Re-run a paired text/PDF sample only after the transport fixes, keeping
   actual service concurrency at one.

The analyzer used for this run was deleted after result recovery.
