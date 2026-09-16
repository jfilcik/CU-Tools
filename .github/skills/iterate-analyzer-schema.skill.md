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

Use [the canonical v1 format](../../docs/iteration-workspaces.md) and
[copyable template](../../examples/_TEMPLATE/), not a separate iteration
layout. Select the case and next unused number before creating artifacts.

```text
case/
|-- manifest.json
|-- README.md
|-- inputs/documents/
`-- iterations/
    `-- 001/
        |-- manifest.json
        |-- inputs/
        |   |-- schemas/
        |   `-- ...             # Inventory, truth, evaluator and rules
        |-- outputs/raw/
        |-- outputs/evaluation/
        `-- report.md
```

The initial baseline is iteration `001`; candidates set `baseline_iteration`
to a prior ID. Preserve existing shared samples/legacy evidence in place and
link them with provenance rather than relabeling them as a new run. Snapshot
and hash submitted schemas; inventory/hash every input and version evaluator,
truth, and acceptance policy. Changes to hypothesis, configuration, dataset,
or metrics start a new number. `--iterations N` is N trials within that number.
Link verified product bugs in the root and relevant iteration `bugs` arrays,
separately from local defects; follow [tracking bugs](../../docs/iteration-workspaces.md#tracking-bugs).

## Workflow

### 1. Establish the baseline

Record:

- API version, model, region, analyzer schema, and exact command;
- representative corpus and data classification;
- reviewed expected outcomes kept outside schema prompts;
- successful, failed, and retried attempt counts and source run IDs;
- correctness, null, variant, array-row, segment, latency, and token metrics
  with explicit denominators and evidence sources;
- per-iteration cost status/amount/basis, including billable repeated trials.

When consistency is the goal, plan at least five repeated trials per document
subject to explicit cost approval; do not launch a paid corpus automatically.

### 2. Define tracked behavior

Separate metrics into:

1. **Correctness**: exact or rule-based reviewed expectations.
2. **Stability**: population, distinct values, and array/segment count drift.
3. **False positives**: semantically wrong fallback or cross-field leakage.
4. **Coverage**: row, segment, and repeated-entity retention.
5. **Efficiency**: latency, token use, and cost (estimated versus actual charges).
6. **Diagnostics**: field source and confidence coverage.

For repeated entities, evaluate each row or segment and the document aggregate.
For STP claims, define eligible scope and a held-out evaluation of critical
correctness, false accepts, review, failures, and business-rule gates. Field
fill/confidence is not a proxy for case-level automatic correctness.

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

Use official `cu` for routine individual operations; keep `run.py` for repeat
trials/diagnostics and `create_and_test.py` for lifecycle or routing
orchestration. Those runners retain their legacy REST backend and bundle.
Save exact sanitized commands, tool git/version, API/model, runtime IDs,
metadata, and raw JSON under the selected iteration's `outputs/raw/`.
Put derived comparisons/exports under `outputs/evaluation/`, never over raw
baseline results.

### 6. Apply promotion gates

A candidate is promotable only when:

- every required trial completed successfully;
- all critical correctness rules pass;
- false-positive leakage does not increase;
- protected fields do not regress;
- required row and segment coverage passes;
- schema descriptions pass the anti-hard-coding review.

Efficiency improvements cannot compensate for correctness regressions. Failed
documents fail closed for acceptance; mark incomplete comparison evidence
inconclusive rather than treating absent output as a correct null value.

### 7. Design the next iteration

Use failure evidence from the complete corpus to choose the next hypothesis.
Change only the smallest coherent field family needed to test it. Rerun the
entire corpus; do not rerun only the document that motivated the change.

Set a safety cap before starting. Stop when all gates pass or the cap is
reached, then document the safest candidate and unresolved blockers.

### 8. Publish evidence

Maintain:

- the root manifest's iteration index, refreshed from authoritative iteration
  manifests (hypothesis, result summary, status, and path);
- the root defect list with expected/actual behavior and evidence-backed
  unknown/suspected/confirmed cause status;
- a per-iteration report with schema links, machine-readable comparison, raw
  results, runtime/tokens, cost status/basis, and promotion decision.

Record every iteration's cost, including failures. Price-based calculations
remain estimated; unknown costs are null, not zero. Optional `findings.md`
may curate reusable lessons with source links and contradictions, never
replace immutable inputs or raw evidence.

## Success criteria

- Baseline and raw results remain immutable.
- Every candidate is reproducible from a manifest and exact command.
- Correctness and stability are measured across the full corpus.
- Promotion decisions are deterministic and machine-readable.
- Schema prompts remain generic as the corpus and template variation grow.
- Each iteration's cost and limitations are visible; root navigation matches it.
