# CU Migrate — Azure Content Understanding Preview-to-GA Migration Assistant

A migration tool that automates the transition from Azure Content Understanding Preview API to GA.

## Features

- **Resource-wide discovery** — scan one or all analyzers in a CU resource
- **Preview→GA transform** — rewrite analyzer definitions for the GA API
- **Knowledge source migration** — convert `trainingData` to `knowledgeSources`
- **Compatibility rules** — flag removed features (Pro mode, Face API, person directory)
- **Validation** — verify GA payloads before applying
- **Three execution modes** — dry-run, export, apply
- **Developer handoff** — Markdown reports, app checklists, Copilot prompt packs

## Quick Start

```bash
# Install
cd "CU GA Migration"
pip install -e .

# Set endpoint (or use --endpoint flag)
export CU_ENDPOINT="https://<your-resource>.cognitiveservices.azure.com"

# List analyzers
cu-migrate --endpoint $CU_ENDPOINT inventory

# Dry-run migration for all analyzers
cu-migrate --endpoint $CU_ENDPOINT migrate --mode dry_run

# Migrate specific analyzers and export artifacts
cu-migrate --endpoint $CU_ENDPOINT migrate -a my-analyzer -m export -o ./output

# Apply migration (creates new GA analyzers)
cu-migrate --endpoint $CU_ENDPOINT migrate -a my-analyzer -m apply -y
```

## Authentication

**Entra ID (recommended):** Uses `DefaultAzureCredential` — works with `az login`, managed identity, etc.

**Subscription key fallback:**
```bash
cu-migrate --endpoint $CU_ENDPOINT --key YOUR_KEY inventory
```

## Output Artifacts

After running a migration, the output directory contains:

| File | Description |
|------|-------------|
| `manifest.json` | Run metadata and summary counts |
| `<analyzer>-ga.json` | Proposed GA analyzer payload |
| `<analyzer>_source_backup.json` | Original preview definition backup |
| `migration_report.md` | Full migration report with findings |
| `app_checklist.md` | App integration checklist |
| `copilot_prompts.md` | Ready-to-use Copilot prompts for code changes |

## Finding Severities

| Severity | Meaning |
|----------|---------|
| 🟢 Auto-fixed | Automatically handled by the tool |
| 🟡 Needs review | Requires human judgment |
| 🔴 Not supported | Feature removed in GA — requires redesign |

## Development

```bash
pip install -e ".[dev]"
pytest
```
