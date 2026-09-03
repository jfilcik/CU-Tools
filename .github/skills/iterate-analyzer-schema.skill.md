---
name: iterate-analyzer-schema
description: Runs evidence-driven Azure AI Content Understanding schema experiments with immutable baselines, repeated trials, promotion gates, and linked reports. Use when users ask to improve analyzer consistency, compare schema versions, measure regressions, or iteratively tune extraction without hard-coding sample answers.
---

# Skill: Iterate Analyzer Schema

## Purpose

Use this workflow to improve a Content Understanding analyzer while preserving
causal evidence. Each iteration states one coherent hypothesis, runs the full
representative corpus repeatedly, evaluates correctness and stability, and is
promoted only when protected behavior does not regress.

For a new single-document analyzer, start with
`generate-analyzer.skill.md`. For packet segmentation and routing, also use
`generate-analyzer-classify-route.skill.md`.

## Required boundaries

- Keep customer samples, reviewed truth, schemas, raw results, and reports in
  the customer's private issue workspace.
- Keep reusable skills and generic tools in CU-Tools.
- Never place expected customer values in field descriptions.
- Never tune to file names, page numbers, customer names, coordinates, or one
  template's literal answers.
- Never overwrite baseline or prior-iteration raw results.
- Never use confidence or fill rate as a substitute for correctness.

## Workspace contract

```text
iterative-schema-improvement/
|-- README.md
|-- config/
|   |-- corpus.json
|   |-- acceptance-criteria.json
|   `-- tracked-fields.json
|-- baseline/manifest.json
|-- iterations/
|   `-- iteration-NNN/
|       |-- manifest.json
|       |-- hypothesis.md
|       |-- schemas/
|       |-- results/
|       |-- analysis/
|       `-- report.md
`-- reports/
    |-- experiments.md
    `-- issues.md
```

The baseline manifest points to preserved evidence; it does not copy or mutate
the baseline.

## Workflow

### 1. Establish the baseline

Record:

- API version, model, region, analyzer schema, and exact command;
- representative corpus and data classification;
- reviewed expected outcomes kept outside schema prompts;
- successful and failed run counts;
- correctness, null, variant, array-row, segment, latency, and token metrics.

Use at least five repeated runs per document when the goal is consistency.

### 2. Define tracked behavior

Separate metrics into:

1. **Correctness**: exact or rule-based reviewed expectations.
2. **Stability**: population, distinct values, and array/segment count drift.
3. **False positives**: semantically wrong fallback or cross-field leakage.
4. **Coverage**: row, segment, and repeated-entity retention.
5. **Efficiency**: latency and token use.
6. **Diagnostics**: field source and confidence coverage.

For repeated entities, evaluate each row or segment and the document aggregate.

### 3. State one coherent hypothesis

Good hypotheses describe a reusable semantic rule:

- bind a value to an exact label or same table column;
- separate two semantically different fields;
- represent repeated entities as arrays;
- split packet documents before scalar extraction;
- replace a lossy scalar with address lines or structured components;
- compute deterministic totals outside model extraction.

Do not bundle unrelated prompt changes merely to improve a score.

### 4. Review schema language

Field descriptions may contain:

- semantic labels and common label variants;
- party, section, row, and column boundaries;
- explicit exclusions for commonly confused fields;
- domain-valid normalization such as ISO currency or weight units;
- null behavior when the correct source is blank or absent.

Field descriptions must not contain:

- expected values copied from test documents;
- file names, customer names, page counts, or page numbers;
- coordinates or instructions tied to one layout;
- fallbacks between semantically different values;
- model arithmetic that can be performed deterministically after extraction.

### 5. Validate and execute

Validate every schema before creating analyzers. Pass preview API versions
explicitly. For classify-and-route:

- create inner analyzers before the classifier;
- use `config.enableSegment: true` with `contentCategories`;
- test inner analyzers independently;
- run the routed packet and verify segment boundaries;
- delete temporary analyzers after the run.

Save the command, manifest, metadata, and raw JSON for every experiment.

### 6. Apply promotion gates

A candidate is promotable only when:

- every required trial completed successfully;
- all critical correctness rules pass;
- false-positive leakage does not increase;
- protected fields do not regress;
- required row and segment coverage passes;
- schema descriptions pass the anti-hard-coding review.

Efficiency improvements cannot compensate for correctness regressions. Mark an
incomplete or failed run invalid rather than scoring missing output as null.

### 7. Design the next iteration

Use failure evidence from the complete corpus to choose the next hypothesis.
Change only the smallest coherent field family needed to test it. Rerun the
entire corpus; do not rerun only the document that motivated the change.

Set a safety cap before starting. Stop when all gates pass or the cap is
reached, then document the safest candidate and unresolved blockers.

### 8. Publish evidence

Maintain:

- an experiment ledger with hypothesis, exact changes, run count, gate result,
  lessons, next action, and links to raw evidence;
- an issue ledger with expected behavior, baseline and iteration rates,
  regression status, and detail links;
- a per-iteration report with schema links, machine-readable comparison, raw
  results, runtime/tokens, and promotion decision.

## Success criteria

- Baseline and raw results remain immutable.
- Every candidate is reproducible from a manifest and exact command.
- Correctness and stability are measured across the full corpus.
- Promotion decisions are deterministic and machine-readable.
- Schema prompts remain generic as the corpus and template variation grow.
