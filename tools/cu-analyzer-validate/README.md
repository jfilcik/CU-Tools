# CU-Analyzer-Validate Tool

Validate Content Understanding analyzer schemas before creating them on the service.

## Purpose

Validates that a schema file:
- Is valid JSON
- Meets CU service requirements
- Has proper field names and types
- Includes required fields (baseAnalyzerId, fieldSchema)
- Has well-formed array and object structures
- Provides helpful error messages for issues
- Warns about description quality issues

**Integration**: This validator is automatically run by `create_and_test.py` before creating analyzers.

## Installation

The validator is a standalone Python module with no external dependencies (uses standard library only).

```bash
cd tools/cu-analyzer-validate
# No additional installation required - uses standard library only
```

## Usage

### Validate Schema File
```bash
python cu_analyzer_validator.py ../../schemas/invoice_v1.json
```

or from the repository root:
```bash
python tools/cu-analyzer-validate/cu_analyzer_validator.py schemas/invoice_v1.json
```

### Validate and Test Create (Dry Run)
```bash
# Note: Test create functionality is not yet implemented
# Use create_and_test.py instead which validates then creates
python ../../tools/cu-analyzer-run/create_and_test.py \
  --schema ../../schemas/invoice_v1.json \
  --input ../../samples/ \
  --output ../../test_results/
```

### Validate Multiple Schemas
```bash
# From repository root
for schema in schemas/*.json; do
  python tools/cu-analyzer-validate/cu_analyzer_validator.py "$schema"
done
```

## Validation Checks

### 1. JSON Syntax
- Valid JSON format
- No syntax errors
- Proper encoding

### 2. Required Fields
- `description` present
- `fieldSchema` present
- `fieldSchema.fields` is an object

### 3. Field Names
- 1-64 characters long
- Start with letter or underscore
- Only letters, numbers, underscores allowed
- No spaces or special characters

### 4. Field Types
- Type is one of: string, number, boolean, array, object
- Array items have proper schema
- Object properties have proper schema
- Nested structures are valid

### 5. Base Analyzer
- If `baseAnalyzerId` specified, it's a valid prebuilt analyzer
- Valid options: prebuilt-document, prebuilt-invoice, prebuilt-receipt, etc.

### 6. Field Descriptions
- All fields have descriptions (warning if missing)
- Descriptions are non-empty
- Descriptions do not exceed maximum length (4096 characters)

### 7. Method
- `method` field is valid (extract, derive, etc.)
- Method is appropriate for field type

## Output Format

### Success
```
✅ Schema validation passed: schemas/invoice_v1.json

Validation Summary:
- JSON Syntax: ✅ Valid
- Required Fields: ✅ Present
- Field Names: ✅ Valid (5 fields checked)
- Field Types: ✅ Valid
- Base Analyzer: ✅ Valid (prebuilt-invoice)
- Descriptions: ✅ Present (5/5 fields)
- Methods: ✅ Valid

Schema is ready to create analyzer.
```

### Failure
```
❌ Schema validation failed: schemas/invoice_v1.json

Errors:
1. Field name "Invoice-Date" is invalid
   - Must start with letter or underscore
   - Cannot contain hyphens
   - Suggested: "InvoiceDate"

2. Field "TotalAmount" missing description
   - Descriptions help the model understand what to extract
   - Add: "description": "The total amount..."

3. Base analyzer "prebuilt-invoices" is invalid
   - Did you mean "prebuilt-invoice"?

Warnings:
1. Field "VendorAddress" has vague description
   - Current: "Vendor address"
   - Consider adding location hints and format examples
```

## CLI Options

The validator accepts a single file path as argument:
```bash
python cu_analyzer_validator.py <path_to_schema.json>
```

Exit codes:
- 0: Validation passed (may have warnings/info)
- 1: Validation failed (errors found)

## Examples

### Basic Validation
```bash
# From validator directory
python cu_analyzer_validator.py ../../schemas/invoice_v1.json

# From repository root
python tools/cu-analyzer-validate/cu_analyzer_validator.py schemas/invoice_v1.json
```

### Strict Mode (Fail on Warnings)
```bash
# Not currently supported via command line
# Use programmatically instead:
python -c "
from cu_analyzer_validator import validate_cu_analyzer_file
result = validate_cu_analyzer_file('schemas/invoice_v1.json')
if result.warnings:
    print('Warnings found - failing in strict mode')
    exit(1)
"
```

### Test Create on Service
```bash
# Use create_and_test.py which validates then creates
python tools/cu-analyzer-run/create_and_test.py \
  --schema schemas/invoice_v1.json \
  --input samples/ \
  --output test_results/
```

### Batch Validation with Report
```bash
# Validate all schemas and save output
for schema in schemas/*.json; do
  echo "Validating: $schema"
  python tools/cu-analyzer-validate/cu_analyzer_validator.py "$schema" > "validation_$(basename $schema .json).txt"
done
```

## Exit Codes

- 0: Validation passed
- 1: Validation failed (errors found)

## Integration

**Automatic validation in create_and_test.py:**

The validator is automatically run when you use `create_and_test.py`:

```bash
python tools/cu-analyzer-run/create_and_test.py \
  --schema schemas/my_schema.json \
  --input samples/ \
  --output test_results/
```

This tool will:
1. Validate the schema first
2. Display all errors and warnings
3. Stop if validation fails
4. Continue to create analyzer only if validation passes

**Manual validation before creating:**

```bash
# Validate first
python tools/cu-analyzer-validate/cu_analyzer_validator.py schemas/new_schema.json

# If exit code is 0, proceed to create
if [ $? -eq 0 ]; then
  python tools/cu-analyzer-run/create_and_test.py --schema schemas/new_schema.json ...
fi
```

## Dependencies

**None!** This validator uses only Python standard library modules:
- json (JSON parsing)
- re (regular expressions for field name validation)
- dataclasses (data structures)
- typing (type hints)
- enum (enumerations)
- pathlib (file path handling)

No external packages required.

## Implementation Status

- [x] README and structure
- [x] cu_analyzer_validator.py implementation
- [x] cu-analyzer-instructions.md guide
- [x] Integration with create_and_test.py
- [x] Command-line interface
- [x] Comprehensive validation checks
- [ ] Unit tests (future enhancement)

## Related Tools

- `cu-analyzer-run/create_and_test.py` - Creates and tests analyzers (uses this validator automatically)
- `cu-analyzer-run/run.py` - Runs analysis with existing analyzers

## Related Documentation

- `.github/prompts/generate-analyzer-schema.prompt.md` - Guide for creating valid schemas
- `.github/skills/generate-analyzer.skill.md` - Complete analyzer generation workflow
- `cu-analyzer-instructions.md` - Comprehensive schema creation guide
