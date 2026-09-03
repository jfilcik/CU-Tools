# Preview agentic API: successful-result quality

**Verdict: mixed behavior, but not good enough overall.**

The three completed contracts show that the analyzer can produce highly
source-grounded evidence. They do not show acceptable obligation discovery or
classification quality. This is a survivor-only view and must not be read as a
15%-completion reliability result or as representative of all 20 contracts.

## Successful-result scorecard

| Metric | Successful contracts only | Assessment |
|---|---:|---|
| Completed contracts | 3 | Very small, survivor-biased sample |
| Predicted obligations | 293 | High output volume |
| Mapped CUAD gold clauses | 149 | Benchmark target |
| Matched clauses | 30 | Low |
| Clause precision | 10.2% | Poor |
| Clause recall | 20.1% | Poor |
| Clause F1 | 13.6% | Poor |
| Type accuracy on 30 matches | 63.3% | Needs improvement |
| Exact quote groundedness | 327/333 (98.2%) | Strong |
| Obligations with evidence | 293/293 (100.0%) | Strong |
| Mean evidence-to-gold overlap on matches | 84.9% | Strong |

The direct answer is **no: the successful outputs are not broadly good yet**.
Their evidence behavior is good, but the analyzer misses many benchmark clauses
and emits many obligations that do not align to a CUAD target.

## Contract-level results

| Contract | Minutes | Predicted | Gold | Matched | Precision | Recall | F1 | Type accuracy | Quote groundedness |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `buffalowildwingsinc-06-05-1998-ex-10-3-franchise-d3ecacf8` | 17.6 | 79 | 74 | 19 | 24.1% | 25.7% | 24.8% | 63.2% | 98.9% |
| `corioinc-07-20-2000-ex-10-5-license-and-hosting--9425f23a` | 19.5 | 63 | 38 | 5 | 7.9% | 13.2% | 9.9% | 60.0% | 97.3% |
| `dovapharmaceuticalsinc-20181108-10-q-ex-10-2-114-93a7191f` | 18.2 | 151 | 37 | 6 | 4.0% | 16.2% | 6.4% | 66.7% | 98.2% |

Only the Buffalo Wild Wings result reached even 20% F1. The Dova result
produced more than four obligations per mapped gold clause while matching six,
which is the clearest sign of granularity mismatch or over-production.

## Interpretation limits

CUAD labels review clauses in 32 mapped categories, while this analyzer asks for
every atomic duty, prohibition, conditional duty, and surviving duty across a
broader 15-type taxonomy. A valid predicted obligation can therefore lack a
CUAD gold counterpart, and one CUAD clause can split into multiple atomic
obligations. This makes the 10.2% precision an imperfect measure of business
usefulness.

That mismatch does not explain the low 20.1% recall: 119 of 149 mapped clauses
in the completed contracts still had no match at the configured threshold.
Party-role accuracy and obligation completeness also remain unscored because
the atomic gold set has not been human-verified.

## Latency and token cost of successes

| Contract | Minutes | Input tokens | Output tokens |
|---|---:|---:|---:|
| Buffalo Wild Wings | 17.6 | 618,210 | 134,613 |
| Corio | 19.5 | 487,476 | 144,327 |
| Dova | 18.2 | 742,105 | 135,932 |
| **Total** | **55.3** | **1,847,791** | **414,872** |

The completed calls averaged 18.4 minutes, 615,930 input tokens, and 138,291
output tokens. They also reported 132,000 contextualization tokens, for
2,394,663 total reported tokens across the three results. That latency and token
volume are too high for broad production processing in this shape.

## Why the full run took 17.33 hours

The run was **not serial**. `create_and_test.py` used a
`ThreadPoolExecutor(max_workers=3)` and submitted all 20 tasks to three workers.

If every request had honored the 1,800-second operation limit, even 20 full
timeouts in three-worker waves would take roughly 3.5 hours, plus setup and
cleanup. The observed 17.33 hours therefore cannot be explained by local
serialization.

The retained evidence supports this explanation:

1. Three successful requests occupied workers for 17.6-19.5 minutes.
2. Nine service operations reached the 30-minute operation timeout.
3. Six operations failed under service-reported 429 pressure.
4. Two polling connections eventually reset.
5. The client calls `requests.post` and `requests.get` without HTTP connect or
   read timeouts. The 1,800-second deadline is checked only between polling
   calls, so a blocked HTTP call can hold a worker far beyond 30 minutes.

The exact excess time cannot be apportioned because failed tasks did not record
per-task start/end timestamps. The most defensible conclusion is that parallel
transport stalls collapsed effective throughput; it was not intentionally
running one document at a time.

## Original document formats

The benchmark input was text reconstructed from each record's `context` in the
pinned GitHub `data.zip`. That ZIP contains only `CUADv1.json`, `test.json`, and
`train_separate_questions.json`; it contains no PDF, DOC, DOCX, or TXT files.

The official Hugging Face CUAD distribution separately contains 510 original
PDFs and 200 standalone TXT files at revision
`a3c393f5d103fd0c516374e4fdff676c8176dcb1`. It contains no DOC or DOCX files
in those document collections.

The same 20 held-out contracts have been matched by original CUAD title and
downloaded as PDFs to the ignored local directory:

`samples/downloaded-pdf/`

Its `download_manifest.json` records the pinned source path, source revision,
file size, and SHA-256 for every PDF. No Content Understanding API request was
started while preparing these files.
