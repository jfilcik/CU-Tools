# CUAD benchmark data

`cuad_manifest.json` pins the official CUAD revision and archive checksum. Run:

```powershell
python scripts\download_cuad.py
python scripts\prepare_cuad_eval.py
```

The scripts verify the checksum, reject unsafe ZIP entries, select 5 development and 20 held-out contracts deterministically, write text samples under `samples/downloaded/`, and generate clause-span ground truth locally.

The pinned GitHub `data.zip` contains annotation JSON only. It does not contain
PDF, DOC, DOCX, or standalone TXT files. The full CUAD distribution is also
published on Hugging Face with original PDFs. After preparing the deterministic
selection, download the corresponding held-out PDFs with:

```powershell
python scripts\download_cuad_pdfs.py
```

`cuad_pdf_manifest.json` pins the Hugging Face dataset revision. The downloader
requires exactly one normalized title match per selected contract, verifies the
PDF signature, and records source paths and SHA-256 hashes in the ignored output
directory's `download_manifest.json`.

Downloaded contract text, generated clause quotations, and selection manifests are intentionally gitignored. Review the CUAD license and attribution requirements before redistributing any generated artifacts.
