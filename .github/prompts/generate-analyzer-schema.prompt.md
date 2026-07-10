---
status: ✅ IMPLEMENTED
version: 1.1.0
last_updated: 2026-01-30
---

# Prompt: Generate Analyzer Schema

## Goal

Generate a complete, valid Content Understanding analyzer schema based on identified extraction requirements.

## Context

- **Document Type**: [e.g., Invoice, Purchase Order, Contract]
- **Base Analyzer**: [optional - e.g., prebuilt-invoice, prebuilt-document]
- **Fields to Extract**: [list from document structure analysis]

## Input

Field requirements from the document structure analysis:

| Field Name | Type | Description | Required |
|------------|------|-------------|----------|
| {field} | {type} | {description} | {yes/no} |

## Understanding Content Understanding Architecture

**IMPORTANT**: Content Understanding uses a **two-stage pipeline**:

1. **Stage 1 - Document Analysis**: OCR and layout analysis extract text, tables, structure from the document
2. **Stage 2 - Field Extraction**: AI model analyzes the OCR/layout results to extract your defined fields

**Key Implications**:
- ✅ Field descriptions should reference text content, structure, and layout (not visual appearance)
- ✅ The model "sees" extracted text and structure, not the original images
- ✅ Leverage base analyzers (prebuilt-document, prebuilt-layout) which provide rich OCR/layout results
- ❌ Avoid asking for information already provided by OCR/layout (e.g., "extract all text")
- ❌ Don't describe visual elements like colors, fonts, or styling (model doesn't see these)

**Best Practices**:
- Reference text labels, section headers, and structural elements
- Describe location using text-based landmarks ("near Total label", "in header section")
- Use clear, specific descriptions that help the model understand what to extract from text

## Schema Requirements

### Required Structure

All schemas must include these required sections:

```json
{
  "baseAnalyzerId": "prebuilt-document",
  "description": "Brief description of what this analyzer extracts",
  "scenario": "document",
  "config": {
    "returnDetails": true,
    "estimateFieldSourceAndConfidence": true
  },
  "models": {
    "completion": "gpt-4.1"
  },
  "fieldSchema": {
    "fields": {
      "FieldName": {
        "type": "string|number|boolean|array|object",
        "method": "extract|generate|classify",
        "description": "Clear, specific description",
        "estimateSourceAndConfidence": true
      }
    }
  }
}
```

### Required Properties

1. **baseAnalyzerId**: Which prebuilt analyzer to extend
   - `"prebuilt-document"` - Most common, for custom document extraction
   - `"prebuilt-layout"` - For layout-focused extraction
   - `"prebuilt-invoice"` - For invoice-specific fields

2. **models.completion**: The AI model to use
   - **Default**: `"gpt-4.1"` (recommended for most use cases)
   - Alternatives: `"gpt-4o"`, `"gpt-4o-mini"`, `"gpt-4.1-mini"`, `"gpt-4.1-nano"`

3. **config.returnDetails**: Always `true` for debugging and quality review

4. **config.estimateFieldSourceAndConfidence**: Always `true` to track extraction confidence

5. **scenario**: Always `"document"` for document extraction

### Field Naming Rules
- Use PascalCase (e.g., `InvoiceNumber`, `VendorName`)
- 1-64 characters
- Start with letter or underscore
- No spaces or special characters

### Supported Types
- `string` - Text values
- `number` - Integers or decimals
- `boolean` - True/false
- `array` - Lists (define items schema)
- `object` - Nested structure (define properties)

### Method Options

**Explicitly set the method for each field based on its purpose:**

- `extract` - Values appearing directly in the content (e.g., invoice number, date, amounts)
  - **Only supported for Document analyzers**
  - Use when the exact value is present in the document text
  
- `generate` - Values requiring inference or summarization (e.g., risk level, summary, sentiment)
  - Use when the AI needs to analyze and create a new value
  - Examples: "Overall document sentiment", "Key risk factors", "Executive summary"
  
- `classify` - Selection from predefined options (e.g., document type, category, status)
  - Use for categorizing into specific buckets
  - Examples: "Document type: Invoice/Receipt/Contract", "Priority: High/Medium/Low"

## Field Description Best Practices

**Critical Principle**: Clear and detailed field definitions are critical to accurate extraction. Follow these guidelines:

### 1. Write Detailed Descriptions

Provide clear, specific descriptions that guide the model to the correct information:
- **Include location hints**: "typically found at the top right corner", "in the delivery information section"
- **Specify format expectations**: "Format is usually MM/DD/YYYY or DD-MM-YYYY", "alphanumeric with prefix"
- **List alternative labels**: "May be labeled as 'Invoice Date', 'Billing Date', or 'Issue Date'"
- **Reference text-based landmarks**: Use section headers, labels, and structural elements (not visual appearance)

### 2. Include All Aliases

List all possible names for each field, especially when working with diverse document templates. This helps the model recognize the field regardless of labeling variations.

**Example - Investment distributions:**
```json
"distributions": {
  "type": "number",
  "method": "extract",
  "description": "Equal to the 'Distributions' column. Also disclosed as 'Realizations' or 'Realized Proceeds'. Typically found in the financial summary table."
}
```

### 3. Use Affirmative Language

Describe what the field IS rather than what it ISN'T. Positive descriptions are clearer and more effective.

**❌ Avoid:**
```json
"deliveryDate": {
  "type": "string",
  "description": "This field isn't the invoice date and isn't the due date."
}
```

**✅ Use:**
```json
"deliveryDate": {
  "type": "string",
  "method": "extract",
  "description": "The date when goods or services were delivered, found in the delivery information section. May be labeled as 'Delivery Date', 'Ship Date', or 'Received Date'. Format is typically MM/DD/YYYY."
}
```

### 4. Match Language to Content

Define field names and descriptions in the same language as your documents. Language mismatches can significantly reduce accuracy.

**Example for Italian invoices:**
```json
"fornitore": {
  "type": "string",
  "method": "extract",
  "description": "Il nome dell'azienda fornitrice, di solito nella parte superiore del documento. Può apparire vicino a 'Fornitore:', 'Da:', o nel logo aziendale."
}
```

### 5. Avoid Hardcoded Values (Critical Anti-Pattern)

**NEVER include specific values from test documents in field descriptions.** This is "cheating" - the schema will only work for that specific document, not generalize to other documents.

**❌ Hardcoded values (will not generalize):**
```json
"codeAmount": {
  "description": "Box 17 code B=345, Box 19 code B=514"
}
```
```json
"lineItems": {
  "description": "Expected values like B 345, B=345, B 514, B=514"
}
```

**✅ Generic patterns (will generalize):**
```json
"codeAmount": {
  "description": "3-digit dollar amount associated with the letter code"
}
```
```json
"lineItems": {
  "description": "Letter code (A, B, C, D, etc.) followed by amount. Format: X=NNN or X NNN"
}
```

**Rule of thumb**: If you can look at your test document and find the exact string in your description, it's probably hardcoded.

### 6. Description Quality Checklist

- Include text labels the field might appear under
- Specify location using text-based landmarks
- Provide format examples using **generic patterns**, not actual values
- Add disambiguation instructions when similar fields exist
- Use negative instructions when helpful ("Do NOT extract...", "Ignore...")

## Complete Description Examples

**Example - Invoice Date (following all best practices):**
```json
"InvoiceDate": {
  "type": "string",
  "method": "extract",
  "description": "The date when the invoice was issued, typically found at the top right corner. May be labeled as 'Invoice Date', 'Billing Date', or 'Issue Date'. Format is usually MM/DD/YYYY or DD-MM-YYYY. Examples: '01/15/2024', '2024-01-15', 'January 15, 2024'."
}
```

**Example - Poor (too vague):**
```json
"InvoiceDate": {
  "type": "string",
  "method": "extract",
  "description": "Invoice date"
}
```

**Example - Avoid (references visual appearance):**
```json
"InvoiceDate": {
  "type": "string", 
  "method": "extract",
  "description": "The date in bold text at the top"  // ❌ Model doesn't see colors/fonts/styling
}
```

### 7. Reading-Order Pitfalls in Summary Footers and Multi-Row Headers

The layout model does not always recognize summary footers (e.g., totals rows below a table) or multi-row header layouts as tables. When labels are in one row and values in another, but the layout model emits them as **free text** rather than a `<table>`, the OCR reading order can place labels far away from their values in the text stream.

**Symptom**: A field returns no `valueString` but has `confidence ≥ 0.7` — the LLM knows a value should exist but cannot resolve which token to extract from the garbled reading order.

**Example pattern (from real APL Logistics document)**:
```
Visual layout (what a human sees):
| Gross Kgs | Net Kgs | CBM  | # of Cartons | # of Units |
| 180.82    | 133.52  | 2.04 | 86           | 1,002      |

OCR reading order (what the LLM sees as text):
  Gross Kgs                  ← all labels read first
  Net Kgs
  CBM
  2.04                       ← CBM value adjacent → extracts correctly
  # of Cartons
  # of Units
  Total by Size:  110  156  271  278  187   ← interleaved size totals
  180.82  133.52  86  1,002  ← all values read last, far from labels
```

**Mitigations** (apply all that are relevant):

1. **Anchor by name + relative position in the description**, not by table column:
   ```
   ✅ "Found in the summary section at the bottom of the carton table,
       labeled 'Gross Kgs'. The numeric value appears directly below
       the 'Gross Kgs' label. Format: decimal number. Example: '180.82'"
   ```
   Telling the LLM the value is "directly below the label" helps it resolve vertical column alignment even when reading order is broken.

2. **Match the exact label in the document**, not a paraphrase:
   - ❌ "labeled 'Total Gross'" when the document says "Gross Kgs"
   - ❌ "labeled 'Total Cartons'" when the document says "# of Cartons"

3. **Flatten summary-row fields out of nested arrays.** Fields like `GrossWeight`, `CartonsQty`, `PiecesQty` are document-level totals, not line-item properties. Placing them inside `Goods[].properties` adds parsing complexity and dilutes the LLM's attention across many fields per array item.

4. **Diagnostic**: Run `tools/cu-analyzer-run/run.py --layout` and inspect `.layout.md`. If a summary row appears as plain text (not inside `<table>`) and the values are visually separated from their labels by other content, expect reading-order issues. As a confirmation, run `--read` (no layout) and check whether the labels and values are still positionally close — if they aren't, the document layout is the culprit.

5. **Last resort**: Set `enableLayout: false` in the analyzer config. This trades layout-table awareness for the `prebuilt-document` key-value pair detector, which uses spatial proximity instead of text reading order. Document this as a workaround for the specific document type.

## Use Structured Types for Repeated Data

Define repeated items (like line items or entries) as **arrays of objects** rather than string fields requesting JSON output.

**✅ Correct approach:**
```json
"lineItems": {
  "type": "array",
  "method": "extract",
  "description": "All items or services listed on the invoice. Extract each row from the line items table.",
  "items": {
    "type": "object",
    "properties": {
      "description": {
        "type": "string",
        "method": "extract",
        "description": "Product or service description from the line item"
      },
      "quantity": {
        "type": "number",
        "method": "extract",
        "description": "Number of units ordered"
      },
      "unitPrice": {
        "type": "number",
        "method": "extract",
        "description": "Price per single unit"
      },
      "total": {
        "type": "number",
        "method": "extract",
        "description": "Line total (quantity × unit price)"
      }
    }
  }
}
```

**❌ Avoid (requesting JSON as string):**
```json
"lineItems": {
  "type": "string",
  "description": "Extract line items as JSON string"
}
```

## Using Confidence Scores

Confidence scores help determine when human review is needed. Set different thresholds based on field criticality:

- **Critical fields** (e.g., TotalAmount, ContractTerminationDate): Use higher thresholds (≥0.90)
- **Important fields** (e.g., VendorName, InvoiceNumber): Use medium thresholds (≥0.80)
- **Non-critical fields** (e.g., Comments, Notes): Use lower thresholds (≥0.70)

**Note**: These thresholds are guidelines. Determine optimal thresholds experimentally for each use case.

**Configuration**:
```json
{
  "config": {
    "returnDetails": true,
    "estimateFieldSourceAndConfidence": true  // Required for confidence scores
  },
  "fieldSchema": {
    "fields": {
      "TotalAmount": {
        "type": "number",
        "method": "extract",
        "description": "...",
        "estimateSourceAndConfidence": true  // Enable per-field confidence
      }
    }
  }
}
```

**Important**: Only document analyzers currently support confidence scores.

## Iterative Improvement Strategy

Follow this approach when improving analyzer accuracy:

### 1. Start with Descriptions (Priority)

**Prioritize refining field descriptions before adding training examples.** Clear, detailed descriptions often resolve issues without requiring more data.

**Steps**:
1. Review low-confidence or incorrect extractions
2. Enhance descriptions with:
   - More specific location hints
   - Additional alternative labels
   - Clearer format expectations
   - Better disambiguation
3. Test with same documents to verify improvement

### 2. Add Training Examples (If Needed)

If accuracy or confidence scores remain low after optimizing descriptions, add similar documents to the knowledge base as training examples.

**When to add examples**:
- Consistent extraction errors despite clear descriptions
- Low confidence scores (<0.80) on important fields
- Complex documents with unusual layouts
- Domain-specific terminology or formats

## Output Format

Generate complete JSON schema:

```json
{
  "description": "Extract key information from {document_type} documents including {summary of fields}",
  "scenario": "document",
  "config": {
    "returnDetails": true
  },
  "fieldSchema": {
    "fields": {
      // All fields with complete definitions
    }
  }
}
```

## Schema Validation

**CRITICAL**: Always validate schemas before creating analyzers using the validation tool:

```bash
python tools/cu-analyzer-validate/cu_analyzer_validator.py schemas/my_schema.json
```

The validator checks for:
- ✅ Valid JSON syntax
- ✅ Required fields (baseAnalyzerId, fieldSchema)
- ✅ Field naming rules (start with letter, alphanumeric only, max 64 chars)
- ✅ Valid field types and structures
- ✅ Array items and object properties defined
- ✅ Description quality (warns if too vague or missing)
- ✅ Config options are valid
- ⚠️ Reserved field names avoided
- ⚠️ Nesting limits (max 10 levels deep)

**Integration**: The `create_and_test.py` tool automatically runs validation before creating analyzers.

## Validation Checklist

Before finalizing the schema:

- [ ] All field names are valid (PascalCase, no special chars, start with letter)
- [ ] All fields have clear, specific descriptions (min 20 chars recommended)
- [ ] Descriptions reference text labels and structure (not visual appearance)
- [ ] Types are appropriate for the data
- [ ] Array items have defined structure with `items` property
- [ ] Object fields have defined structure with `properties`
- [ ] Description helps the model understand what to extract from OCR/layout results
- [ ] Edge cases are addressed in descriptions
- [ ] Run validation: `python tools/cu-analyzer-validate/cu_analyzer_validator.py schemas/my_schema.json`

## Example: Custom Invoice Schema

```json
{
  "baseAnalyzerId": "prebuilt-document",
  "description": "Extract invoice details including vendor information, line items, and totals",
  "scenario": "document",
  "config": {
    "returnDetails": true,
    "estimateFieldSourceAndConfidence": true
  },
  "models": {
    "completion": "gpt-4.1"
  },
  "fieldSchema": {
    "fields": {
      "InvoiceNumber": {
        "type": "string",
        "method": "extract",
        "description": "The unique invoice identifier found in the header area. Usually alphanumeric with a prefix like 'INV-', '#', or 'Invoice No:'. Examples: 'INV-2024-0042', '#12345'",
        "estimateSourceAndConfidence": true
      },
      "InvoiceDate": {
        "type": "string",
        "method": "extract",
        "description": "The date the invoice was issued. Look for labels like 'Invoice Date', 'Date', or 'Issued'. Return in the format shown on the document.",
        "estimateSourceAndConfidence": true
      },
      "DueDate": {
        "type": "string",
        "method": "extract",
        "description": "The payment due date. May be shown as a specific date or terms like 'Net 30'. If terms are given, extract as shown."
      },
      "VendorName": {
        "type": "string",
        "method": "extract",
        "description": "Name of the company issuing the invoice. Usually prominently displayed in the header, often near or below the company logo."
      },
      "VendorAddress": {
        "type": "string",
        "method": "extract",
        "description": "Full address of the vendor/seller, typically in the header area near the vendor name."
      },
      "CustomerName": {
        "type": "string",
        "method": "extract",
        "description": "Name of the customer being billed. Look for 'Bill To', 'Customer', or 'Sold To' section."
      },
      "LineItems": {
        "type": "array",
        "method": "extract",
        "description": "List of products or services being billed, typically shown in a table format",
        "items": {
          "type": "object",
          "properties": {
            "Description": {
              "type": "string",
              "description": "Product or service description"
            },
            "Quantity": {
              "type": "number",
              "description": "Number of units"
            },
            "UnitPrice": {
              "type": "number",
              "description": "Price per unit"
            },
            "Amount": {
              "type": "number",
              "description": "Line total amount"
            }
          }
        }
      },
      "Subtotal": {
        "type": "number",
        "method": "extract",
        "description": "Sum of all line items before tax. Usually labeled 'Subtotal' near the bottom of the invoice."
      },
      "TaxAmount": {
        "type": "number",
        "method": "extract",
        "description": "Tax amount charged. May be labeled as 'Tax', 'VAT', 'GST', or 'Sales Tax'."
      },
      "TotalAmount": {
        "type": "number",
        "method": "extract",
        "description": "Final total amount due. Usually the largest/most prominent number at the bottom, labeled 'Total', 'Amount Due', or 'Balance Due'."
      }
    }
  }
}
```

## Usage in Workflow

This prompt is used in **Step 4-5** of the `generate-analyzer.skill.md` workflow, after fields have been identified from document structure analysis.

Save the generated schema to: `{project_folder}/schemas/{name}_v1.json`

## Reference: Working Schema Examples

See these proven schemas for reference:

### Simple Extraction (Invoice)
- **Path**: `AzureSamples/analyzer_templates/invoice.json`
- **Use case**: Basic field extraction from invoices
- **Pattern**: Flat field structure with clear descriptions

### Complex Nested Structure (K-1 Form)
- **Path**: `Issues/WK_Runs/WK/schemas/AxScan_K1_1065_Fed_Page_v2.1_optimized copy.json`
- **Use case**: Multi-section tax form with arrays and objects
- **Pattern**: Nested objects with detailed location guidance

### Array/Table Extraction
- **Path**: `Issues/WK_Runs/WK/schemas/AxScan_K1_1065_Fed_Page_v2_improved.json`
- **Use case**: Extracting tabular data and repeating sections
- **Pattern**: Array items with consistent structure

### Key Patterns to Copy

**1. Basic Field with Source Tracking**:
```json
"FieldName": {
  "type": "string",
  "method": "extract",
  "description": "What to extract, where to find it, expected format",
  "estimateSourceAndConfidence": true
}
```

**2. Nested Object**:
```json
"AddressInfo": {
  "type": "object",
  "method": "extract",
  "description": "Complete address information from header section",
  "properties": {
    "Street": {
      "type": "string",
      "description": "Street address line",
      "estimateSourceAndConfidence": true
    },
    "City": {
      "type": "string",
      "description": "City name",
      "estimateSourceAndConfidence": true
    }
  }
}
```

**3. Array of Items**:
```json
"LineItems": {
  "type": "array",
  "method": "generate",
  "description": "All line items in the table. Extract every row.",
  "items": {
    "type": "object",
    "method": "generate",
    "properties": {
      "Description": {
        "type": "string",
        "description": "Item description",
        "estimateSourceAndConfidence": true
      },
      "Amount": {
        "type": "number",
        "description": "Line amount",
        "estimateSourceAndConfidence": true
      }
    }
  }
}
```

## See Also

- Write field descriptions: `.github/prompts/write_schema_fields.prompt.md`
- Classify-and-route schemas: `.github/prompts/classify-and-route-schema.prompt.md`
- Video analyzer schemas: `.github/skills/generate-analyzer-video.skill.md`
- Evaluate results: `.github/prompts/evaluate-analyzer.prompt.md`
