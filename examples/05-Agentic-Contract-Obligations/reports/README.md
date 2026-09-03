# Reports

`evaluation/generate_accuracy_report.py` writes `overall_accuracy.md`, JSON, and CSV reports here. Generated reports are ignored until reviewed for source quotations and sensitive content.

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
