# Reading Order Visualizer

Creates annotated PDFs showing numbered bounding boxes with reading-order arrows overlaid on original document pages. Useful for diagnosing reading order issues in Azure AI Content Understanding layout extraction.

## Features

- **Numbered bounding boxes** — each paragraph gets a colored box with sequence number
- **Rainbow gradient** — reading order visualized as red→orange→yellow→green→cyan→blue→purple
- **Directional arrows** — show reading order flow between consecutive paragraphs
- **Auto-detection** — handles native CLI CU, saved CU envelopes, and Document Intelligence JSON
- **Batch mode** — recursively matches source-relative paths without flattening duplicate names
- **Comparison mode** — side-by-side visualization of two layout sources
- **Page filtering** — visualize specific pages only

## Usage

```bash
# Single document
python visualize_reading_order.py --pdf document.pdf --layout document.layout.json -o output/

# Batch mode (all PDFs in a folder)
python visualize_reading_order.py --input-dir samples/ --layout-dir layout_results/ -o output/

# Compare CU and Document Intelligence layout results
python visualize_reading_order.py --pdf doc.pdf --layout-a cu.json --layout-b di.json -o output/

# Specific pages only
python visualize_reading_order.py --pdf doc.pdf --layout doc.json -o output/ --pages 1-3,18
```

## Dependencies

```
PyMuPDF (fitz)
Pillow
```

## JSON Format Support

| Format | Detection | Source |
|--------|-----------|--------|
| Native CLI CU | `contents[].paragraphs` with `source: "D(page,...)"` | Official `cu analyze --json` |
| CU envelope | `result.contents[].paragraphs` with `source: "D(page,...)"` | Native LRO or historical results |
| DI | `analyzeResult.paragraphs` with `boundingRegions` | Document Intelligence |

The tool auto-detects the format — no manual specification needed.

Capture new layout JSON with `cu analyze FILE --analyzer prebuilt-layout
--json --output-dir DIRECTORY`. Native batch names such as
`subfolder/invoice.pdf.result.json` and saved `invoice.layout.json`/`invoice.json`
are supported. Multiple matching results are ambiguous: select one explicitly
with `--layout`. Unknown/malformed payloads fail instead of producing a
success-shaped empty visualization.
