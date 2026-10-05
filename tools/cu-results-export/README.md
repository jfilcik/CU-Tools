# Offline CU result export and field diagnosis

Export official `cu` JSON analysis results to CSV or Excel. This tool is
**offline**: it has no service client, CLI SDK dependency, or credentials.
Install/configure the official CLI using the [root README](../../README.md).

## Capture and export

From the repository root:

```powershell
cu analyze --source samples --analyzer ID --json --output-dir results --report-file batch-report.json --yes
python tools\cu-results-export\export.py --input results --output exports\results.csv
python tools\cu-results-export\export.py --input results --output exports\results.xlsx --diagnose
python tools\cu-results-export\export.py --input results --summary-only
```

The analysis source is each ordinary native CLI JSON result, saved as
`<input filename including extension>.result.json`. Native output may be a
direct payload with root `contents` or an LRO envelope with root
`id`, `status`, `result`, and `usage`, with contents under `result.contents`.
Both are native formats; an LRO envelope is not necessarily legacy output.
The CLI preserves source-relative directories. The separate report
(`schema: "cu-cli/analyze-report/v1"`) contains **status metadata**, not an
analysis document. Do not export it as if it held extracted fields.

For repeated experiments, point `--input` at the experiment's raw results
directory or enclosing experiment directory. Discovery is recursive and keeps
analyzer/trial/input path identity; it does not collapse repeated basenames.
`experiment.json` (planned matrix), `run.json` (execution/job state), and each
batch's `native-report.json` are metadata, not analysis inputs. They remain
separate evidence for attempted-input denominators and failed/missing jobs.
Already saved CU-Tools `{"result": {"contents": [...]}, "_metadata": {...}}`
envelopes and historical direct `result.fields` remain supported.

CSV needs only Python's standard library. Excel additionally needs:

```powershell
python -m pip install -r tools\cu-results-export\requirements.txt
```

## CLI options

| Option | Description |
|---|---|
| `--input`, `-i` | Result directory (recursive) or explicit JSON result |
| `--output`, `-o` | CSV or `.xlsx` output path |
| `--fields`, `-f` | Comma-separated export columns; category prefixes are included |
| `--summary-only` | Print summary without exporting |
| `--diagnose` | Field fill/confidence diagnosis; with output, save `.diagnosis.json` |

```powershell
python tools\cu-results-export\export.py --input results --output exports\selected.csv --fields invoice.Number,invoice.Total
```

Exports also write `<output stem>.summary.json`.
The CLI emits UTF-8 on stdout/stderr, including redirected Windows output.
Importing `export` as a library does not change the caller's stream encodings.

## Output and correctness

- One row per content entry, including classification-only entries. Empty or
  failed result files contribute an empty row, not invented successful values.
- Metadata columns: `run_id`, `document`, `result_file`, `status`, `category`,
  `iteration`, `timestamp`, `analyzer_id`. Unrecorded metadata is blank. A native
  result without a recorded status is **not** labelled succeeded.
- `result_file` is relative to the input directory and always distinguishes
  analyzer/trial paths. `document` preserves legacy document/source metadata;
  otherwise it uses that relative path with `.result.json` removed.
- Native `valueString`, `valueNumber`, `valueBoolean`, other `value*` scalars,
  `valueObject`, and `valueArray` are decoded along with legacy `value`/`values`.
  Objects use dotted columns; arrays become JSON cells containing decoded values.
- Field `.confidence`, `.source`, and `.spans` columns preserve recorded
  confidence/grounding. Array `._raw` columns preserve the original typed array,
  including nested item grounding/confidence. Raw inputs are never rewritten.
- Categories prefix field columns, preventing same-named category fields from
  overwriting each other. Arrays use indexed paths in field diagnostics.
- Fill rates count actual values: numeric zero and false are filled; null,
  missing and empty values are not. Empty/failed files stay in denominators.
  Diagnostics distinguish `present_count` from `confidence_count`; confidence
  is not an accuracy measurement. `total_docs` is the number of content rows
  (at least one per result), not necessarily unique source documents.
- Report-only failures/missing files have no analysis record to export. The
  experiment/report owner must use its manifest for attempted-input coverage;
  export statistics describe **discovered result files/content rows only**.
- Native CLI JSON may omit usage and per-file timings. This exporter does not
  invent either or parse human-readable `--usage` stderr.

## Offline loader contract

`cu_result_io.py` is a standard-library-only shared module used by export and
cost tools:

```python
from cu_result_io import load_results, normalize_result, result_payload

results = load_results("experiment")  # str or pathlib.Path
for envelope in results:
    payload = result_payload(envelope)  # native fields/contents
    identity = envelope["_metadata"]["result_file"]
```

- `load_results(input_path) -> list[dict]`: deterministic, recursive, deduplicated
  file discovery. Returns normalized envelopes with copied `_metadata`;
  adds `result_file` and a default `source_file` without inventing run IDs,
  iteration numbers, status, usage, or timing.
- `normalize_result(data) -> dict`: validates native direct/LRO or saved envelope
  shapes, preserving unknown properties and null/failed operation results.
- `result_payload(result) -> dict`: unwraps native LRO or saved envelopes; also
  accepts direct native payloads.
- `content_entries(result) -> list[(category, fields)]`: at least one entry
  per result, including empty entries; recorded non-success results yield no
  successful field values.
- `result_status(result) -> str | None`: recorded status, or `failed` for an
  explicit error; never infers success from contents.
- `result_usage(result) -> dict | None`: only structured root/envelope or nested
  result `usage`; no console parsing.

During directory discovery, known report/manifest/schema/summary/diagnosis/
comparison artifacts and unrecognized valid JSON are excluded. Native
`*.result.json` files always undergo result validation. Malformed JSON or an
invalid result-shaped payload raises `ResultFormatError` with its source path;
the CLI exits nonzero rather than quietly dropping damaged results.
An **explicitly selected** metadata or non-result JSON file is an error even if
it would be skipped during directory discovery.

## Offline tests

Run this suite in a separate Python process from other tool suites:

```powershell
python -m pytest tools\cu-results-export\tests -q --basetemp tools\cu-results-export\tests\.test-work -o cache_dir=tools\cu-results-export\tests\.pytest-cache
```
