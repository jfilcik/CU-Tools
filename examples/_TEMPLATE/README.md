# Analyzer improvement case template

Copy this folder to create a public example or a **private** customer issue.
No customer repository or scaffold is required. Do not put customer data in
public CU-Tools.

From a CU-Tools checkout in PowerShell, choose a destination that does not
already exist:

```powershell
$destination = "..\my-private-case"
if (Test-Path $destination) { throw "Choose a new destination; do not overwrite a case." }
Copy-Item .\examples\_TEMPLATE $destination -Recurse
```

The [canonical v1 guide](../../docs/iteration-workspaces.md) applies when
viewing this template in CU-Tools. After copying outside the library, keep a
reference to that guide in your own checkout; the relative link above will
need updating.

## Purpose and problem

- Expected behavior: Not provided.
- Actual reported/observed behavior: Not provided.
- Business impact: Not provided.
- Goals, critical fields, acceptance rules, and cost budget: Not provided.
- Scope, holdout, and reviewed truth: Not provided.

Update these details and [the issue manifest](manifest.json). Record each
defect with expected/actual behavior and `unknown`, `suspected`, or `confirmed`
cause status; do not infer a cause from a symptom alone.

## Iterations

| Iteration | Hypothesis | Status | Evidence |
|-----------|------------|--------|----------|
| [001](iterations/001/manifest.json) | The selected analyzer can reproduce the reported behavior on the frozen input set. | Planned; not run | [Report](iterations/001/report.md) |

No analysis, evaluation, or paid API call has been performed by this template.
Empty output directories are placeholders, not run results. Cost is unknown,
not zero.

## Start the baseline

1. Add authorized documents to `inputs/documents/`, or retain an existing
   immutable `samples/` corpus. Inventory the selected files and SHA-256 hashes.
2. Put the exact schema in `iterations/001/inputs/schemas/`. Add reviewed truth,
   evaluator/version/configuration, corpus membership, and acceptance rules
   under the iteration's `inputs/`; link and hash them in its manifest.
3. Replace the generic hypothesis and fill the case goals before execution.
   Use `cu` for routine operations; use CU-Tools runners only for advanced
   orchestration, repeats, diagnostics, or their result bundles.
4. Obtain any required cost approval. Direct raw output to
   `iterations/001/outputs/raw/`, derived metrics/exports to
   `iterations/001/outputs/evaluation/`, and record exact sanitized commands
   and runtime identifiers.
5. Complete the [report](iterations/001/report.md) and manifest from evidence,
   including each iteration's cost status/basis. Synchronize the root index.
6. Start `002` for the next hypothesis/configuration/dataset/metric change.
   Set its `baseline_iteration`, preserve `001`, and update navigation.

JSON paths use `/` relative to the containing manifest. Link only existing
artifacts; leave planned input/output lists empty until files are supplied.
Repeated trials (`--iterations 10`) remain inside one numbered experiment.
Fill rate/confidence alone cannot establish straight-through processing.
