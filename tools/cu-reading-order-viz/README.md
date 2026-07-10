# Reading Order Visualizer

Creates annotated PDFs showing numbered bounding boxes with reading-order arrows overlaid on original document pages. Useful for diagnosing reading order issues in Azure AI Content Understanding layout extraction.

## Features

- **Numbered bounding boxes** — each paragraph gets a colored box with sequence number
- **Rainbow gradient** — reading order visualized as red→orange→yellow→green→cyan→blue→purple
- **Directional arrows** — show reading order flow between consecutive paragraphs
- **Auto-detection** — handles both CU (prod) and Document Intelligence (selfhost) JSON formats
- **Batch mode** — process entire folders of PDFs at once
- **Comparison mode** — side-by-side visualization of two layout sources
- **Page filtering** — visualize specific pages only

## Usage

```bash
# Single document
python visualize_reading_order.py --pdf document.pdf --layout document.layout.json -o output/

# Batch mode (all PDFs in a folder)
python visualize_reading_order.py --input-dir samples/ --layout-dir layout_results/ -o output/

# Compare two layout sources (e.g., prod vs selfhost)
python visualize_reading_order.py --pdf doc.pdf --layout-a prod.json --layout-b selfhost.json -o output/

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
| CU (prod) | `result.contents[0].paragraphs` with `source: "D(page,...)"` | Azure AI Content Understanding |
| DI (selfhost) | `analyzeResult.paragraphs` with `boundingRegions` | Document Intelligence |

The tool auto-detects the format — no manual specification needed.
