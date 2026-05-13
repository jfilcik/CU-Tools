---
status: ✅ IMPLEMENTED
version: 1.0.0
last_updated: 2026-01-26
---

# Prompt: Analyze Document Structure

## Goal

Analyze layout extraction results to understand document structure and identify key fields for extraction.

## Context

- **Layout Results Folder**: [Path to layout_results folder with .layout.md and .layout.json files]
- **Document Type**: [e.g., Invoice, Purchase Order, Contract, Receipt]
- **Purpose**: [What the customer wants to extract/achieve]

## Input Files

Review the following files from the layout results:
1. `*.layout.md` - Markdown representation of document content
2. `*.layout.json` - Full layout analysis with structure details

## Analysis Tasks

### 1. Document Structure Analysis

For each sample document, identify:

**Sections/Regions**:
- Header area (logos, titles, identifiers)
- Main content areas
- Tables and lists
- Footer/signature areas

**Common Patterns**:
- Consistent section headers across documents
- Key-value pair patterns (Label: Value)
- Tabular data structures
- Repeating elements

### 2. Key Data Points

Identify data that would be valuable to extract:

| Data Point | Location | Format | Consistency |
|------------|----------|--------|-------------|
| {name} | {where found} | {string/number/date/etc} | {always/sometimes/varies} |

Consider:
- Identifiers (numbers, codes, references)
- Dates and timestamps
- Names (people, companies, products)
- Amounts and quantities
- Addresses and contact info
- Line items and lists

### 3. Variations Across Samples

Note differences between documents:
- Layout variations
- Missing fields in some documents
- Different formats for same data
- Edge cases

### 4. Extraction Challenges

Identify potential difficulties:
- Data embedded in images/logos
- Inconsistent formatting
- Multiple possible locations for same data
- Ambiguous field boundaries

## Output Format

Provide a structured summary:

```markdown
## Document Structure Summary

### Document Type: {type}

### Consistent Elements
- {element 1}
- {element 2}

### Recommended Extraction Fields

| Field Name | Type | Description | Found In |
|------------|------|-------------|----------|
| {name} | {type} | {what it is} | {all/most/some} docs |

### Variations Observed
- {variation 1}
- {variation 2}

### Potential Challenges
- {challenge 1}
- {challenge 2}

### Recommendations
- {recommendation for schema design}
```

## Example Analysis

Given layout results from invoice samples:

```markdown
## Document Structure Summary

### Document Type: Invoice

### Consistent Elements
- Company logo and name in header (top-left)
- Invoice number and date (top-right)
- "Bill To" and "Ship To" sections
- Line items table with columns: Item, Description, Qty, Price, Total
- Subtotal, Tax, and Total at bottom
- Payment terms in footer

### Recommended Extraction Fields

| Field Name | Type | Description | Found In |
|------------|------|-------------|----------|
| InvoiceNumber | string | Unique invoice identifier (e.g., INV-2024-001) | all docs |
| InvoiceDate | string | Date invoice was issued | all docs |
| DueDate | string | Payment due date | most docs |
| VendorName | string | Name of the company issuing invoice | all docs |
| BillToName | string | Name of the customer being billed | all docs |
| BillToAddress | string | Customer billing address | all docs |
| LineItems | array | List of items with description, qty, price | all docs |
| Subtotal | number | Sum before tax | all docs |
| TaxAmount | number | Tax amount | most docs |
| TotalAmount | number | Final amount due | all docs |

### Variations Observed
- Some invoices have "Ship To" separate from "Bill To", others combine them
- Tax shown as percentage in some, amount in others
- Due date format varies: "Net 30" vs specific date

### Potential Challenges
- Vendor name sometimes in logo only (image, not text)
- Line item table structure varies (different column orders)
- Some invoices have multiple pages

### Recommendations
1. Make DueDate and TaxAmount optional fields
2. Add clear description for VendorName to check header text area
3. For LineItems, define flexible schema that handles column variations
4. Consider adding PageCount field for multi-page tracking
```

## Usage in Workflow

This prompt is used in **Step 3** of the `generate-analyzer.skill.md` workflow, after layout analysis has been run on sample documents.

The output feeds into the schema generation step.
