# Prompt: Analyze Document Structure

Review CU layout evidence to identify text/structure anchors and propose
extraction fields. This is an offline review unless new analysis is explicitly
authorized.

## Context to supply

- Selected case and `iterations\NNN` (private for customer material).
- Document type and desired business outcome.
- Hypothesis/baseline, expected versus actual behavior, local defect IDs, and
  verified tracking bugs.
- Frozen input inventory/hashes and saved layout paths.

Follow [iteration workspaces](../../docs/iteration-workspaces.md) for
manifests/evidence and [Agents.md](../../Agents.md) for technical rules.
Reuse immutable prior layout when applicable; do not rerun or move evidence
just to change its folder format.

## Acquire layout only if needed

Official `cu` is the sole execution backend. After approval for the billable
scope, use this PowerShell template from the repository root:

```powershell
cu analyze "{document_path}" --analyzer prebuilt-layout --json `
  --api-version 2025-11-01 --yes --on-existing error `
  --output-dir "{iteration_folder}\outputs\raw\layout" `
  --report-file "{iteration_folder}\outputs\raw\layout-status.json"
```

For ordinary folders follow [Generate Analyzer](../skills/generate-analyzer.skill.md).
Read native `.result.json` files for structured content and returned markdown.
The CLI defaults to markdown without `--json`; one call does not promise both
file formats. Retain legacy saved layout as evidence without relabeling it.
CLI status reports are not documents and must not enter field statistics.

## Review tasks

1. **Structure:** headings, identifiers, sections, key-value pairs, tables,
   lists, signatures, footers, and repeated entities.
2. **Candidate fields:** identifiers, dates, parties, amounts, addresses, and
   row-level data. Distinguish extracted values from deterministic derivations.
3. **Variation:** optional/absent fields, label alternatives, column ordering,
   continuation pages, languages, and ambiguous formats.
4. **Challenges:** missing OCR text, separated labels/values, ambiguous party
   or section ownership, and content only present as an image.
5. **Evidence:** cite source file/page/segment and exact text anchors. Record
   suspected causes as hypotheses, not proven processing mechanisms.

Do not describe field sources by colors, fonts, or position alone. A logo
without corresponding extracted text is an evidence gap, not a reliable text
anchor. Repeated rows belong in arrays; totals belong at the proper scope.

## Required output

Write `{iteration_folder}\outputs\evaluation\document-structure.md` with:

- Scope and source links, distinguishing new analysis from offline review.
- Observed common structure and meaningful variations.
- A field proposal table:

| Field | Type/method | Text/structure anchor | Optionality/ambiguity | Source |
|---|---|---|---|---|
| InvoiceNumber | string/extract | Invoice Number or Invoice No. near invoice heading | Distinguish from order number | Actual evidence link |
| LineItems | array of objects/extract | Item, Quantity, Unit Price columns | Preserve continuation rows | Actual evidence link |

The table illustrates design, not measured findings for the current inputs.

Include expected/actual defects, cause status, questions evidence cannot
answer, and a next schema hypothesis. Link the output in manifest/report,
retain raw results unchanged, and record any layout cost. Missing usage/cost
stays unknown/null; offline review is not a new extraction result.

Continue with [Generate Analyzer Schema](generate-analyzer-schema.prompt.md).
