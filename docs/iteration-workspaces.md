# Issue iteration workspaces (v1)

CU-Tools turns a customer reproduction into **evidence-based analyzer
improvements and evaluation**, with cost accounted for at every iteration.
The aim is safe straight-through processing (STP), not simply a successful API
response or higher field fill rates.

This document is the canonical **workspace and manifest format** for new
public examples and private customer issues. [Agents.md](../Agents.md) remains
authoritative for CU API behavior and analyzer correctness. The
[generic template](../examples/_TEMPLATE/) works by manual copy; no customer
repository, browser, or additional framework is required.

## Boundaries and layout

Keep reusable tools, documentation, and approved public examples in CU-Tools.
Keep customer documents, repro details, truth labels, raw responses, and
customer-specific schemas in an appropriately restricted workspace, such as a
private customer repository. **Do not copy customer data into public CU-Tools.**
Removing a customer name alone does not make an artifact safe to publish.
Never record keys, bearer tokens, SAS query strings, or `.env` contents.

```text
case/
├── manifest.json                 # Issue, defects, and iteration index
├── README.md                     # Problem, goals, and navigation
├── inputs/documents/             # Immutable shared source corpus
├── iterations/
│   ├── 001/
│   │   ├── manifest.json         # Authoritative record of this experiment
│   │   ├── inputs/
│   │   │   ├── schemas/          # Exact schema snapshots
│   │   │   └── ...               # Corpus inventory, truth, evaluator/config
│   │   ├── outputs/
│   │   │   ├── raw/              # Untouched responses, run metadata, logs
│   │   │   └── evaluation/       # Derived metrics, exports, comparisons
│   │   └── report.md             # Evidence, cost, limitations, decision
│   └── 002/                      # Next hypothesis/configuration/scope
└── findings.md                   # Optional curated, source-linked learning
```

Existing `samples/` may serve as the immutable shared corpus. Do not move,
rewrite, or relabel old `layout_results/`, `test_results/`, or `reports/` as a
new run. Add links to legacy evidence and describe its known provenance and
gaps. Saved evidence remains usable; new execution uses the official CLI.

### What counts as an iteration?

`001`, `002`, ... identify experiments, not retries or repeated API calls.
Give each a one-sentence hypothesis and explicit baseline. A change to the
hypothesis, schema/configuration, model, dataset, ground truth, evaluator,
acceptance policy, or metric definition starts a **new number**. Never
overwrite a finished experiment. Planned records can be filled in before
execution; retain attempt-level evidence while a run is active.

`cu-experiments` with `--iterations 10` means ten repeated trials **inside one experiment**,
not ten numbered experiments. Record each trial and its failures/retries.
Scale (1×N) measures corpus coverage; stability (N×1) measures consistency.
Neither replaces a correctness evaluation against reviewed truth.

## Manifest contract

Both manifests are UTF-8 JSON objects with `schema_version: 1`. Keep IDs as
strings, including leading zeroes. Use JSON `null` for unknown execution
values or costs and empty arrays for artifacts/metrics not yet available.
Use nonempty ordinary text such as `"Not recorded"` or `"Not provided"` for
missing descriptive strings, not machine-interpreted sentinel values.
Problem/defect descriptions and the results decision must not be empty.
A planned manifest must not invent
filenames, run IDs, scores, or costs.

### Artifact links

Each entry in `links`, `inputs`, or `outputs` is:

| Key | Type | Meaning |
|-----|------|---------|
| `label` | string | Human-readable description |
| `path` | string | Existing file or directory, relative to **this manifest** |
| `role` | string | Descriptive role, e.g. `document`, `schema`, `ground_truth`, `evaluator`, `inventory`, `raw`, `evaluation`, `report`, `overview` |
| `sha256` | string, optional | SHA-256 of exact file bytes; not a directory hash |

Use **POSIX `/` separators inside JSON**, including on Windows. Shell
commands use the host's path syntax. Thus an iteration can link
`../../inputs/documents/document.pdf`; its report is simply `report.md`.
Resolve `..` inside the case boundary only. Do not use absolute paths, remote
URLs, or paths to another case as artifact links. Put tracked product bugs in
`bugs` as described below; other external references belong in the README/report,
with no credentials. Link only files that exist; planned
deliverables belong in report prose until created. A directory link is
navigation, not proof of a run. `.gitkeep` files only preserve empty folders.

Before executing, hash every selected document and schema. Shared documents
may remain at case root, but record the exact selected list, hashes, and
development/holdout membership; never rely on a mutable folder name. Snapshot
schemas into the iteration's `inputs/schemas/` and hash the final submitted
bytes, including resolved inner-analyzer references. List versioned ground
truth, evaluator source/configuration, and acceptance rules as input artifacts;
record external evaluator/tool versions and commits in execution metadata.

### Issue manifest: `case/manifest.json`

| Key | Type | Meaning |
|-----|------|---------|
| `schema_version` | integer | `1` |
| `kind` | string | `"issue"` |
| `id`, `title`, `customer`, `owner`, `opened`, `status` | strings | Case identity; record opening date when known; status is descriptive (e.g. `open`) |
| `slug` | string, optional | Stable readable URL identity, distinct from `id`; see [share slugs](#readable-share-slugs) |
| `summary` | string | Concise case purpose and current understanding |
| `problem` | object | `expected`, `actual`, `impact` strings; distinguish reports from verified observations |
| `goals`, `success_criteria` | string arrays | Desired outcome and predeclared acceptance gates |
| `defects` | object array | Each has `id`, `summary`, `expected`, `actual`, `cause_status`, `cause` strings |
| `bugs` | object array, optional | Explicit external tracking references; see [tracking bugs](#tracking-bugs) |
| `links` | artifact array | Case overview and supporting evidence/report navigation |
| `iterations` | object array | Each has `id`, `path`, `summary`, `result`, `status` strings |

`cause_status` is exactly `unknown`, `suspected`, or `confirmed`. Observing a
failure does not establish a root cause. Support confirmed causes with
reproduction/isolation evidence; use `defect_ids` to connect experiments.

For an index entry, `path` is `iterations/001/manifest.json`, `summary` copies
the iteration's `hypothesis`, `result` copies `results.summary`, and `status`
copies its status. This index is **denormalized navigation**; the iteration
manifest is authoritative. A scaffold's `refresh` operation regenerates it.
When copying the template manually, keep these fields synchronized yourself.

### Readable share slugs

An optional root-only `slug` provides a human-readable share URL without
changing the stable issue `id`. Its exact contract is a nonempty string
matching `^[a-z0-9]+(?:-[a-z0-9]+)*$`, maximum 120 characters.
Existing v1 manifests without it remain compatible. The public template
includes a clear placeholder slug; select a unique case-specific value before
sharing a copy.

The private scaffold derives and persists the slug **once** from the title:
replace non-ASCII-letter/digit runs with hyphens, lowercase, trim, and cap at
120 characters without a trailing hyphen. Titles without ASCII letters/digits
use `issue-` plus the first 12 characters of the generated issue ID.
Later title edits, refreshes or new experiments must not regenerate it.
The shared private helper exposes `validate_slug(value)` and
`make_slug(title, identifier)` in `tools/issue-workspace/workspace.py`
(`slug_from_title` remains a compatibility alias).

Local and static share links use readable directory routes, for example
`issues/invoice-extraction/iterations/001/`, relative to the site's deployment
base. Static exports generate an `index.html` at that path. Prefer these human-readable
URLs when sharing; old query-based URLs remain backward-compatible.
**Do not change a slug after sharing it.** A site's exporter must detect
duplicate slugs and refuse ambiguous exports; per-case validation checks
syntax, not uniqueness across a site.

When enriching legacy cases, a readable existing ID may be copied into `slug`
without changing the ID. Do not rewrite original evidence, snapshots,
migration plans or receipts to add this derived navigation metadata.

### Iteration manifest: `case/iterations/001/manifest.json`

| Key | Type | Meaning |
|-----|------|---------|
| `schema_version`, `kind` | integer, string | `1`, `"iteration"` |
| `id`, `title`, `hypothesis` | strings | Number, name, and one-sentence testable hypothesis |
| `status` | string | `planned`, `running`, `completed`, `blocked`, or `inconclusive` |
| `baseline_iteration` | string or null | An existing prior iteration ID, or `null` for the initial baseline |
| `defect_ids`, `changes` | string arrays | Case defect IDs and deliberate differences from baseline |
| `bugs` | object array, optional | Tracking bugs directly related to this experiment; same contract as issue-level `bugs` |
| `execution` | object | `command`, `api_version`, `model`, `analyzer_id`, `region`, `tool_version`, each string or null |
| `inputs`, `outputs` | artifact arrays | Reproducible inputs and produced evidence/report links |
| `results` | object | `summary`, `metrics`, `cost`, `decision`, `limitations` |

`results.summary` and `results.decision` are strings; `limitations` is a
string array. `metrics` contains objects with `name`, `value`, `unit` and,
where applicable, `denominator` and `source`. Use numeric values for measured
metrics; leave the list empty when nothing was measured. Make each rate's
denominator explicit (including excluded/failed documents), define units,
and set `source` to an existing evidence path relative to the iteration
manifest. Explain the metric calculation and scope in the report.

`execution.command` records the **exact sanitized command actually run**,
not a planned command. Record the working directory, all commands in order,
tool package version/git SHA, API/model/deployment, region, resolved analyzer
IDs, operation/request/run IDs, timestamps, timeouts, concurrency, retry
policy, attempt counts, and failure counts in linked execution metadata or
the report. Do not change the runners' output format to fit this manifest:
preserve their bundle under `outputs/raw/` and link its files.

`results.cost` always has:

| Key | Values |
|-----|--------|
| `status` | `unknown`, `estimated`, `measured`, `not_applicable` |
| `amount` | Nonnegative number, or `null` when not quantified/not applicable |
| `currency` | `"USD"` |
| `basis` | Explanation with evidence, price assumptions, scope, and exclusions |

Record cost **on every iteration**, including failed/incomplete ones.
Token/page usage multiplied by a price sheet is **estimated**, even if usage
was measured. Use `measured` only for actual attributable charge evidence;
state its source and coverage. Include billable layout, analysis, repeat,
retry, and evaluator calls, or identify omissions. `unknown` is not zero:
use `amount: null` and explain what is missing. `not_applicable` is for
explicitly offline-only work with no billable calls, not an unrun planned
analysis. Zero is valid only when substantiated. Cost/document, accepted
document, or STP case needs the matching denominator and cost scope.

### Tracking bugs

Issue and iteration manifests may both contain `bugs`. New templates/scaffolds
use `bugs: []`; existing v1 manifests without it remain compatible. Each entry:

| Key | Type | Meaning |
|-----|------|---------|
| `id` | nonempty string | Actual tracker ID, not a support case number |
| `title` | nonempty string | Recorded tracker title, or a source-backed descriptive label when the exact title is unavailable |
| `url` | nonempty string | Safe absolute HTTPS tracker link |
| `system` | string, optional | Tracker name, e.g. `azure-devops` or `github` |
| `status` | string, optional | Last observed tracker status, not a live assertion; omit if unknown |

Synthetic example, valid in either manifest:

```json
{
  "bugs": [
    {
      "id": "123",
      "title": "Synthetic example: missing invoice rows",
      "url": "https://dev.azure.com/example/project/_workitems/edit/123",
      "system": "azure-devops",
      "status": "New"
    }
  ]
}
```

URLs require a hostname and must not contain embedded credentials, control
characters, backslashes, or secret/signed query parameters, including encoded
forms. HTTP, protocol-relative, `javascript:` and `data:` links are invalid.
Ordinary tracker query parameters and anchors are allowed. Other bug strings
must also be free of control characters. Offline validation does not contact
the tracker or establish the link's factual relevance.
The private browser/exporter reuse `workspace.validate_bugs(items, label)`,
which returns `None` for valid arrays and raises `ValueError` otherwise.

Root references track the issue's relevant bugs. Add the same reference to
an iteration only when the evidence associates that bug with the experiment
or escalation; do not copy every issue bug into each new iteration.
Stable local `defects`/`defect_ids` are observations and are **not tracking bugs**.
Use actual filing receipts/context, not guessed IDs, URLs, customers, or status.
Keep receipts in the relevant iteration's `outputs/evaluation` and link them
as local artifacts. Enrich derived manifests without altering original
evidence, immutable snapshots, frozen migration plans or receipts.

When filing through the private customer-workspace skill, pass its `--issue`
and optional `--iteration` arguments to persist returned tracking metadata.
For a verified existing receipt, the private offline helper supports
`workspace.py link-bug ISSUE --id ID --title TITLE --url URL --system azure-devops --iteration NNN`.
`workspace.py validate ISSUE` checks `bugs` at both levels; `refresh` preserves
them without inferring bug associations.

### Status and completion

- `planned`: not run; execution may be null, metrics empty, report says so.
- `running`: active; retain all attempts and update evidence links.
- `completed`: planned execution/evaluation finished; **does not mean passed**.
  Record an accept/reject decision and limitations.
- `blocked`: cannot execute or finish; record the blocker and any incurred cost.
- `inconclusive`: evidence cannot support the comparison, such as incomplete
  trials or missing truth. Do not silently count missing outputs as successes.

## Workflow: repro to evidence to decision

1. **Intake.** Create a case from the template in the appropriate public/private
   location. Describe expected versus reported/observed behavior, impact,
   defects, owner, goals, and success criteria. Identify data permissions.
2. **Plan baseline `001`.** Choose the corpus, truth, protected fields,
   acceptance/review policy, evaluator, budget, and stopping condition.
   Document a hypothesis. Keep unrun records honest.
3. **Freeze inputs.** Snapshot/hash the schema, inventory/hash the exact
   documents, version truth/evaluator/rules, and separate development from
   holdout. Do not embed expected customer answers in schema descriptions.
4. **Validate and execute with approval.** Use official `cu` for every CU
   service operation, including native concurrent file/folder analysis. Check
   installed `--help`. Use the offline schema planner for dependency snapshots
   and `cu-experiments` only for immutable repeated trials/comparison matrices;
   it invokes native CLI batches within one global concurrency budget.
   Follow [CLI-only routing](../Agents.md#cli-only-operation-routing) for
   credentials, safe updates, result contracts, and cost approval. Link the
   experiment's full expected matrix, native reports, and raw results. Save all
   output beneath the selected iteration, never a mutable `latest` directory.
5. **Evaluate.** Preserve raw responses unchanged. Put derived exports,
   evaluator outputs, and baseline comparisons under `outputs/evaluation/`.
   Count successes, failures, retries, and excluded inputs explicitly; failed
   documents fail closed for acceptance. Record quality, latency, usage, and
   cost with denominators and evidence sources.
6. **Decide and close.** Complete `report.md` and `results`, link actual
   artifacts, synchronize the root index, and validate paths/hashes. State
   accept/reject/inconclusive with protected behavior and budget checks.
   Unknown costs or missing holdout evidence must remain visible.
7. **Improve in `002+`.** Link the prior baseline, identify addressed defects
   and exact changes, and repeat the fixed comparison before broadening
   scope. A broader corpus, new metric, or new evaluation policy is a new
   experiment. Keep finished evidence immutable.

### Evidence required for an STP claim

Predeclare the eligible population and review/acceptance rules. Measure at
document or business-case level, with reviewed truth and all critical fields,
row/segment coverage, business checks, and exceptions:

- **Verified STP rate:** correctly completed cases requiring no human
  intervention / all eligible attempted cases. An automatic acceptance
  count alone is not verified STP.
- **False-accept rate:** incorrectly auto-accepted cases / all auto-accepted
  cases, including the audit coverage and sampling limits.
- **Review rate:** cases routed to humans / all eligible attempted cases;
  report failures/rejections separately so missing output is not hidden.
- **Scope and generalization:** development versus held-out counts, document
  variants, exclusions, critical-field correctness, latency, and cost.

Global field fill/confidence is diagnostic, **not STP evidence**. A small
repro set can show a fix for those inputs, not production readiness. Without
reviewed truth or a representative holdout, label any STP estimate unverified.

## Optional private customer-workspace helpers

These commands belong to the separate **CU-Issue-Testing** repository, not
CU-Tools. They are convenience tools for this same contract. Run from that
repository's root; a public example can simply use the manual template.

- `.github\skills\create-customer-issue\scripts\create_issue.py` creates the
  root issue and planned iteration `001`. Check its `--help` for intake
  arguments. Its default root remains `Issues` for compatibility; pass
  `--issues-dir "CU Issues"` explicitly to select that root.
- `tools\issue-workspace\workspace.py` manages subsequent iterations:

```powershell
python tools\issue-workspace\workspace.py new-iteration "CU Issues\case" --title "Refine label anchoring" --hypothesis "Explicit label anchors reduce cross-field leakage." --schema .\candidate.json --input "CU Issues\case\inputs\documents\document.pdf" --baseline 001
python tools\issue-workspace\workspace.py validate "CU Issues\case"
python tools\issue-workspace\workspace.py refresh "CU Issues\case"
python tools\issue-browser\serve.py --root "CU Issues" --port 8765
```

`--schema` and `--input` may be repeated. `--schema` takes an existing source
file and copies a snapshot into the new iteration. `--input` references and
hashes an existing file **inside the case**; it does not import or copy
external documents. Place authorized documents in the case first, then pass
their existing paths. Omit `--baseline` only when no prior baseline applies.
The browser is navigation,
not an evaluation or proof that a run occurred. Refresh regenerates root
index summaries from iteration manifests; it must not invent measurements.

## Design rationale: evidence log plus curated learning

Raw inputs and responses are immutable sources; numbered iterations are the
experiment log. An optional `findings.md` is a small, curated synthesis with
links back to source iterations, scope, promotion decisions, and contradictory
evidence. Promote only supported reusable lessons; mark superseded or
contradicted claims instead of erasing their provenance. This makes the
workspace useful to humans and LLMs without replacing evidence with prose,
claiming an external standard, or adding a wiki framework.
