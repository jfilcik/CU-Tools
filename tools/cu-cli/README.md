# cu-cli

A unified command-line interface and Python operations layer for running
**actual operations against the Azure AI Content Understanding (CU) service** —
create/list/get/delete analyzers, analyze files/URLs, create/run classifiers,
and manage model deployment defaults.

`cu-cli` wraps the shared [`tools/cu-client`](../cu-client/README.md) HTTP
client (`AzureContentUnderstandingClient`) with small, tested,
poll-aware operations (`create_analyzer_and_wait`, `analyze_file_and_wait`,
`delete_analyzer_safe`, ...). It is the single place in CU-Tools where CU
service calls happen — other tools (`cu-analyzer-run`, `create_and_test.py`)
import `cu_cli.operations` rather than re-implementing create/poll/delete
logic themselves, while keeping their own responsibilities (schema
validation, scale/stability test orchestration, comparison reports, CSV
export, cost estimation, etc.) unchanged.

## Install

```bash
pip install -r requirements.txt
cp ../../.env.sample ../../.env   # then fill in AZURE_AI_ENDPOINT / AZURE_AI_API_KEY
```

## Use as a CLI

Run from this directory (so `cu_cli` is importable), or add this directory
to `PYTHONPATH`:

```bash
# Validate connectivity/auth
python -m cu_cli validate-setup --verbose

# Analyzers
python -m cu_cli analyzer list
python -m cu_cli analyzer get --analyzer-id my-analyzer
python -m cu_cli analyzer create --analyzer-id my-analyzer --schema ../../schemas/my_schema.json
python -m cu_cli analyzer delete --analyzer-id my-analyzer

# Analyze
python -m cu_cli analyze file --analyzer-id my-analyzer --input document.pdf --output result.json
python -m cu_cli analyze url --analyzer-id my-analyzer --url https://example.com/doc.pdf

# Classify-and-route
python -m cu_cli classifier create --classifier-id my-classifier --schema classifier_schema.json
python -m cu_cli classify --classifier-id my-classifier --input packet.pdf

# Model deployment defaults
python -m cu_cli defaults get
python -m cu_cli defaults set --model gpt-4.1=my-gpt41-deployment
```

Every command prints JSON to stdout (or writes it to `--output <file>`) and
exits non-zero on failure, so it composes well in scripts and CI.

## Use as a library

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path("tools/cu-cli")))
from cu_cli import operations as cu_ops

client = cu_ops.get_client()  # reads AZURE_AI_ENDPOINT / AZURE_AI_API_KEY / CU_API_VERSION
detail = cu_ops.create_analyzer_and_wait(client, "my-analyzer", schema_dict)
result = cu_ops.analyze_file_and_wait(client, "my-analyzer", Path("document.pdf"))
cu_ops.delete_analyzer_safe(client, "my-analyzer")
```

## What moved here from other tools

`tools/cu-analyzer-run/create_and_test.py` and `tools/cu-analyzer-run/run.py`
now call into `cu_cli.operations` for the actual service interaction
(create-analyzer-and-wait, analyze-and-wait, safe delete/cleanup) instead of
duplicating polling loops against `AzureContentUnderstandingClient` directly.
Everything else about those tools — schema validation, classify-and-route
DAG resolution, parallel batch processing, comparison reports, token-usage
extraction — is unchanged.

## Tests

```bash
pip install pytest
pytest tests/
```

- `tests/test_operations.py`, `tests/test_cli.py` — unit tests against a
  mocked `AzureContentUnderstandingClient` (no network calls, run in CI).
- `tests/test_integration_live.py` — end-to-end smoke test against a **live**
  CU resource. Skipped automatically unless `AZURE_AI_ENDPOINT` and
  `AZURE_AI_API_KEY` are set (see `requires_credentials` fixture). It
  creates a throwaway `prebuilt-document`-based analyzer, analyzes a sample
  file from `data/`, and deletes the analyzer — safe to run repeatedly, but
  it does incur real CU usage.
