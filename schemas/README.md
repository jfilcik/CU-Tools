# Schemas Directory

This directory contains Content Understanding analyzer schemas for testing and iteration.

## Available Schemas

### invoice_v1.json
**Baseline version with minimal field descriptions**

- VendorName
- VendorAddress
- InvoiceNumber
- InvoiceDate
- TotalAmount
- Items (array)

**Purpose**: Establish baseline performance metrics

**Limitations**: Descriptions lack location hints, aliases, and format expectations

### invoice_v2.json
**Improved version with enhanced descriptions**

- Enhanced all field descriptions with:
  - Location hints
  - Format examples
  - Common label variations
  - Edge case handling

**Purpose**: Demonstrate improvement from enhanced descriptions

### invoice_v3_improved.json (NEW)
**Following Azure Content Understanding Best Practices**

Enhanced with all Azure best practices:
- ✅ **Detailed descriptions** with location hints, format expectations, and examples
- ✅ **All aliases included**: Lists all possible labels ("May be labeled as...")
- ✅ **Affirmative language**: Describes what field IS, not what it ISN'T
- ✅ **Structured arrays**: Proper array of objects with complete property definitions
- ✅ **Method specification**: Explicit `extract` method for all fields
- ✅ **Confidence tracking**: `estimateSourceAndConfidence` enabled on all fields
- ✅ **Config section**: Includes `returnDetails` and `estimateFieldSourceAndConfidence`
- ✅ **Better field names**: More descriptive (ItemDescription, LineTotal vs generic names)

**Key Improvements over v1/v2**:
- VendorName: Now includes "From:", "Vendor:", "Supplier:", "Seller:" aliases and examples
- InvoiceDate: Specifies to NOT extract due date, includes multiple format examples
- TotalAmount: Clarifies to extract FINAL amount, not subtotals, with specific label examples
- LineItems: Each property has detailed description with aliases and examples
- All fields: Include 2-3 concrete examples of expected values

**Purpose**: Demonstrate best practices from Azure Content Understanding documentation

## Azure Content Understanding Best Practices

When creating new schemas, follow these principles:

### 1. Write Detailed Descriptions
- Include location hints: "typically found at the top right corner"
- Specify format: "Format is usually MM/DD/YYYY or DD-MM-YYYY"
- List alternatives: "May be labeled as 'Invoice Date', 'Billing Date', or 'Issue Date'"
- Provide examples: "Examples: '01/15/2024', 'INV-2024-001'"

### 2. Include All Aliases
List all possible names the field might appear under

### 3. Use Affirmative Language
- ✅ "The date when goods were delivered, found in delivery section"
- ❌ "This isn't the invoice date and isn't the due date"

### 4. Match Language to Content
Use same language as your documents (e.g., Italian fields for Italian documents)

### 5. Use Structured Types
Use arrays of objects for repeated data, not strings requesting JSON

### 6. Specify Methods
Always set `extract`, `generate`, or `classify`

### 7. Enable Confidence Tracking
Set `estimateSourceAndConfidence: true` for important fields

### 8. Iterative Improvement
Start with descriptions, then add training examples if needed

## Schema Naming Convention

Use semantic versioning for schemas:
- `{analyzer_type}_v{major}.json` - e.g., `invoice_v1.json`
- `{analyzer_type}_v{major}.{minor}.json` - e.g., `invoice_v1.1.json`
- `{analyzer_type}_v{major}_improved.json` - for best practices versions

## Creating New Schemas

1. Review Azure best practices in `.github/prompts/generate-analyzer-schema.prompt.md`
2. Use `invoice_v3_improved.json` as a reference template
3. Follow all 8 best practices listed above
4. Validate using `python tools/cu-analyzer-validate/cu_analyzer_validator.py schemas/your_schema.json`
5. Test using `python tools/cu-analyzer-run/create_and_test.py`
6. Iterate based on results

## Related Resources

- **Best Practices Guide**: `.github/prompts/generate-analyzer-schema.prompt.md`
- **Field Writing Guide**: `.github/prompts/write_schema_fields.prompt.md`
- **Complete Guide**: `tools/cu-analyzer-validate/cu-analyzer-instructions.md`
- **Validation Tool**: `tools/cu-analyzer-validate/cu_analyzer_validator.py`
