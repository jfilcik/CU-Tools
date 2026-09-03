# Cost Estimator Test Suite

This document provides detailed explanations of each test case to help reviewers verify that the expected values are correct based on the [Azure AI Content Understanding Pricing Documentation](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/pricing-explainer).

## Running Tests

```bash
# Run all tests
pytest tools/tests/test_cost_estimator.py -v

# Run with detailed output
pytest tools/tests/test_cost_estimator.py -v --tb=long

# Run specific test class
pytest tools/tests/test_cost_estimator.py::TestDocumentationPricingExample -v
```

---

## Test Classes Overview

| Test Class | Tests | Purpose |
|------------|-------|---------|
| `TestPricingConfig` | 4 | Validate pricing constants match MS documentation |
| `TestDocumentationPricingExample` | 4 | Test the invoice example from MS docs |
| `TestUsageBasedEstimation` | 3 | Validate usage-based estimation logic |
| `TestSchemaBasedEstimation` | 4 | Validate schema-based estimation logic |
| `TestContentExtractionCosts` | 5 | Test CE costs for all file types |
| `TestContextualizationCosts` | 4 | Test contextualization token calculations |
| `TestModelComparison` | 2 | Compare model pricing tiers |
| `TestBatchAnalysis` | 2 | Test batch result aggregation |
| `TestAutoEstimationModeSelection` | 3 | Test automatic mode selection |
| `TestEdgeCases` | 3 | Test error handling |
| `TestTextConversion` | 2 | Test text-to-page conversion |

---

## TestPricingConfig

These tests verify that the hardcoded pricing values match Microsoft's documentation.

### `test_content_extraction_rates`

**Source**: [Pricing Explainer - Content Extraction](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/pricing-explainer)

| Rate | Expected Value | Verification |
|------|---------------|--------------|
| Document pages | $5.00 per 1,000 pages | From "Content extraction" section |
| Audio | $0.006 per minute | From "Audio/Video" section |
| Video | $0.0167 per minute | From "Audio/Video" section |

### `test_contextualization_rates`

**Source**: Contextualization section of pricing docs

| Rate | Expected Value | Verification |
|------|---------------|--------------|
| Regular model tokens | $1.00 per 1M tokens | All models use same CTX rate |
| Mini model tokens | $1.00 per 1M tokens | All models use same CTX rate |

### `test_contextualization_units`

**Source**: "Contextualization tokens" table in pricing docs

| Content Type | Tokens per Unit | Verification |
|--------------|-----------------|--------------|
| Document page | 1,000 tokens | "1 Page = 1,000 contextualization tokens" |
| Image | 1,000 tokens | "1 Image = 1,000 contextualization tokens" |
| Audio (per minute) | 1,667 tokens | 100,000 per hour ÷ 60 = 1,667 |
| Video (per minute) | 16,667 tokens | 1,000,000 per hour ÷ 60 = 16,667 |

### `test_model_pricing_gpt4o_mini`

**Source**: Azure OpenAI pricing / Content Understanding pricing

| Rate | Expected Value | Verification |
|------|---------------|--------------|
| Input tokens (Global) | $0.15 per 1M | Current gpt-4o-mini pricing |
| Output tokens (Global) | $0.60 per 1M | Current gpt-4o-mini pricing |

---

## TestDocumentationPricingExample

These tests reproduce the **Invoice Field Extraction** example from the MS documentation.

### Scenario
- **Task**: Extract fields from 1,000 invoice pages
- **Model**: GPT-4o-mini
- **Deployment**: Global

### `test_invoice_example_content_extraction`

**Calculation**:
```
Content Extraction = Pages × Rate per 1,000 pages
                   = 1,000 × ($5.00 / 1,000)
                   = $5.00
```

**Expected**: `$5.00`

### `test_invoice_example_contextualization`

**Calculation**:
```
Contextualization Tokens = Pages × Tokens per page
                        = 1,000 × 1,000
                        = 1,000,000 tokens

Contextualization Cost = Tokens × Rate per 1M tokens
                       = 1,000,000 × ($1.00 / 1,000,000)
                       = $1.00
```

**Expected**: `1,000,000 tokens`, `$1.00`

### `test_invoice_example_with_actual_usage`

This test uses actual token counts from the documentation example:

| Metric | Per Page | Total (1,000 pages) |
|--------|----------|---------------------|
| Input tokens | 1,100 | 1,100,000 |
| Output tokens | 60 | 60,000 |
| CTX tokens | 1,000 | 1,000,000 |

**LLM Cost Calculation** (with current gpt-4o-mini rates):
```
Input Cost  = 1,100,000 × ($0.15 / 1,000,000) = $0.165
Output Cost = 60,000 × ($0.60 / 1,000,000)    = $0.036
FE Cost     = $0.165 + $0.036                 = $0.201
```

**Expected**:
- CE Cost: `$5.00`
- CTX Cost: `$1.00`
- FE Cost: `$0.201` (approximately)
- Mode: `usage_based`

### `test_invoice_example_documentation_rates`

The MS documentation example uses illustrative rates that differ from current Azure pricing. This test validates the calculation logic using the exact rates shown in the docs:

| Rate (from docs) | Value |
|------------------|-------|
| Input tokens | $0.40 per 1M |
| Output tokens | $1.60 per 1M |

**Calculation**:
```
Content Extraction:   $5.00
Contextualization:    $1.00
Input (1.1M × $0.40/M):  $0.44
Output (60K × $1.60/M):  $0.096

Total: $5.00 + $1.00 + $0.44 + $0.096 = $6.536 ≈ $6.54
```

**Expected**: `$6.536` (within 2% tolerance)

---

## TestUsageBasedEstimation

### `test_from_api_response`

Tests parsing the actual Azure Content Understanding API response format:

```json
{
  "documentPagesMinimal": 0,
  "documentPagesBasic": 0,
  "documentPagesStandard": 2,
  "contextualizationToken": 2000,
  "tokens": {
    "gpt-4.1-input": 10400,
    "gpt-4.1-output": 360
  }
}
```

**Expected parsed values**:
- Input tokens: `10,400`
- Output tokens: `360`
- CTX tokens: `2,000`
- Pages: `2`

### `test_scaling_from_test_to_production`

Tests scaling from a 10-page test batch to 1,000 pages:

| Metric | Test (10 pages) | Scaled (1,000 pages) | Scale Factor |
|--------|-----------------|----------------------|--------------|
| Input tokens | 11,000 | 1,100,000 | 100× |
| Output tokens | 600 | 60,000 | 100× |
| CTX tokens | 10,000 | 1,000,000 | 100× |

**Scale Factor**: `1,000 ÷ 10 = 100`

### `test_usage_based_has_high_confidence`

Verifies that usage-based estimates are marked as "High confidence" since they use actual token data.

---

## TestSchemaBasedEstimation

### `test_simple_schema`

Tests a simple schema with 5 fields and no advanced features:
- Should produce a cost > 0
- Should be marked as "schema_based" mode
- Should include "LOW confidence" warning

### `test_complex_schema_with_features`

Compares two schemas:

| Schema | Fields | Complexity | Features |
|--------|--------|------------|----------|
| Simple | 5 | simple | None |
| Complex | 20 | complex | source_grounding, confidence_scores, extractive_mode |

**Expected**: Complex schema cost > Simple schema cost

### `test_feature_multipliers`

Tests the token multiplier calculation:

| Features | Multiplier |
|----------|------------|
| None | 1.0× |
| source_grounding | 1.5× |
| confidence_scores | 1.5× |
| Both | 2.0× |

### `test_schema_output_token_estimation`

Compares output token estimates:

| Schema | Fields | Complexity | Avg Length | Expected |
|--------|--------|------------|------------|----------|
| Simple | 5 | simple | 20 chars | Lower |
| Complex | 20 | complex | 100 chars | Higher |

---

## TestContentExtractionCosts

### `test_document_content_extraction`

**Formula**: `Cost = Pages × ($5.00 / 1,000)`

| Pages | Calculation | Expected |
|-------|-------------|----------|
| 1,000 | 1,000 × $0.005 | $5.00 |
| 5,000 | 5,000 × $0.005 | $25.00 |
| 100 | 100 × $0.005 | $0.50 |

### `test_audio_content_extraction`

**Formula**: `Cost = Minutes × $0.006`

| Minutes | Calculation | Expected |
|---------|-------------|----------|
| 60 | 60 × $0.006 | $0.36 |

### `test_video_content_extraction`

**Formula**: `Cost = Minutes × $0.0167`

| Minutes | Calculation | Expected |
|---------|-------------|----------|
| 60 | 60 × $0.0167 | $1.002 |

### `test_text_content_extraction_free`

Text content extraction is free (no OCR/parsing needed).

**Expected**: `$0.00` for any quantity

### `test_image_content_extraction_free`

Image content extraction is free (images are passed directly to the model).

**Expected**: `$0.00` for any quantity

---

## TestContextualizationCosts

### `test_document_contextualization`

**Calculation**:
```
Tokens = 1,000 pages × 1,000 tokens/page = 1,000,000 tokens
Cost = 1,000,000 × ($1.00 / 1,000,000) = $1.00
```

### `test_image_contextualization`

**Calculation**:
```
Tokens = 500 images × 1,000 tokens/image = 500,000 tokens
Cost = 500,000 × ($1.00 / 1,000,000) = $0.50
```

### `test_audio_contextualization`

**Calculation**:
```
Tokens = 60 minutes × 1,667 tokens/minute ≈ 100,000 tokens
Cost = 100,000 × ($1.00 / 1,000,000) = $0.10
```

### `test_video_contextualization`

**Calculation**:
```
Tokens = 60 minutes × 16,667 tokens/minute ≈ 1,000,000 tokens
Cost = 1,000,000 × ($1.00 / 1,000,000) = $1.00
```

---

## TestModelComparison

### `test_mini_model_cheaper_than_regular`

Compares GPT-4o vs GPT-4o-mini for 1,000 document pages:

| Model | Input Rate | Output Rate | Expected |
|-------|------------|-------------|----------|
| gpt-4o | $2.50/M | $10.00/M | Higher cost |
| gpt-4o-mini | $0.15/M | $0.60/M | Lower cost |

**Expected**: Mini model should have >50% savings on LLM costs (docs claim "up to 80%")

### `test_data_zone_more_expensive`

Compares Global vs Data Zone deployment:

| Deployment | Rate Multiplier | Expected |
|------------|-----------------|----------|
| Global | 1.0× | Base cost |
| Data Zone | 1.1× | ~10% higher |

---

## TestBatchAnalysis

### `test_batch_analysis_averages`

Tests aggregation of multiple document results:

| Document | Pages | Input Tokens | Output Tokens |
|----------|-------|--------------|---------------|
| doc1.pdf | 10 | 26,000 | 900 |
| doc2.pdf | 20 | 52,000 | 1,800 |
| **Total** | **30** | **78,000** | **2,700** |

**Expected**:
- Total documents: `2`
- Total pages: `30`
- Avg pages/doc: `15.0`

### `test_empty_batch_returns_error`

Empty batch should return `{"error": ...}` instead of crashing.

---

## TestAutoEstimationModeSelection

### `test_selects_usage_based_when_usage_provided`

When `usage_data` is provided → mode = `"usage_based"`

### `test_selects_schema_based_when_schema_provided`

When `schema_config` is provided (no usage) → mode = `"schema_based"`

### `test_selects_default_when_neither_provided`

When neither is provided → mode = `"default"` (uses model defaults)

---

## TestEdgeCases

### `test_invalid_model_raises_error`

Invalid model name should raise `ValueError` with "not found" message.

### `test_zero_quantity`

Zero pages/images/minutes should return `$0.00` total cost.

### `test_ptu_deployment_no_token_cost`

PTU (Provisioned Throughput Unit) deployments have pre-paid capacity:
- LLM (FE) cost: `$0.00`
- Only content extraction costs apply

---

## TestTextConversion

### `test_text_to_pages_conversion`

**Formula**: `Pages = Characters / 3,000`

| Characters | Calculation | Expected Pages |
|------------|-------------|----------------|
| 3,000 | 3,000 / 3,000 | 1.0 |
| 6,000 | 6,000 / 3,000 | 2.0 |
| 1,500 | 1,500 / 3,000 | 0.5 |

### `test_text_processing_free_ce`

Text content extraction is free:
- Input: 30,000 characters (10 pages equivalent)
- CE Cost: `$0.00`

---

## Verifying Test Accuracy

To verify test values against the official documentation:

1. **Visit**: https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/pricing-explainer

2. **Check these sections**:
   - "Content extraction" for CE rates
   - "Contextualization" for token-per-unit conversions
   - "Field extraction" for model-specific rates
   - "Pricing example" for the invoice scenario

3. **Note**: Azure pricing changes periodically. If tests fail, check if the official rates have been updated and adjust `PRICING_CONFIG` accordingly.

## Known Discrepancies

The MS documentation example uses illustrative rates that may not match current Azure pricing:

| Item | Docs Example | Current Config |
|------|--------------|----------------|
| GPT-4o-mini input | $0.40/M | $0.15/M |
| GPT-4o-mini output | $1.60/M | $0.60/M |

The `test_invoice_example_documentation_rates` test uses a custom config with the doc rates to validate the calculation logic independently of current pricing.
