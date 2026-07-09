r"""
Flatten PDF form-field (/Annot Text Widget) values into the page content stream.

Why this exists
---------------
Azure AI Content Understanding (and OCR pipelines generally) can use a PDF's
embedded digital text -- the text in the page CONTENT STREAM -- to refine or
bypass OCR. In a *fillable* AcroForm PDF, the values you type live in the widget
appearance streams of each `/Annot` object, NOT in the page content stream. That
text is invisible to the content-stream refinement, so CU rasterizes the page and
OCRs it -- which can misread confusable glyphs (I<->l, 0<->O, rn<->m, ...).

This script "bakes" every widget's value into the page content stream so it becomes
real, extractable digital text. The output is born-digital (a genuine text layer),
NOT a re-rendered image, so no quality is lost.

Usage
-----
    pip install pymupdf

    # one file
    python flatten_annot_to_content.py fillable.pdf

    # a folder (writes <name>.flat.pdf next to each, or into --out)
    python flatten_annot_to_content.py samples\ --out flattened\

Verify the fix
--------------
    import fitz
    doc = fitz.open("fillable.flat.pdf")
    print("\n".join(p.get_text() for p in doc))   # field values now appear
"""
from __future__ import annotations

import sys
from pathlib import Path

import fitz  # PyMuPDF >= 1.24 (provides Document.bake)


def flatten(src: Path, dst: Path) -> tuple[int, int]:
    """Bake widget (/Annot) text into the content stream. Returns (widgets_before, after)."""
    doc = fitz.open(src)
    before = sum(1 for page in doc for _ in (page.widgets() or []))

    # The one line that does the work: render each widget's appearance (real text
    # operators) into the page content stream and drop the interactive widget.
    doc.bake(annots=False, widgets=True)

    after = sum(1 for page in doc for _ in (page.widgets() or []))
    dst.parent.mkdir(parents=True, exist_ok=True)
    doc.save(dst, garbage=4, deflate=True, clean=True)
    doc.close()
    return before, after


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2

    args = list(argv)
    out_dir: Path | None = None
    if "--out" in args:
        i = args.index("--out")
        out_dir = Path(args[i + 1])
        del args[i : i + 2]

    target = Path(args[0])
    if target.is_dir():
        pdfs = sorted(target.glob("*.pdf"))
    elif target.is_file():
        pdfs = [target]
    else:
        print(f"Not found: {target}")
        return 1
    if not pdfs:
        print(f"No PDFs in {target}")
        return 1

    for pdf in pdfs:
        dst = (out_dir / pdf.name) if out_dir else pdf.with_suffix(".flat.pdf")
        before, after = flatten(pdf, dst)
        print(f"{pdf.name}: flattened {before} widget(s) -> content stream  =>  {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
