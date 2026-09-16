# Prompt: Classify-and-Route Schema Design

Design a pipeline for mixed packets requiring different extraction schemas.
Use [the routing skill](../skills/generate-analyzer-classify-route.skill.md)
for command templates and [Agents.md §4.7](../../Agents.md#47-classify-and-route-pattern-contentcategories)
for authoritative technical rules. Prefer a single analyzer for one type.

## Context and evidence

- Selected `case\iterations\NNN`, hypothesis/baseline, expected/actual defects,
  and verified tracking bugs.
- Input types, distinguishing text anchors, page/segment boundaries, and
  required fields per type.
- Frozen packet and per-type sample inventory/hashes, reviewed truth,
  evaluator/version, and acceptance rules.
- API/profile/model, planned phases, cost budget, and authorized external
  dependencies, if any.

Follow [iteration workspaces](../../docs/iteration-workspaces.md). Keep customer
packets private. Snapshot all inner/outer schemas under `inputs\schemas\`;
preserve source and final resolved-reference hashes. Changes to pipeline,
corpus, or evaluation require the next number.

## Design contract

1. Inner analyzers use ordinary field schemas with semantic labels, proper
   row/document scope, explicit methods, and absent-source behavior.
2. The outer classifier uses `config.enableSegment: true` and
   `config.contentCategories`. No `fieldSchema` is needed when extraction is
   delegated.
3. Category descriptions identify distinguishing headings, labels, and
   structural/continuation cues. Contrast confusable types; avoid document
   colors/fonts or position-only criteria.
4. A category with `analyzerId` routes to an existing analyzer. Categories
   without it classify only and should not be scored as failed extraction.
5. Service identity comes from `cu analyzer create --name VERSIONED_ID`,
   not an assumed top-level schema identity property.
6. Keep routing shallow unless the selected API contract and testing justify
   more depth. Do not assume recursive document routing is available for video;
   evaluate temporal boundaries independently.

## Source aliases, not guessed IDs

Supply local schemas to the offline planner as `--schema ALIAS=FILE`. Outer
source schemas reference those aliases, including inherited analyzer aliases
in `baseAnalyzerId` when applicable:

```json
{
  "description": "Route invoices and receipts while retaining other classified segments",
  "baseAnalyzerId": "prebuilt-document",
  "config": {
    "enableSegment": true,
    "contentCategories": {
      "invoice": {
        "description": "Invoice heading, Invoice Number, item prices, and an Amount Due identify an invoice.",
        "analyzerId": "invoice"
      },
      "receipt": {
        "description": "Receipt heading, transaction date, and payment confirmation identify a receipt.",
        "analyzerId": "receipt"
      },
      "other": {
        "description": "Segments without sufficient invoice or receipt anchors; classification only."
      }
    },
    "omitContent": true
  },
  "models": { "completion": "gpt-4.1" }
}
```

With `--id-prefix packet_001`, the planner rewrites supplied aliases to
prefixed names and writes immutable snapshots/hashes plus `plan.json`.
`--external EXISTING_ID` permits an explicitly declared pre-existing
dependency; it does not grant ownership or validate service availability.
Classification-only categories do not need a dependency.

The planner is offline and does not create/delete analyzers. Review
dependency-first `commands.create` and reverse `commands.delete` arrays.
Execute the ordered **official `cu`** commands from the plan directory after
validation/authorization; stop on nonzero exit and record actual created IDs.
See the routing skill's checked PowerShell loop. Never delete all planned IDs
after an uncertain failure or remove external analyzers.

## Testing and decision

Predeclare individual-inner and full-packet phases. Test each inner on its
own type before submitting mixed packets to the outer. Run native local-file
or folder analysis; repeated comparisons use the experiment helper in
[Eval CU](../skills/eval-cu.skill.md). All service execution remains official
`cu`, with explicit cost approval.

Review:

- Correct category and page/segment boundaries, including continuation pages.
- Expected fields and retained rows for each routed type.
- Correct handling of classification-only/unknown content.
- Reviewed case correctness, false accepts, review/failures, and holdout scope.

Retain native raw results, statuses, and analyzer IDs; export/score offline
under `outputs\evaluation\`. Reports are execution statuses, not accuracy
or guaranteed per-file token/latency data. State denominators and raw/evaluator
sources. Missing usage/cost is unknown/null; priced usage is estimated.

Complete manifest/report and root navigation with expected/actual findings,
verified bugs, full pipeline cost (including inner checks), and the decision.
Category/fill rates alone are not STP. Replacing an inner requires a new
resolved outer version, not an in-place mutation of a completed pipeline.
