# Local field viewer

Open `cuDocVisualizer.html` beside `run_files.js`. Load individual PDF/image
and result JSON files, or select a folder containing native CLI
`*.result.json` results. Saved legacy folders with `metadata.json` still work.

Native root `contents` and saved `result.contents` are supported. Recursive
paths distinguish identical filenames across analyzers/trials. Source documents
are matched by exact path or a unique basename; ambiguous matches require
manual document selection, never a guessed document.

This is a result viewer, not an evaluator or experiment-status reporter.
Native files are labeled available, not successful; missing planned results
and costs are not inferred. Use the experiment manifest and CLI status reports
for outcome denominators. Selected files are read locally; the existing PDF.js
library is loaded from a public CDN, so the viewer needs access to that asset.

Run the offline file-index tests with:

```powershell
node --test tools\cu-visualize\tests\run_files.test.js tools\cu-visualize\tests\browser_loader.test.js
```
