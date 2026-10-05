# Reviewed obligation golden set

`golden_obligations.jsonl` contains one reviewed record for each contract in
`dataset/selection_manifest.json`. Source contracts are materialized locally and
remain ignored by Git.

## Annotation scope

The gold set includes express duties, prohibitions, conditional duties, and
surviving duties imposed on contracting parties. It excludes:

- recitals and definitions;
- pure grants, rights, options, and remedies;
- factual statements and acknowledgements without a duty;
- duties imposed only on non-parties; and
- obligations inferred from commercial context rather than stated text.

Compound clauses are split when the obligor, action, trigger, timing, amount,
exception, or survival rule differs. Reciprocal duties are separate records.
Every record includes at least one exact source span with validated character
offsets.

## Review process

Five independent extra-high-reasoning contexts drafted two contracts each. A
separate extra-high-reasoning adjudication pass reread all ten contracts,
normalized scope and atomization, corrected the drafts, and validated hashes,
offsets, IDs, enumerations, and references.

This is a **model-assisted expert-style annotation**, not legal advice and not a
substitute for qualified legal-human review. A legal reviewer should approve it
before it is used as an external, contractual, or high-stakes benchmark.
