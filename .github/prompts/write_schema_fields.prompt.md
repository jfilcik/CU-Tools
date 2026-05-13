# Prompt: Write Schema Fields

## Goal

Author or refine field descriptions, types, and examples for a Content Understanding analyzer schema.

## Context

- **Current Schema**: [Path to existing schema or "new schema"]
- **Fields to Add/Modify**: [List of fields]
- **Known Issues**: [Any current problems with field extraction]

## Guidelines

### Field Naming
- Use PascalCase for top-level fields (e.g., `VendorName`, `InvoiceDate`)
- Use descriptive names that clearly indicate content
- Avoid abbreviations unless widely recognized
- Keep names between 1-64 characters

### Field Types
- `string` - text values
- `number` - numeric values (integers or decimals)
- `boolean` - true/false values
- `array` - lists of items (use arrays of objects for structured data, not string fields requesting JSON)
- `object` - nested structures with properties

### Method Selection
Explicitly set the method for each field:
- `extract` - Values appearing directly in content (only for document analyzers)
- `generate` - Values requiring inference or summarization
- `classify` - Selection from predefined options

### Description Best Practices

Write descriptions that follow Azure Content Understanding best practices:

#### 1. Write Detailed Descriptions
- **Include location hints**: "typically found at the top right corner", "in the header section"
- **Specify format expectations**: "Format is usually MM/DD/YYYY", "alphanumeric with prefix"
- **List alternative labels**: "May be labeled as 'Invoice Date', 'Billing Date', or 'Issue Date'"
- **Provide examples**: "Examples: '01/15/2024', 'INV-2024-001', '$1,234.56'"

#### 2. Include All Aliases
List all possible names the field might appear under, especially for documents with diverse templates:
- "Equal to the 'Distributions' column. Also disclosed as 'Realizations' or 'Realized Proceeds'."

#### 3. Use Affirmative Language
Describe what the field IS, not what it ISN'T:
- ✅ "The date when goods or services were delivered, found in the delivery information section"
- ❌ "This field isn't the invoice date and isn't the due date"

#### 4. Match Language to Content
Use the same language as your documents. For Italian invoices, use Italian field names and descriptions.

#### 5. Reference Text Content, Not Visual Appearance
- ✅ "Near the label 'Total:', in the summary section at bottom"
- ❌ "The number in bold red text at the top right"

**Good Example**:
```
"description": "The date when the invoice was issued, typically found at the top right corner. May be labeled as 'Invoice Date', 'Billing Date', or 'Issue Date'. Format is usually MM/DD/YYYY or DD-MM-YYYY. Examples: '01/15/2024', '2024-01-15', 'January 15, 2024'."
```

**Poor Example**:
```
"description": "Invoice date"
```

### Examples
Provide 2-3 canonical examples that show:
- Typical values
- Format expectations
- Range of possibilities

## Tasks

1. For each field, write:
   - Clear, specific description
   - Appropriate type
   - 2-3 example values
   - Any validation rules or constraints

2. Ensure consistency:
   - Similar fields use similar phrasing
   - Nested objects are properly structured
   - Array items have clear schemas

3. Review for clarity:
   - Remove ambiguity
   - Add context where needed
   - Ensure descriptions are actionable

## Output Format

Provide JSON snippet with complete field definitions:

```json
{
  "FieldName": {
    "type": "string",
    "method": "extract",
    "description": "Clear, specific description of what to extract and where to find it.",
    "examples": [
      "Example 1",
      "Example 2"
    ]
  }
}
```

## Validation Checklist

- [ ] All fields have clear descriptions
- [ ] Field types are appropriate
- [ ] Examples are provided
- [ ] No ambiguous language
- [ ] Consistent style across fields
- [ ] Edge cases are addressed
