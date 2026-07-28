# Ground truth

`prepare_cuad_eval.py` generates `cuad_clause_gold.jsonl` from official CUAD spans. Create `atomic_obligations_gold.jsonl` by manually annotating the six documents listed in `dataset/selection_manifest.json`.

Generated quotations are gitignored to avoid redistributing source contract text. The annotation contract is defined in `annotation_guidelines.md`.
