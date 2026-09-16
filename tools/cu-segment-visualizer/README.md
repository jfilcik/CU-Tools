# PDF segment visualizer

Annotate a source PDF using saved CU segmentation evidence. Native CLI
`contents` and historical `result.contents` are supported, including classified
content entries with page ranges and the older nested `segments` array.

```powershell
python tools\cu-segment-visualizer\visualize_segments.py `
  --pdf .\packet.pdf --results .\packet.pdf.result.json --output .\annotated.pdf

python tools\cu-segment-visualizer\visualize_segments.py `
  --pdf-dir .\documents --results-dir .\results --output-dir .\annotated
```

Batch discovery preserves relative subdirectories and accepts native
`packet.pdf.result.json` or saved `packet.json`. Multiple matching results
are ambiguous: use explicit single-file arguments. Missing results or invalid
page segmentation fail rather than silently producing a successful batch.
`content_N` labels identify content entries locally when no service segment ID
is present; they are not service-generated IDs.

Requires PyMuPDF. No service calls or credentials are used. Related regression
tests live in `tools\cu-reading-order-viz\tests\test_cli_results.py`.
