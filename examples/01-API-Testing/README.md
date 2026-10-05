# Tutorial 01: Explore CU with the official CLI

Inspect analyzers, extract document layout, and run field extraction without
maintaining HTTP request files or a second client.

Follow the [root Quick Start](../../README.md#quick-start) to install the
official CLI and configure your own authorized CU resource. Run the examples
from the **CU-Tools repository root**. Profiles and authentication belong to
the official CLI; there is no tutorial-specific credential file.

## Inspect without analyzing documents

```powershell
cu --version
cu doctor
cu analyzer list --json
cu analyzer show prebuilt-layout
cu defaults show
```

These inspect your configured service. To preview file discovery locally
without a service call or writes:

```powershell
cu analyze .\examples\02-Invoice-Extraction\samples\invoice.pdf `
  --analyzer prebuilt-layout --output-dir .\cli-tutorial\layout --dry-run
```

## Extract layout and fields

Analysis incurs charges. Review the input scope and cost before executing;
use fresh output folders instead of silently reanalyzing existing results.

```powershell
cu analyze .\examples\02-Invoice-Extraction\samples\invoice.pdf `
  --analyzer prebuilt-layout --output-dir .\cli-tutorial\layout `
  --report-file .\cli-tutorial\layout-status.json --on-existing error

cu analyze .\examples\02-Invoice-Extraction\samples\invoice.pdf `
  --analyzer prebuilt-invoice --json --output-dir .\cli-tutorial\invoice `
  --report-file .\cli-tutorial\invoice-status.json --on-existing error
```

The first command saves markdown; the second saves native JSON, normally
`invoice.pdf.result.json`. Inspect the status report separately from the
extraction payload. Available analyzers and model mappings depend on your
resource; inspect failures instead of treating empty/missing output as success.

## Create a custom analyzer

```powershell
cu analyzer validate .\examples\02-Invoice-Extraction\schemas\invoice_v1.json --api-version 2025-11-01
cu analyzer create --name tutorial_invoice_v1 --schema .\examples\02-Invoice-Extraction\schemas\invoice_v1.json --api-version 2025-11-01
cu analyzer show tutorial_invoice_v1 > .\cli-tutorial\analyzer-snapshot.json

cu analyze .\examples\02-Invoice-Extraction\samples\invoice.pdf `
  --analyzer tutorial_invoice_v1 --json --output-dir .\cli-tutorial\custom `
  --report-file .\cli-tutorial\custom-status.json --on-existing error
```

Use a new versioned ID if this name already exists. Do not delete/recreate
someone else's analyzer. When explicitly cleaning up the analyzer you created,
use `cu analyzer delete tutorial_invoice_v1` and review its confirmation.

## Continue with evidence-based development

[Invoice extraction](../02-Invoice-Extraction/) adds schema design and reviewed
evaluation. [Video analysis](../03-Video-Analysis/) covers timestamp grounding.
For real investigations, copy the [case template](../_TEMPLATE/) into the
appropriate public/private workspace and preserve numbered experiments.

The former REST Client files are intentionally removed. The
[official CLI reference](https://github.com/Azure/content-understanding-toolkit/tree/main/cu-cli)
is the execution guide; use installed `--help` for version-specific features.
