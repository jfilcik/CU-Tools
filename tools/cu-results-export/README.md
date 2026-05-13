# CU Results Export Tool

> **Status**: ✅ IMPLEMENTED  
> **Last Updated**: 2026-01-26

Export Content Understanding analysis results to CSV or Excel format with a wide table structure.

## Purpose

Flatten nested JSON analysis results into a tabular format for easy analysis in spreadsheets or data tools.

## Output Format

The export produces a **wide table** with:
- **Rows**: One row per document × iteration
- **Columns**: Metadata columns + one column per extracted field

| run_id | document | iteration | timestamp | InvoiceNumber | InvoiceDate | VendorName | Total |
|--------|----------|-----------|-----------|---------------|-------------|------------|-------|
| run_001 | invoice_a.pdf | 1 | 2026-01-26T10:00:00Z | INV-1234 | 2026-01-15 | Acme Corp | 1500.00 |
| run_001 | invoice_a.pdf | 2 | 2026-01-26T10:01:00Z | INV-1234 | 2026-01-15 | Acme Corp | 1500.00 |

## Installation

```bash
cd tools/cu-results-export
pip install -r requirements.txt
```

## Usage

### Export to CSV
```bash
python export.py --input ../../Issues/MyProject/test_results/run_001/ --output results.csv
```

### Export to Excel
```bash
python export.py --input ../../Issues/MyProject/test_results/run_001/ --output results.xlsx
```

### Export specific fields only
```bash
python export.py --input results/ --output results.csv --fields InvoiceNumber,InvoiceDate,Total
```

### View summary without exporting
```bash
python export.py --input results/ --summary-only
```

## CLI Options

| Option | Description |
|--------|-------------|
| `--input`, `-i` | Input directory with JSON results or single JSON file (required) |
| `--output`, `-o` | Output file path (.csv or .xlsx) |
| `--fields`, `-f` | Comma-separated list of fields to include (default: all discovered fields) |
| `--summary-only` | Print summary statistics without exporting |

## Output Files

When exporting, the tool creates:
1. **results.csv** or **results.xlsx** - The main export file
2. **results.summary.json** - Summary statistics including fill rates for each field

## Fill Rates

The summary includes fill rate percentages showing what percentage of rows have values for each field. This helps identify:
- Fields that are always populated
- Fields with low extraction rates (may need schema improvements)
- Fields that are optional vs required

## Dependencies

See `requirements.txt`:
- openpyxl (Excel support)
