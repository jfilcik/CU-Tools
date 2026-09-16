# Official CLI experiments

A small **stdlib-only** helper for what official `cu` does not yet express:
repetitions of explicit files and comparisons across existing analyzers. The sole
CU backend is the installed **official `cu` executable**. There are no SDK imports,
REST clients, per-file threads, service retries, polling loops, or analyzer
creation/deletion in this helper.

For ordinary folder batching, use the CLI directly instead:

```powershell
cu analyze --source .\samples --recursive --analyzer invoice_v1 --json `
  --output-dir .\results --report-file .\batch-report.json --concurrency 5 `
  --api-version 2025-11-01 --yes --on-existing error
```

Install/upgrade the public PyPI `cu-cli` package as described in the repository
README. This helper was verified with **cu-cli 0.1.0b1** and the
`cu-cli/analyze-report/v1` report contract. It checks `cu --version` and required
`cu analyze --help` flags before a paid run. An incompatible/older `cu` fails with
installation guidance; the helper does not translate old dialects.

## Plan first: no service calls

```powershell
python .\tools\cu-experiments\experiment.py plan `
  --input ".\samples\invoice one.pdf" --input ".\samples\invoice two.pdf" `
  --analyzer invoice_v1 --analyzer invoice_v2 `
  --iterations 10 --concurrency 10 --output .\experiments\001 `
  --api-version 2025-11-01 --profile my-profile --usage
```

This plans **2 files × 2 analyzers × 10 trials = 40 submissions**. Use
`--iterations 5 --concurrency 5` for five parallel repetitions with one analyzer.
With multiple files, native CLI decides the order; repetitions are not synchronized
into rounds. `--concurrency` is the **global maximum simultaneous-request budget**
(1–32), not a guarantee that all slots stay busy.

Only explicit regular local `--input FILE` arguments are accepted. Directories,
URLs/network paths, symlinks/junctions, duplicate files/hard-link aliases,
case-colliding analyzer IDs, and names skipped by CLI discovery are rejected.
Different files with the same basename are safe: each gets a distinct input
directory. Analyzer IDs may be custom letters/digits/underscores (up to 64
characters) or `prebuilt-*` IDs. Planning rejects an existing output directory.

Each file is copied independently per trial and SHA-256 hashed; changing or deleting
the original afterward does not change the planned inputs. The full matrix,
expected output paths, CLI argument arrays, API version, profile name, and process
slot allocations are frozen in `experiment.json`. The plan does not invoke `cu`,
authenticate, read CLI profiles/credentials, or create analyzers.

Schema snapshots are **not supported** in this initial focused helper. The manifest
explicitly records that analyzer schema identity, resource identity, and model
mappings are **unverified**. Use versioned analyzer IDs and preserve source schemas
in your experiment documentation; analyzer lifecycle remains direct `cu` work.
The default API version is GA `2025-11-01`; preview must be explicit.

## Run once: explicit paid approval

```powershell
python .\tools\cu-experiments\experiment.py run .\experiments\001 --confirm-cost `
  --cu-executable .\.venv\Scripts\cu.exe
```

Omit `--cu-executable` to use official `cu` on PATH. Pass an executable path, not
a quoted command containing additional arguments or a `.cmd`/`.bat` wrapper.
Argument arrays and `shell=False` preserve paths with spaces without shell
interpolation. Normal CLI environment/profile authentication is inherited, never
copied into the manifest. There are no endpoint/key/token options here.

**Every planned submission may be billed.** `--confirm-cost` approves the printed
total, not a dollar ceiling. No prices or token counts are estimated. Missing
normalized usage/cost/service latency is always `null`/unknown. Native payload
usage, when present (for example `documentPagesStandard`), is retained verbatim
without inventing a token/cost schema. The optional plan `--usage` also asks `cu`
to print its own usage evidence; logs are preserved but not parsed into normalized
metrics. Treat all raw artifacts/logs as potentially sensitive.

Before execution the helper validates the entire manifest, command templates,
matrix, hashes, copied-file identities, and absence of prior execution artifacts.
It persists `run.json` in `running` state exclusively before any paid command.
**Any attempted run is single-use**, including interrupted, failed, partial, and
inconclusive runs. No resume, overwrite, skip, automatic retry, or implicit rebilling:
create a fresh numbered experiment and consciously approve its cost.

One native `cu analyze --source inputs --recursive ...` batch runs per analyzer.
At most `min(analyzers, global concurrency)` process slots run together. The budget
is split between slots, and each slot runs its assigned analyzer batches serially.
For example, two analyzers with budget five receive **3 + 2**, never five each.
With five analyzers and budget two, only two native batches run at once, each with
`--concurrency 1`. Allocations are recorded in both the plan and execution report.
Only the CLI schedules individual files and owns HTTP retries and polling.

Ctrl+C/SIGTERM terminates the CLI child processes started by this helper, retains
logs/results, and records interruption. **Terminating a client does not cancel
server-side operations or undo charges.** A forced OS kill may leave `running`
state; never assume it is safe to repeat. No process/service timeout is offered.

## Evidence and success rules

```text
experiments\001\
  experiment.json                         Immutable plan and full expected matrix
  inputs\trial-0001\input-0001\invoice.pdf  Independent frozen copy (each trial/input)
  run.json                                State, CLI capability evidence, allocations,
                                          incremental batch outcomes, per-job reconciliation
  batches\analyzer-0001\
    native-report.json                    Untouched native CLI JSON status report
    stdout.txt                            Raw CLI stdout
    stderr.txt                            Raw CLI stderr, including optional usage
    results\trial-0001\input-0001\invoice.pdf.result.json
```

Raw `.result.json` bytes are never rewritten. The helper accepts both a direct
analyzer payload with root `contents` and the native CLI LRO envelope:
`{"id": "...", "status": "Succeeded", "result": {"analyzerId": "...",
"contents": [...]}, "usage": {"documentPagesStandard": 1}}`. The envelope must
declare success; its nested result gets the same validation as a direct payload.
Envelope usage and all other fields are preserved unchanged. This native envelope
is **not** the old CU-Tools metadata contract. Native reports have `schema`,
`analyzer`, `result_view`, `counts`, and per-input `results`
(`input`, `analyzer`, `status`, and `output` for successes).

Every expected matrix job must match a native report entry and the planned output.
Missing/malformed reports or output JSON, duplicate/unexpected entries/files,
wrong analyzers/paths/counts, skipped inputs, and service errors are not successes.
A nonzero CLI exit invalidates otherwise successful jobs in that batch. Partial
evidence remains available with explicit failed/inconclusive statuses and a
nonzero helper exit. Success means **execution/output integrity**, not extraction
accuracy, schema equivalence, field coverage, or a statistical comparison.

## Offline verification

```powershell
python -m unittest discover -s .\tools\cu-experiments\tests -v
python .\tools\cu-experiments\tests\verify_public_cli_dry_run.py `
  --cu-executable .\.venv\Scripts\cu.exe
```

Unit tests use mocked CLI processes and synthetic files. The separate opt-in
verification runs the actual public CLI with precisely the generated arguments,
replacing `--yes` with `--dry-run` (the CLI forbids both together). It isolates CLI
configuration in an empty project-local directory, removes credential-related
environment variables, verifies no file writes, and cleans its synthetic fixtures.
Neither command performs a paid analysis or needs credentials.
