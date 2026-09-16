# Local CU-Tools compatibility layer

**This directory is not the official Azure CU CLI.** For routine operations,
install the official [`cu-cli` package](https://github.com/Azure/content-understanding-toolkit/tree/main/cu-cli)
and call `cu` directly. See the [root quick start](../../README.md#install-or-update-the-official-cu-cli)
for installation, updates, configuration, and command examples.

## Why this directory remains

`cu-analyzer-run/run.py` and `create_and_test.py` import this directory's
`cu_cli.operations` for create/analyze/classify/delete and polling. It wraps
the legacy [`tools/cu-client`](../cu-client/README.md) REST client; it does
**not** invoke the official CLI or use its SDK. Installing the official package
does not change the runners' backend.

Retaining this layer preserves complex workflows: diagnostics, run metadata,
scale/stability testing, and classify-and-route orchestration. Do not build
new routine-operation wrappers here when `cu` already supports the operation.
The legacy entry point is retained for existing callers, not recommended for
new interactive use.

## Avoid the package-name collision

Both this directory and the official package use the Python name `cu_cli`.
Use the official `cu` executable from the repository root or outside the repo.
Do not add `tools/cu-cli` to `PYTHONPATH` or run the official CLI from this
directory. In particular, `python -m cu_cli` here invokes the local wrapper,
whose commands and flags differ from the official CLI.

The runners deliberately load this local package for compatibility. A future
backend migration must preserve their diagnostics and result contracts; a
package installation alone is not such a migration.

## Configuration and results

The local layer loads `.env` and reads `AZURE_AI_ENDPOINT`,
`AZURE_AI_API_KEY`, and `CU_API_VERSION`. The official CLI uses `CU_ENDPOINT`,
`CU_API_KEY`, `CU_AUTH_MODE`, and saved configuration instead; it does not
automatically load the repository `.env`.

Official CLI result files are not identical to CU-Tools result bundles. Keep
using the runners for downstream evaluation/export expecting their envelopes,
run metadata, and usage summaries.

## Tests

Run from the repository root with the CU-Tools dependencies and pytest installed:

```powershell
# Offline unit tests for the local layer, not the official CLI
python -m pytest tools\cu-cli\tests -m "not integration" -v

# Explicit live test run: incurs real CU usage
python -m pytest tools\cu-cli\tests\test_integration_live.py -m integration -v
```

The live tests load the repository `.env` and skip when endpoint/key credentials
are absent. When configured, they read defaults, list analyzers, and create a
temporary analyzer, analyze the checked-in invoice sample, and attempt cleanup.
Run them only against an intended test resource. Running the whole test
directory without excluding `integration` also enables live tests when
credentials are present.

These tests cover the **legacy runner backend**. They do not demonstrate that
CU-Tools delegates to the official CLI. For the official CLI's own tests and
supported options, use the upstream toolkit documentation.
