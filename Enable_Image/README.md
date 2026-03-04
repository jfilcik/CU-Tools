# Experimental enableImage Flag for Azure Content Understanding

> **Status**: Private Preview / Experimental  
> **Recommended Model**: GPT-4.1

## Overview

The `enableImage` flag is an experimental configuration option that enables **multimodal document analysis** in Azure Content Understanding. When enabled, CU sends both OCR-extracted markdown **and** full-page rendered images to the GPT model, allowing the model to use visual context for improved extraction accuracy.

### How It Works

```
┌─────────────────┐     ┌──────────────────────────────────────┐
│   PDF Document  │────▶│  Azure Content Understanding (CU)    │
└─────────────────┘     │                                      │
                        │  1. OCR extracts text → Markdown     │
                        │  2. Renders each page → Images       │
                        │                                      │
                        │  Both sent to GPT for extraction     │
                        └──────────────────────────────────────┘
                                          │
                                          ▼
                        ┌──────────────────────────────────────┐
                        │         GPT-4.1 (Multimodal)         │
                        │                                      │
                        │  Analyzes markdown + images together │
                        │  for improved spatial understanding  │
                        └──────────────────────────────────────┘
```

This dual-channel approach helps the model interpret:
- Spatial relationships between fields
- Two-column layouts where text order differs from visual order
- Checkbox positions and their associated labels
- Grid-based forms where position determines meaning

---

## When to Use enableImage

### Recommended Use Cases

| Scenario | Why enableImage Helps |
|----------|----------------------|
| **Two-column layouts** (e.g., K-1 tax forms) | OCR may serialize columns incorrectly; images preserve visual structure |
| **Checkbox-heavy forms** | Visual position of checkboxes relative to labels is critical |
| **Grid-based documents** | Row/column alignment visible in images but lost in text |
| **Forms with boxed fields** | Box boundaries help identify field groupings |
| **Documents with position-dependent meaning** | Same text in different positions means different things |

### When NOT to Use

| Scenario | Reason |
|----------|--------|
| **Latency-critical applications** | Processing time may double (e.g., 55-60s → 100-120s) |
| **Simple single-column documents** | Standard extraction works well; images add no value |
| **Low-resolution scans** | Poor image quality may hurt rather than help |
| **High-volume processing** | Increased latency and cost may not be justified |

---

## Observed Results

### Benefits
- **+8.7% accuracy improvement** observed in K-1 form test suite
- Fixes checkbox fields that depend on spatial layout (e.g., K-1 K3 checkbox)
- Supports field descriptions referencing visual cues (box labels, column positions, superscripts)

### Limitations
- Results vary by document type, image quality, and field complexity
- Some fine-detail extractions (e.g., superscripts) still have low reliability
- Not all documents show improvement—testing is essential

---

## Configuration

Add the `_experimental` block to your analyzer's `config` section:

```json
{
  "config": {
    "returnDetails": true,
    "enableOcr": true,
    "enableLayout": true,
    "enableFormula": true,
    "enableFigureDescription": true,
    "enableFigureAnalysis": true,
    "chartFormat": "chartjs",
    "disableContentFiltering": true,
    "tableFormat": "html",
    "estimateFieldSourceAndConfidence": true,
    "enableSegment": false,
    "omitContent": false,
    "segmentPerPage": false,
    "enableAnnotations": true,
    "annotationFormat": "markdown",
    "_experimental": {
      "enableImage": "true"
    }
  }
}
```

> **Important**: The flag must be set when **creating** the analyzer. It cannot be added to an existing analyzer.

---

## Schema Design Best Practices

When using `enableImage`, optimize your field descriptions to leverage visual context:

### Use VISUAL Prefixes

Add `VISUAL:` to field descriptions where image context helps:

```json
{
  "partnerName": {
    "type": "string",
    "method": "extract",
    "description": "The partner's name. VISUAL: Look for the name field in the left column, near 'Part II - Information About the Partner'."
  }
}
```

### Describe Checkbox Appearance

Be explicit about how checkmarks may appear:

```json
{
  "isFinalReturn": {
    "type": "boolean",
    "method": "extract",
    "description": "VISUAL: Check if the 'Final K-1' checkbox is marked. Check marks may appear as X, ✓, filled boxes, or handwritten marks. Return true if marked, false if empty."
  }
}
```

### Reference Spatial Locations

Use location-based descriptions:

```json
{
  "partnershipEIN": {
    "type": "string",
    "method": "extract",
    "description": "VISUAL: The EIN in the upper-left section of Part I, directly below the partnership name. Format: XX-XXXXXXX."
  }
}
```

---

## Testing Workflow

### Before Testing
1. Gather representative input samples (minimum 3-5 documents)
2. Build a ground truth table with expected field values
3. Run baseline extraction without enableImage to understand current accuracy

### During Testing
1. Create an analyzer WITH enableImage (see HTTP file)
2. Create a comparison analyzer WITHOUT enableImage
3. Process the same documents with both analyzers
4. Compare:
   - Field accuracy (especially checkboxes and spatial fields)
   - Confidence scores (`estimateFieldSourceAndConfidence`)
   - Processing time

### Evaluation
- Change one variable at a time
- Document accuracy metrics between runs
- Focus on fields where visual context matters most

---

## Using the HTTP Test File

This folder includes an HTTP test file (`enableImage-Guide.http`) with ready-to-use API requests.

### Prerequisites

Follow the setup instructions in the [CU API Testing Guide README](../CU_API_Testing/README.md):
1. Install the VS Code REST Client extension
2. Create a `.env` file with your credentials
3. Ensure GPT-4.1 model deployment is configured

### What's Included

The HTTP file provides:

| Section | Description |
|---------|-------------|
| **3.1** | Check model deployments |
| **3.2** | Create analyzer WITH enableImage |
| **3.3** | Verify analyzer was created correctly |
| **3.4** | Create comparison analyzer WITHOUT enableImage |
| **4.1-4.2** | Analyze documents with enableImage |
| **4.3-4.4** | Analyze documents without enableImage |
| **5.1** | Cleanup (delete test analyzers) |

### Example Workflow

1. Open `enableImage-Guide.http` in VS Code
2. Run **3.2** to create the enableImage analyzer
3. Run **3.3** to verify the `_experimental.enableImage` flag is present
4. Replace `YOUR_DOCUMENT_URL_HERE` with your document URL
5. Run **4.1** to start analysis, then **4.2** to get results
6. Compare with non-enableImage results from **4.3** and **4.4**

---

## Troubleshooting

### How do I confirm enableImage was applied?

GET your analyzer definition and verify `_experimental.enableImage` is present in the config response:

```http
GET {endpoint}/contentunderstanding/analyzers/{analyzerName}?api-version=2025-11-01
```

### Results aren't improving with enableImage?

- Add `VISUAL:` prefixes to field descriptions
- Ensure your document has clear visual structure that benefits from image analysis
- Some document types may not benefit—standard extraction may already work well

### Extraction is too slow?

enableImage approximately doubles processing time. Consider:
- Is the accuracy improvement worth the latency cost?
- Can you use it selectively for complex documents only?
- Is batch processing acceptable for your use case?

---

## Prompt Structure (Internal Reference)

When `enableImage=true`, CU sends this structure to GPT:

```json
{
  "role": "system",
  "content": "You will be given a Document and its corresponding images. Read the images carefully..."
},
{
  "role": "user",
  "content": [
    { "type": "text", "text": "```markdown\n<document markdown>\n```" },
    { "type": "image_url", "image_url": { "url": "data:image/png;base64,...", "detail": "high" } }
  ]
}
```

---

## Documentation

- [Azure Content Understanding Overview](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/overview)
- [REST API Reference](https://learn.microsoft.com/en-us/rest/api/contentunderstanding/operation-groups)
- [Content Understanding Studio](https://aka.ms/cu-studio)

---

## Feedback

This is an **experimental feature**. We welcome feedback to help improve extraction accuracy for visually complex documents. Please share:
- Document types where enableImage helped (or didn't help)
- Accuracy metrics and comparisons
- Schema design patterns that worked well
