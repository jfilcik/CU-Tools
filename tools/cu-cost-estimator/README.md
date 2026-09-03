# Azure AI Content Understanding Cost Estimator

A Python tool for estimating and analyzing costs for Azure AI Content Understanding services.

## Overview

This cost estimator supports two estimation modes:

1. **Usage-based estimation** (Recommended): Use actual token counts from API responses for the most accurate cost calculations
2. **Schema-based estimation**: Estimate costs based on schema configuration when you haven't run test cases yet

> ⚠️ **Important**: For production cost planning, always validate estimates by running representative test files through the actual Azure Content Understanding service and using the returned usage data for calculations. Schema-based estimates are approximations and may vary significantly from actual costs.

## Installation

```bash
# From the repository root
pip install -r requirements.txt
```

## Table of Contents

- [Quick Start](#quick-start)
- [Quick Reference](#quick-reference)
- [Estimation Modes](#estimation-modes)
- [Supported File Types](#supported-file-types)
- [Supported Models](#supported-models)
- [Cost Breakdown](#cost-breakdown)
- [CLI Examples](#cli-examples)
- [Batch Analysis](#batch-analysis)
- [Cost Optimization Tips](#cost-optimization-tips)
- [Running Tests](#running-tests)
- [Troubleshooting](#troubleshooting)

## Quick Start

### Python API

```python
from tools import CostEstimator, ProcessingRequest, UsageData, SchemaConfig

estimator = CostEstimator()

# Option 1: Usage-based estimation (RECOMMENDED - most accurate)
usage = UsageData(
    input_tokens=1_100_000,
    output_tokens=60_000,
    contextualization_tokens=1_000_000,
    document_pages_standard=1000
)
request = ProcessingRequest(
    file_type="document",
    quantity=1000,
    model_name="gpt-4o-mini",
    deployment_type="global",
    usage_data=usage
)
breakdown = estimator.estimate_cost(request)
print(f"Total cost: ${breakdown.total_cost:.2f}")

# Option 2: Schema-based estimation (when no usage data available)
schema = SchemaConfig(
    num_fields=10,
    field_complexity="moderate",
    source_grounding_enabled=True,
    confidence_scores_enabled=True
)
request = ProcessingRequest(
    file_type="document",
    quantity=1000,
    model_name="gpt-4o-mini",
    schema_config=schema
)
breakdown = estimator.estimate_from_schema(request)
print(f"Estimated cost: ${breakdown.total_cost:.2f}")
print(f"Confidence: {breakdown.confidence_note}")
```

### Command Line Interface

#### Estimate Cost

```bash
# Basic estimate with default model
python cost_estimator.py estimate --file-type document --quantity 1000

# Specify model and deployment type
python cost_estimator.py estimate --file-type document --quantity 1000 \
    --model gpt-4o-mini --deployment global

# Schema-based estimation
python cost_estimator.py estimate --file-type document --quantity 1000 \
    --schema-fields 10 --schema-complexity moderate

# Output as JSON
python cost_estimator.py estimate --file-type document --quantity 1000 --json
```

#### Usage-Based Estimation (Recommended)

```bash
# From CU analyzer output JSON file (easiest - automatically extracts usage)
python cost_estimator.py estimate-usage \
    --cu-output "Issues/MyProject/results/document.json" \
    --model gpt-4o-mini

# Manual token counts
python cost_estimator.py estimate-usage \
    --input-tokens 1100000 --output-tokens 60000 --ctx-tokens 1000000 \
    --pages 1000 --model gpt-4o-mini

# Scale to different volume
python cost_estimator.py estimate-usage \
    --cu-output "path/to/result.json" \
    --scale-to 10000 \
    --model gpt-4o-mini
```

#### Batch Cost Analysis

```bash
# Analyze batch processing results from directory
python generate_cost_summary.py "Issues/MyProject/results/" --model gpt-4o-mini

# Save as JSON
python generate_cost_summary.py "Issues/MyProject/results/" --json --output costs.json

# Analyze results with different model configuration
python generate_cost_summary.py "Issues/MyProject/results/" \
    --model gpt-4o \
    --deployment data_zone
```

## Estimation Modes

### Usage-Based Estimation (Recommended)

Use this mode when you have actual token consumption data from the Azure Content Understanding API. This provides the most accurate cost estimates.

```python
# Parse usage from API response
api_response = {
    "documentPagesMinimal": 0,
    "documentPagesBasic": 0,
    "documentPagesStandard": 10,
    "contextualizationToken": 10000,
    "tokens": {
        "gpt-4.1-input": 26000,
        "gpt-4.1-output": 900
    }
}

usage = UsageData.from_api_response(api_response)

# Scale from test batch to production volume
request = ProcessingRequest(
    file_type="document",
    quantity=10000,  # Target: 10,000 pages
    model_name="gpt-4o-mini",
    usage_data=usage
)

# Scale factor automatically calculated: 10000 / 10 = 1000x
breakdown = estimator.estimate_from_usage(request, test_pages=10)
```

### Extracting Usage from CU Analyzer Output

The easiest way to get accurate cost estimates is to run your documents through the CU analyzer and use the `usage` object from the JSON output:

```python
from cost_estimator import extract_usage_from_cu_output, CostEstimator

# Extract usage data from CU analyzer output
usage_dict = extract_usage_from_cu_output("path/to/analyzer_output.json")

# Create usage data
usage = UsageData(
    input_tokens=usage_dict['input_tokens'],
    output_tokens=usage_dict['output_tokens'],
    contextualization_tokens=usage_dict['contextualization_tokens'],
    document_pages_standard=usage_dict['document_pages']
)

# Estimate cost
estimator = CostEstimator()
request = ProcessingRequest(
    file_type="document",
    quantity=usage_dict['document_pages'],
    model_name="gpt-4o-mini",
    usage_data=usage
)
breakdown = estimator.estimate_from_usage(request)
print(f"Estimated cost: ${breakdown.total_cost:.6f}")
```

**Supported CU Output Format:**
```json
{
  "usage": {
    "documentPagesStandard": 10,
    "contextualizationTokens": 10000,
    "tokens": {
      "gpt-4.1-input": 26000,
      "gpt-4.1-output": 900
    }
  }
}
```

### Batch Cost Analysis

Analyze multiple CU analyzer results to get total costs and per-document averages:

```bash
# Generate cost summary for all results in a directory
python generate_cost_summary.py "Issues/MyProject/results/"
```

This will:
- Process all JSON files in the directory
- Extract usage data from each file
- Aggregate statistics (total tokens, pages, costs)
- Calculate per-document and per-page costs
- Display in human-readable format

Output includes:
- **Batch Information**: Total documents and pages processed
- **Cost Breakdown**: By component (content extraction, field extraction, contextualization)
- **Per-Unit Costs**: Cost per document and per page
- **Token Usage**: Average and total token consumption
- **Cost Projections**: Estimated costs at different scales

### Schema-Based Estimation

Use this mode when you want to estimate costs before running any test files. Provide your schema configuration and the estimator will approximate token usage.

```python
schema = SchemaConfig(
    num_fields=15,                    # Number of fields to extract
    field_complexity="complex",       # simple, moderate, or complex
    source_grounding_enabled=True,    # Adds ~50% more output tokens
    confidence_scores_enabled=True,   # Adds ~50% more output tokens
    extractive_mode=True,             # Copy exact text from source
    avg_field_value_length=50         # Average characters per field value
)

request = ProcessingRequest(
    file_type="document",
    quantity=1000,
    model_name="gpt-4o",
    schema_config=schema
)

breakdown = estimator.estimate_from_schema(request)
```

> ⚠️ Schema-based estimates are marked as **LOW confidence**. Always validate with actual usage data before production deployment.

## Supported File Types

| File Type | Content Extraction Cost | Contextualization Tokens |
|-----------|------------------------|-------------------------|
| `document` | $5.00 per 1,000 pages | 1,000 tokens per page |
| `image` | Free | 1,000 tokens per image |
| `audio` | $0.006 per minute | 1,667 tokens per minute |
| `video` | $0.0167 per minute | 16,667 tokens per minute |
| `text` | Free | Based on character count |

## Supported Models

| Model | Class | Input Cost (Global) | Output Cost (Global) |
|-------|-------|--------------------|--------------------|
| `gpt-4o` | Regular | $2.50/M tokens | $10.00/M tokens |
| `gpt-4o-mini` | Mini | $0.15/M tokens | $0.60/M tokens |
| `gpt-4.1` | Regular | $2.00/M tokens | $8.00/M tokens |
| `gpt-4.1-mini` | Mini | $0.40/M tokens | $1.60/M tokens |
| `gpt-4.1-nano` | Nano | $0.10/M tokens | $0.40/M tokens |

Data Zone deployments are ~10% more expensive than Global/Regional.

## Cost Breakdown

The estimator provides detailed cost breakdowns:

```python
breakdown = estimator.estimate_cost(request)

print(f"Content Extraction: ${breakdown.ce_cost:.4f}")
print(f"Contextualization:  ${breakdown.ctx_cost:.4f}")
print(f"LLM (Field Extraction): ${breakdown.fe_cost:.4f}")
print(f"Total Cost: ${breakdown.total_cost:.4f}")
print(f"Cost per Page: ${breakdown.cost_per_unit:.6f}")
print(f"Estimation Mode: {breakdown.estimation_mode}")
print(f"Confidence: {breakdown.confidence_note}")
```

## Running Tests

The test suite validates cost calculations against the [Microsoft pricing documentation](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/pricing-explainer).

```bash
# Run all tests
pytest tools/tests/test_cost_estimator.py -v

# Run specific test class
pytest tools/tests/test_cost_estimator.py::TestDocumentationPricingExample -v

# Run with coverage
pytest tools/tests/test_cost_estimator.py --cov=tools --cov-report=term-missing
```

### Test Categories

| Test Class | Description |
|------------|-------------|
| `TestPricingConfig` | Validates pricing rates match documentation |
| `TestDocumentationPricingExample` | Tests the invoice example from MS docs |
| `TestUsageBasedEstimation` | Tests usage-based cost calculations |
| `TestSchemaBasedEstimation` | Tests schema-based estimations |
| `TestContentExtractionCosts` | Tests CE costs for all file types |
| `TestContextualizationCosts` | Tests contextualization token calculations |
| `TestModelComparison` | Compares costs between models |
| `TestBatchAnalysis` | Tests batch processing analysis |
| `TestEdgeCases` | Tests error handling and edge cases |

## Batch Analysis

Analyze results from processing multiple files:

```python
results = [
    {
        "file_name": "invoice1.pdf",
        "file_type": "document",
        "pages": 10,
        "actual_input_tokens": 26000,
        "actual_output_tokens": 900,
        "model_name": "gpt-4o-mini",
        "deployment_type": "global"
    },
    # ... more results
]

analysis = estimator.analyze_batch_results(results)

print(f"Total documents: {analysis['summary']['total_documents']}")
print(f"Total pages: {analysis['summary']['total_pages']}")
print(f"Avg tokens/page: {analysis['averages']['input_tokens_per_page']:.0f}")
print(f"Total cost: ${analysis['summary']['total_cost']:.2f}")
```

## Batch Results JSON Format

When analyzing batch results, provide a JSON file with this structure:

```json
[
  {
    "file_name": "invoice_2024_Q1.pdf",
    "file_type": "document",
    "pages": 45,
    "actual_input_tokens": 117000,
    "actual_output_tokens": 4050,
    "model_name": "gpt-4o",
    "deployment_type": "global"
  },
  {
    "file_name": "contract.pdf",
    "file_type": "document",
    "pages": 120,
    "actual_input_tokens": 312000,
    "actual_output_tokens": 10800,
    "model_name": "gpt-4o",
    "deployment_type": "global"
  }
]
```

See `example_batch_results.json` in the repository root for a complete example.

## CLI Examples

### Compare Models

```bash
# Compare gpt-4o vs gpt-4o-mini for 10,000 pages
python -m tools.cost_estimator --file-type document --quantity 10000 --model gpt-4o
python -m tools.cost_estimator --file-type document --quantity 10000 --model gpt-4o-mini
```

### Different File Types

```bash
# Document processing (1000 pages)
python -m tools.cost_estimator --file-type document --quantity 1000 --model gpt-4o

# Audio transcription (120 minutes)
python -m tools.cost_estimator --file-type audio --quantity 120 --model gpt-4o

# Video processing (30 minutes)
python -m tools.cost_estimator --file-type video --quantity 30 --model gpt-4o

# Image analysis (500 images)
python -m tools.cost_estimator --file-type image --quantity 500 --model gpt-4o
```

### Deployment Comparison

```bash
# Compare Global vs Data Zone
python -m tools.cost_estimator --file-type document --quantity 1000 --model gpt-4o --deployment global
python -m tools.cost_estimator --file-type document --quantity 1000 --model gpt-4o --deployment data_zone
```

## Cost Optimization Tips

- **Use mini models**: Save 85-95% on LLM costs by using `gpt-4o-mini` or `gpt-4.1-mini` for many use cases
- **Choose appropriate deployment**: Use Global/Regional instead of Data Zone unless data residency is required (~10% savings)
- **Batch processing**: Process documents in batches to get accurate per-page averages for cost projections
- **File type selection**: Use `text` type when possible (free content extraction)
- **Test before scaling**: Run representative test files first to get actual usage data for accurate estimates

## Pricing Reference

Based on [Azure AI Content Understanding Pricing](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/pricing-explainer):

- **Content Extraction**: $5.00 per 1,000 pages (documents)
- **Contextualization**: $1.00 per 1M tokens
- **Field Extraction**: Varies by model (see table above)

> **Note**: Pricing is subject to change. Always verify with official Azure pricing documentation for the most current rates.

## Troubleshooting

### "Model not found" error
Make sure you're using a supported model name exactly as listed (e.g., `gpt-4o-mini`, not `gpt4o-mini`).

### Unexpected cost estimates
Verify that:
- File type matches your actual content
- Quantity is in the correct units (pages for documents, characters for text, minutes for audio/video)
- Model name is spelled correctly

### Tests failing
If tests fail after an Azure pricing update:
1. Check the [official pricing documentation](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/pricing-explainer)
2. Update `PRICING_CONFIG` in `cost_estimator.py` with new rates
3. Update expected values in `tests/test_cost_estimator.py`

## Quick Reference

### Common Commands

```bash
# 1. Extract usage from CU output (most accurate)
python cost_estimator.py estimate-usage \
    --cu-output "Issues/MyProject/results/document.json" \
    --model gpt-4o-mini

# 2. Batch cost summary
python generate_cost_summary.py "Issues/MyProject/results/" --model gpt-4o-mini

# 3. Basic estimation (when no usage data available)
python cost_estimator.py estimate --file-type document --quantity 1000 --model gpt-4o-mini

# 4. Get JSON output
python cost_estimator.py estimate-usage \
    --cu-output "path/to/result.json" --model gpt-4o-mini --json
```

### Cost by Model (Per 1,000 Pages)

| Model | Per 1K Pages | Per 100 Docs (3.7 pages avg) |
|-------|--------------|------------------------------|
| gpt-4o-mini | ~$0.018 | ~$0.07 |
| gpt-4o | ~$0.054 | ~$0.20 |

### Usage Data Extraction

The easiest way to get accurate estimates is to use CU analyzer output:

```python
from cost_estimator import extract_usage_from_cu_output

# Extract from file
usage_dict = extract_usage_from_cu_output("result.json")
# Returns: {
#   'input_tokens': int,
#   'output_tokens': int,
#   'contextualization_tokens': int,
#   'document_pages': int,
#   'source_file': str
# }
```

### Example Results (WK K-1 Test - 22 documents, 82 pages)

```
Total Cost:           $0.51
Cost per Document:    $0.023
Cost per Page:        $0.006

Breakdown:
  Content Extraction: $0.41 (80%)
  Field Extraction:   $0.018 (3%)
  Contextualization:  $0.082 (17%)
```

### Production Projection

```bash
# Get per-document cost from single test
python cost_estimator.py estimate-usage \
    --cu-output "sample_result.json" --model gpt-4o-mini

# Then multiply by expected volume
# Cost per doc: $0.02 × 10,000 docs = $200
```

### Integration with Other Tools

```bash
# Export fields for comparison
python ../cu-results-export/export.py --input results/ --output fields.tsv --mode fields-only

# Export costs separately
python generate_cost_summary.py results/

# Correlate: accuracy vs. cost
```

### Optimization Tips Summary

1. **Use gpt-4o-mini**: 75% cheaper than gpt-4o
2. **Disable optional features**: Source grounding, confidence scores (~2x cost)
3. **Batch processing**: Amortize fixed content extraction cost
4. **Process text files**: Free content extraction (vs. $5 per 1,000 pages for documents)

## License

See [LICENSE](../../LICENSE) for details.

