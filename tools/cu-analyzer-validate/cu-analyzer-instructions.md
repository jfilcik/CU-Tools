# CU (Custom Understanding) Analyzer Creation Guide

> **Purpose**: This document provides comprehensive instructions for creating valid CU analyzer configurations for Azure AI Document Intelligence Custom Understanding models.

---

## Overview

A CU analyzer is a JSON configuration that defines:
1. **Config**: Optional settings controlling extraction behavior
2. **Field Schema**: The structure and types of data to extract from documents

```json
{
  "config": { /* extraction settings */ },
  "fieldSchema": {
    "fields": { /* field definitions */ }
  }
}
```

---

## Understanding the Two-Stage Pipeline

**Content Understanding uses a two-stage architecture**:

### Stage 1: Document Analysis (OCR + Layout)
- Extracts text using OCR (Optical Character Recognition)
- Analyzes document structure (paragraphs, tables, sections, headers)
- Identifies bounding regions and spatial relationships
- Outputs structured text and layout information

### Stage 2: Field Extraction (AI Analysis)
- AI model (GPT-4.1) analyzes the OCR/layout results from Stage 1
- Uses your field descriptions to extract specific information
- Works with **text and structure**, not the original images
- Returns extracted field values with confidence scores

### Key Implications for Schema Design

**✅ DO**:
- Write field descriptions that reference text content, labels, and structure
- Describe location using text-based landmarks ("near 'Total:' label", "in header section")
- Leverage base analyzers (prebuilt-document, prebuilt-layout) for rich OCR/layout
- Reference section headers, table structures, and text patterns
- Use clear, specific descriptions that help the AI understand what to extract

**❌ DON'T**:
- Reference visual appearance (colors, fonts, styling, bold text, etc.)
- Ask for outputs already provided by OCR/layout (e.g., "extract all text")
- Describe elements by visual position alone without text context
- Expect the model to "see" images directly - it sees extracted text

### Example: Good vs Poor Descriptions

**❌ Poor** (references visual appearance):
```json
{
  "InvoiceNumber": {
    "type": "string",
    "description": "The number in bold red text in the top-right corner"
  }
}
```

**✅ Good** (references text labels and structure):
```json
{
  "InvoiceNumber": {
    "type": "string",
    "description": "The unique invoice identifier, typically found in the header area near labels like 'Invoice #', 'Inv No:', or 'Invoice Number'. Format is usually alphanumeric (e.g., 'INV-2024-001')."
  }
}
```

---

## Quick Start Template

Use this minimal template as a starting point:

```json
{
  "config": {
    "returnDetails": true,
    "enableOcr": true,
    "enableLayout": true
  },
  "fieldSchema": {
    "fields": {
      "documentTitle": {
        "type": "string",
        "method": "extract",
        "description": "The main title or heading of the document, typically found at the top of the first page."
      },
      "documentDate": {
        "type": "date",
        "method": "extract",
        "description": "The date the document was created or issued."
      },
      "totalAmount": {
        "type": "number",
        "method": "extract",
        "description": "The total monetary amount shown on the document."
      }
    }
  }
}
```

---

## Config Section Reference

The `config` section is **optional** but recommended. All values have sensible defaults.

### Boolean Options

| Option | Default | Description |
|--------|---------|-------------|
| `returnDetails` | `false` | Return detailed extraction information including bounding regions |
| `enableOcr` | `true` | Enable OCR for scanned/image documents |
| `enableLayout` | `true` | Enable layout analysis for tables, paragraphs, sections |
| `enableFormula` | `false` | Enable mathematical formula detection |
| `enableFigureDescription` | `false` | Generate descriptions for figures/images |
| `enableFigureAnalysis` | `false` | Analyze figure content |
| `disableContentFiltering` | `false` | Disable content safety filtering |
| `estimateFieldSourceAndConfidence` | `false` | Include source location and confidence scores |
| `enableSegment` | `false` | Enable document segmentation |
| `omitContent` | `false` | Omit raw content from response |
| `segmentPerPage` | `false` | Segment document by page |
| `enableAnnotations` | `false` | Enable annotation extraction |

### Enum Options

| Option | Valid Values | Default |
|--------|--------------|---------|
| `tableFormat` | `"html"`, `"markdown"` | `"html"` |
| `chartFormat` | `"chartjs"`, `"markdown"` | `"chartjs"` |
| `annotationFormat` | `"markdown"`, `"json"` | `"markdown"` |

### Example Config

```json
{
  "config": {
    "returnDetails": true,
    "enableOcr": true,
    "enableLayout": true,
    "enableFormula": false,
    "enableFigureDescription": true,
    "tableFormat": "html",
    "estimateFieldSourceAndConfidence": true
  }
}
```

---

## Field Types Reference

### Scalar Types

| Type | Use Case | Example Value |
|------|----------|---------------|
| `string` | Text values | `"John Doe"` |
| `number` | Decimal numbers | `123.45` |
| `integer` | Whole numbers | `42` |
| `date` | Calendar dates | `"2024-01-15"` |
| `time` | Time values | `"14:30:00"` |
| `boolean` | True/false values | `true` |
| `currency` | Monetary amounts with currency | `{"amount": 99.99, "currencyCode": "USD"}` |
| `address` | Physical addresses | Structured address object |
| `countryRegion` | Country/region names | `"United States"` |

### Selection Types

| Type | Use Case |
|------|----------|
| `selectionMark` | Checkboxes, radio buttons (selected/unselected) |
| `signature` | Signature presence detection |
| `selectionGroup` | Groups of related selection marks |

### Compound Types

| Type | Use Case | Required Property |
|------|----------|-------------------|
| `object` | Nested structured data | `properties` |
| `array` | Lists/tables of items | `items` |

---

## Field Definition Structure

Every field MUST have:
- `type`: One of the valid field types

Every field SHOULD have:
- `description`: Clear instructions for what to extract (improves accuracy significantly)

Every field MAY have:
- `method`: `"extract"` (from document) or `"generate"` (AI-inferred)

### Basic Field Example

```json
{
  "invoiceNumber": {
    "type": "string",
    "method": "extract",
    "description": "The unique invoice number or ID, typically found in the header area. Format is usually alphanumeric (e.g., 'INV-2024-001')."
  }
}
```

---

## Writing Effective Descriptions

**Descriptions are the most important factor for extraction accuracy.** Write them as clear instructions that reference **text content and structure** from the OCR/layout analysis.

### ✅ Good Description Patterns

```json
{
  "customerName": {
    "type": "string",
    "description": "The full name of the customer or buyer. Look for labels like 'Bill To:', 'Customer:', 'Sold To:', or 'Buyer:'. Extract the complete name, not the company name."
  }
}
```

```json
{
  "totalDue": {
    "type": "number",
    "description": "The final total amount to be paid. Look for labels like 'Total Due', 'Amount Due', 'Grand Total', or 'Balance Due'. This should be the largest/final amount, NOT subtotals or line item amounts."
  }
}
```

```json
{
  "issueDate": {
    "type": "date",
    "description": "The date the invoice was issued or created. Look for text labels like 'Invoice Date', 'Date', 'Issue Date'. Do NOT extract the due date or payment date."
  }
}
```

### ❌ Poor Descriptions (Avoid)

```json
{
  "name": {
    "type": "string",
    "description": "The name"  // ❌ Too vague - which name?
  }
}
```

```json
{
  "amount": {
    "type": "number",
    "description": "Amount"  // ❌ No guidance on which amount
  }
}
```

```json
{
  "total": {
    "type": "number", 
    "description": "The amount shown in large bold text at the bottom"  // ❌ References visual formatting the model can't see
  }
}
```

### Description Best Practices (Azure Content Understanding)

Follow these principles from Azure Content Understanding best practices:

1. **Write detailed descriptions** with location hints, format expectations, and alternative labels
   - Include: "typically found at the top right corner"
   - Specify: "Format is usually MM/DD/YYYY or DD-MM-YYYY"
   - List alternatives: "May be labeled as 'Invoice Date', 'Billing Date', or 'Issue Date'"
   
2. **Include all aliases** - List all possible names for each field
   - "Equal to the 'Distributions' column. Also disclosed as 'Realizations' or 'Realized Proceeds'."
   
3. **Use affirmative language** - Describe what the field IS, not what it ISN'T
   - ✅ "The date when goods were delivered, found in delivery section"
   - ❌ "This isn't the invoice date and isn't the due date"
   
4. **Match language to content** - Use same language as your documents
   - Italian invoices: Use Italian field names and descriptions
   
5. **Reference text-based landmarks** ("near 'Total' label", "in section with header 'Customer Info'")

6. **Avoid visual references** (colors, fonts, bold, size, positioning without text context)

7. **Minimum 20 characters** recommended (validator will warn on very short descriptions)

8. **Provide examples** in the description when helpful
   - "Examples: '01/15/2024', '2024-01-15', 'January 15, 2024'"

---

## Working with Objects

Use `object` type for nested, structured data with named properties.

```json
{
  "vendor": {
    "type": "object",
    "description": "Information about the vendor/seller who issued the invoice.",
    "properties": {
      "name": {
        "type": "string",
        "method": "extract",
        "description": "The vendor's company or business name."
      },
      "address": {
        "type": "address",
        "method": "extract",
        "description": "The vendor's business address."
      },
      "taxId": {
        "type": "string",
        "method": "extract",
        "description": "The vendor's tax identification number (EIN, VAT, etc.)."
      },
      "phone": {
        "type": "string",
        "method": "extract",
        "description": "The vendor's contact phone number."
      }
    }
  }
}
```

---

## Working with Arrays

**Azure Best Practice**: Use `array` type with structured objects for repeated data (like line items). **Do not** use string fields requesting JSON output.

### ✅ Correct: Array of Objects (Tables/Line Items)

```json
{
  "lineItems": {
    "type": "array",
    "method": "extract",
    "description": "All line items or product entries in the invoice. Extract EVERY row from the items table.",
    "items": {
      "type": "object",
      "description": "A single line item representing one product or service.",
      "properties": {
        "description": {
          "type": "string",
          "method": "extract",
          "description": "The product or service description/name."
        },
        "quantity": {
          "type": "number",
          "method": "extract",
          "description": "The quantity ordered (number of units)."
        },
        "unitPrice": {
          "type": "number",
          "method": "extract",
          "description": "The price per single unit."
        },
        "totalPrice": {
          "type": "number",
          "method": "extract",
          "description": "The total price for this line (quantity × unit price)."
        }
      }
    }
  }
}
```

---

## Method: Extract vs Generate vs Classify

**Azure Best Practice**: Explicitly set the method for each field based on its purpose.

### `extract` (Default)
Pulls values directly from the document text. Use for:
- Values that appear verbatim in the document
- Dates, numbers, names, IDs, amounts
- Most fields in document analysis

**Note**: `extract` is **only supported for Document analyzers**.

### `generate`
AI generates/infers the value based on context. Use for:
- Values requiring inference or summarization
- Risk level assessment, sentiment analysis
- Executive summaries, key takeaways
- Derived values not explicitly stated

**Examples**:
```json
{
  "riskLevel": {
    "type": "string",
    "method": "generate",
    "description": "Assess overall document risk level as 'low', 'medium', or 'high' based on contract terms, financial amounts, and compliance requirements."
  },
  "executiveSummary": {
    "type": "string",
    "method": "generate",
    "description": "Generate a 2-3 sentence summary of the key points and obligations in this contract."
  }
}
```

### `classify`
Selection from predefined options. Use for:
- Document type categorization
- Status classification
- Category assignment

**Examples**:
```json
{
  "documentType": {
    "type": "string",
    "method": "classify",
    "description": "Classify this document as one of: 'invoice', 'receipt', 'purchase_order', 'quote', 'contract', or 'other'."
  },
  "priorityLevel": {
    "type": "string",
    "method": "classify",
    "description": "Classify priority as 'high', 'medium', or 'low' based on urgency indicators and due dates."
  }
}
```

---

## Field Naming Conventions

### Rules (Enforced)
- Must start with a letter (a-z, A-Z)
- Can contain letters, numbers, underscores
- Maximum 64 characters
- Must be unique within the same object (case-insensitive)

### Best Practices (Recommended)
- Use **camelCase**: `invoiceNumber`, `lineItems`, `totalAmount`
- Be descriptive but concise
- Avoid abbreviations unless universally understood
- Use consistent naming patterns across similar fields

### ✅ Good Names
```
invoiceNumber, customerName, lineItems, totalAmount, issueDate, 
vendorAddress, taxRate, shippingCost, paymentTerms
```

### ❌ Avoid
```
inv_num      // Use camelCase instead of snake_case
n            // Too short, unclear
InvoiceNumber // Start with lowercase
data1        // Non-descriptive
```

---

## Complete Invoice Analyzer Example

```json
{
  "config": {
    "returnDetails": true,
    "enableOcr": true,
    "enableLayout": true,
    "tableFormat": "html",
    "estimateFieldSourceAndConfidence": true
  },
  "fieldSchema": {
    "fields": {
      "invoiceNumber": {
        "type": "string",
        "method": "extract",
        "description": "The unique invoice identifier. Look for 'Invoice #', 'Invoice Number', 'Inv No.', or similar labels, typically in the document header."
      },
      "invoiceDate": {
        "type": "date",
        "method": "extract",
        "description": "The date the invoice was issued. Look for 'Invoice Date', 'Date', 'Issue Date'. Do NOT extract due date or payment date."
      },
      "dueDate": {
        "type": "date",
        "method": "extract",
        "description": "The payment due date. Look for 'Due Date', 'Payment Due', 'Pay By'."
      },
      "vendor": {
        "type": "object",
        "description": "The seller/vendor who issued this invoice.",
        "properties": {
          "name": {
            "type": "string",
            "method": "extract",
            "description": "The vendor's company name, usually prominently displayed at the top or with a logo."
          },
          "address": {
            "type": "string",
            "method": "extract",
            "description": "The vendor's full mailing address."
          },
          "taxId": {
            "type": "string",
            "method": "extract",
            "description": "The vendor's tax ID, VAT number, or EIN."
          }
        }
      },
      "customer": {
        "type": "object",
        "description": "The buyer/customer receiving this invoice.",
        "properties": {
          "name": {
            "type": "string",
            "method": "extract",
            "description": "The customer name. Look for 'Bill To', 'Customer', 'Sold To'."
          },
          "address": {
            "type": "string",
            "method": "extract",
            "description": "The customer's billing address."
          }
        }
      },
      "lineItems": {
        "type": "array",
        "description": "All products or services listed on the invoice. Extract every row from the line items table.",
        "items": {
          "type": "object",
          "description": "A single product or service entry.",
          "properties": {
            "description": {
              "type": "string",
              "method": "extract",
              "description": "The item description or product name."
            },
            "quantity": {
              "type": "number",
              "method": "extract",
              "description": "Number of units."
            },
            "unitPrice": {
              "type": "number",
              "method": "extract",
              "description": "Price per unit."
            },
            "amount": {
              "type": "number",
              "method": "extract",
              "description": "Line total (quantity × unit price)."
            }
          }
        }
      },
      "subtotal": {
        "type": "number",
        "method": "extract",
        "description": "The subtotal before tax. Look for 'Subtotal', 'Sub-Total'."
      },
      "taxAmount": {
        "type": "number",
        "method": "extract",
        "description": "The total tax amount. Look for 'Tax', 'VAT', 'Sales Tax'."
      },
      "totalAmount": {
        "type": "number",
        "method": "extract",
        "description": "The final total amount due. Look for 'Total', 'Total Due', 'Amount Due', 'Grand Total'. This is the largest total, after tax."
      },
      "currency": {
        "type": "string",
        "method": "generate",
        "description": "The currency code (e.g., 'USD', 'EUR', 'GBP'). Infer from currency symbols ($, €, £) or explicit mentions."
      }
    }
  }
}
```

---

## Validation Checklist

Before deploying an analyzer, verify:

### Structure
- [ ] Root object has `fieldSchema` with `fields` property
- [ ] Every field has a valid `type`
- [ ] Every `object` type has `properties`
- [ ] Every `array` type has `items`
- [ ] No circular references

### Field Names
- [ ] Start with letter, alphanumeric only
- [ ] Under 64 characters
- [ ] No duplicates within same scope
- [ ] Using camelCase consistently

### Descriptions
- [ ] Every field has a description
- [ ] Descriptions are specific and actionable
- [ ] Disambiguation instructions where needed
- [ ] No placeholder text ("TODO", "TBD")

### Config (if present)
- [ ] Boolean values are `true`/`false` (not strings)
- [ ] Enum values are valid options
- [ ] No unknown/misspelled keys

### Limits
- [ ] Total fields under 500
- [ ] Nesting depth under 10 levels
- [ ] Array nesting under 5 levels

---

## Validation Tool

Use the included validator to check your analyzer:

```bash
python cu_analyzer_validator.py my-analyzer.json
```

Or programmatically:

```python
from cu_analyzer_validator import validate_cu_analyzer_file

result = validate_cu_analyzer_file("my-analyzer.json")
if not result.is_valid:
    print(result.get_all_messages())
else:
    print("✅ Analyzer is valid!")
```

---

## Using Confidence Scores Effectively

**Azure Best Practice**: Use confidence scores to determine when human review is needed. Set different thresholds based on field criticality.

### Recommended Thresholds

- **Critical fields** (e.g., TotalAmount, ContractTerminationDate, LegalObligation): ≥0.90
- **Important fields** (e.g., VendorName, InvoiceNumber, CustomerAddress): ≥0.80
- **Non-critical fields** (e.g., Comments, Notes, InternalReference): ≥0.70

**Note**: These thresholds are guidelines. Determine optimal thresholds experimentally for each use case.

### Configuration

Enable confidence scores in your analyzer configuration:

```json
{
  "config": {
    "returnDetails": true,
    "estimateFieldSourceAndConfidence": true
  },
  "fieldSchema": {
    "fields": {
      "totalAmount": {
        "type": "number",
        "method": "extract",
        "description": "The final total amount due...",
        "estimateSourceAndConfidence": true
      }
    }
  }
}
```

**Important**: Only document analyzers currently support confidence scores.

### Using Scores in Production

```python
# Example: Review logic based on confidence
if result['totalAmount']['confidence'] < 0.90:
    # Flag for human review
    queue_for_review(result)
elif result['vendorName']['confidence'] < 0.80:
    # Flag vendor name for verification
    verify_vendor(result)
```

---

## Improving Accuracy Over Time

**Azure Best Practice**: Start with descriptions, then add training examples.

### Phase 1: Optimize Descriptions (Priority)

**Prioritize refining field descriptions before adding labeled training examples.** Clear descriptions often resolve issues without requiring more data.

**Steps**:
1. Identify fields with low confidence or incorrect extractions
2. Enhance descriptions with:
   - More specific location hints
   - Additional alternative labels (aliases)
   - Clearer format expectations
   - Better disambiguation from similar fields
3. Test with same documents to verify improvement
4. Iterate until accuracy is acceptable

**Example improvement**:

❌ **Before**:
```json
"vendorName": {
  "type": "string",
  "description": "Vendor name"
}
```

✅ **After**:
```json
"vendorName": {
  "type": "string",
  "method": "extract",
  "description": "The company name of the vendor/supplier issuing this invoice. Typically found at the top of the document, often with a logo. May be labeled as 'From:', 'Vendor:', 'Supplier:', or appear as a company header. Extract the full legal business name. Examples: 'Acme Corporation', 'Tech Solutions Inc.', 'Global Services LLC'."
}
```

### Phase 2: Add Training Examples (If Needed)

If accuracy or confidence scores remain low after optimizing descriptions, add similar documents to the knowledge base as training examples.

**When to add training examples**:
- Consistent extraction errors despite clear descriptions
- Low confidence scores (<0.80) on important fields after description optimization
- Complex documents with unusual or inconsistent layouts
- Domain-specific terminology or specialized formats
- Edge cases that descriptions alone cannot address

**Best practices for training examples**:
- Use diverse examples representing different layouts and variations
- Include both typical cases and edge cases
- Ensure examples are accurately labeled
- Start with 5-10 examples and add more if needed
- Monitor improvement after adding each batch

---

## Common Mistakes & Fixes

### Missing `properties` on Object

❌ **Wrong:**
```json
{
  "address": {
    "type": "object",
    "description": "The address"
  }
}
```

✅ **Fixed:**
```json
{
  "address": {
    "type": "object",
    "description": "The address",
    "properties": {
      "street": { "type": "string", "description": "Street address" },
      "city": { "type": "string", "description": "City name" }
    }
  }
}
```

### Missing `items` on Array

❌ **Wrong:**
```json
{
  "tags": {
    "type": "array",
    "description": "List of tags"
  }
}
```

✅ **Fixed:**
```json
{
  "tags": {
    "type": "array",
    "description": "List of tags",
    "items": {
      "type": "string",
      "description": "A single tag"
    }
  }
}
```

### Boolean as String

❌ **Wrong:**
```json
{
  "config": {
    "enableOcr": "true"
  }
}
```

✅ **Fixed:**
```json
{
  "config": {
    "enableOcr": true
  }
}
```

### Vague Description

❌ **Wrong:**
```json
{
  "amount": {
    "type": "number",
    "description": "The amount"
  }
}
```

✅ **Fixed:**
```json
{
  "totalAmount": {
    "type": "number",
    "description": "The final total amount due after all taxes and discounts. Look for 'Total Due', 'Grand Total', or 'Amount Due'. This should be the largest amount on the invoice, not a subtotal or line item."
  }
}
```

---

## Tips for Complex Documents

### Multi-Language Documents
Include language hints in descriptions:
```json
{
  "totalAmount": {
    "type": "number",
    "description": "The total amount. May appear as 'Total', 'Totale' (Italian), 'Gesamt' (German), or 'Total a pagar' (Spanish)."
  }
}
```

### Documents with Multiple Similar Sections
Be explicit about which section to extract from:
```json
{
  "shippingAddress": {
    "type": "string",
    "description": "The shipping/delivery address. Look for 'Ship To', 'Deliver To'. Do NOT extract the billing address."
  }
}
```

### Tables with Merged Cells or Complex Layout
Describe the visual structure:
```json
{
  "lineItems": {
    "type": "array",
    "description": "Extract from the main product table. Each row represents one item. If descriptions span multiple lines, combine them. Ignore header rows and summary rows."
  }
}
```

---

*Last Updated: January 2026*
*Validator Version: 1.0*
