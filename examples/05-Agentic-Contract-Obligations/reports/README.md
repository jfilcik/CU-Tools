# Reports

`evaluation/generate_broad_quality_report.py` and
`evaluation/generate_clause_span_report.py` generate standalone Markdown, JSON,
and CSV reports from official CLI status reports, saved `--json` CU results,
and public CUAD annotations (older `metadata.json` bundles remain readable). Use
`--output-prefix` or `--output`, respectively, to write new reports beneath
ignored `test_results/`; review them for source quotations and sensitive content
before sharing.

The CLI status report does not contain usage or timing measurements. Missing
measurements are explicitly unavailable, not zero; console `--usage`/`--time`
output is not parsed. Keep `analyze-report.json` beside its result files.

The retired private evaluation integration's weighted accuracy report is no
longer generated. The standalone reports do not score atomic party roles or
completeness.

The files below preserve historical measurements, including their recorded
region and workload facts. They are not prerequisites or default results for a
new run.

`heldout_20_quality.md` is the reviewed report from the 20-contract preview run.
Its adjacent ignored JSON and CSV files contain machine-readable metrics without
source contract text.

`heldout_20_successes.md` isolates extraction quality, latency, and token usage
for the three completed contracts and documents the original-PDF follow-up
dataset.

`pdf_5_quality.md` is the reviewed report for the five-original-PDF follow-up,
including paired text/PDF comparisons and recovered CU request IDs.

`clause_span_15_quality.md` is generated from the 15-document Agentic schema
aligned directly to the 31 mapped CUAD exact-span categories. Its execution time
sums active run windows and excludes pauses between retry commands.
