# Ground truth

`prepare_cuad_eval.py` generates `cuad_clause_gold.jsonl` from official CUAD spans
for the standalone quality reports. For optional manual atomic-obligation
review, create `atomic_obligations_gold.jsonl` by annotating the six documents
listed in `dataset/selection_manifest.json`.

The standalone reports do not consume these atomic annotations or calculate
party-role, completeness, or weighted atomic-obligation scores. Manual review
must not be represented as a passing automated evaluation.

Generated quotations are gitignored to avoid redistributing source contract text. The annotation contract is defined in `annotation_guidelines.md`.
