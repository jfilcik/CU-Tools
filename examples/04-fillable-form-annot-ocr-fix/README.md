# Fillable-form `/Annot` text → OCR misreads (and the one-line fix)

**TL;DR** — In a *fillable* PDF, the values you type live in the form-field widget
(`/Annot` Text Widget) appearance streams, **not** in the page content stream. Azure
AI Content Understanding (like most OCR pipelines) uses the content-stream digital
text to refine/skip OCR — but it can't see widget text, so it **rasterizes and OCRs
the page**, which misreads confusable glyphs (`I`↔`l`, `0`↔`O`, `rn`↔`m`, …).
**Fix:** flatten the widget text into the content stream. Then CU reads it as digital
text and the misreads disappear. One line: `doc.bake(widgets=True)`.

---

## The problem

Content Understanding runs a two-stage pipeline. For born-digital PDFs it leverages
the embedded text in the **page content stream** to refine — or entirely bypass — OCR.

A fillable AcroForm looks born-digital, but the filled-in values are stored
differently. Each form field is a `/Annot` **Text Widget** whose value is drawn by
its own *appearance stream*:

```
Fillable PDF
├── page content stream  →  static form text ("Debtor 1", "State", ...)  ← CU reads this
└── /Annot Widgets
    ├── "Debtor 1"  value="Nathan WIlliams"   (in widget appearance stream)  ← CU does NOT read this
    ├── "State 3b"  value="Fl"                (in widget appearance stream)  ← "
    └── ...
```

Because the typed values aren't in the content stream, CU's digital-text refinement
never fires for them. It falls back to rasterizing the page and OCR'ing the pixels,
and OCR then confuses look-alike glyphs.

### Quick way to confirm you're hitting this

```python
import fitz  # pip install pymupdf
doc = fitz.open("your_form.pdf")
print("interactive widgets:", sum(1 for p in doc for _ in (p.widgets() or [])))
```

If that count is `> 0`, the field values are in `/Annot` widgets and are invisible
to content-stream text refinement.

---

## The fix

Flatten (a.k.a. "bake") each widget's value into the page content stream. This
renders the widget's *real text operators* into the page — producing genuine,
extractable digital text. It is **not** a re-rasterized image, so nothing is lost.

```python
import fitz  # pip install pymupdf

doc = fitz.open("fillable.pdf")
doc.bake(annots=False, widgets=True)   # ← flatten /Annot widget text into content stream
doc.save("fillable.flat.pdf", garbage=4, deflate=True, clean=True)
```

A ready-to-run version is in [`flatten_annot_to_content.py`](flatten_annot_to_content.py):

```bash
pip install pymupdf
python flatten_annot_to_content.py samples\ --out flattened\
```

Then send the flattened PDF to Content Understanding instead of the fillable one.

---

## Synthetic example + measured results

The [`samples/`](samples/) folder contains three **synthetic, PII-free** Official
Form 410 (Proof of Claim) filings — fillable AcroForms, each engineered to contain
one classic OCR-confusion trigger. Running CU `prebuilt-layout` on the fillable
originals vs. the flattened output:

| Sample | Field | Correct value | Fillable (`/Annot`) → CU OCR | Flattened (content stream) → CU |
|--------|-------|---------------|------------------------------|---------------------------------|
| `SYN_FULL_04` | State | `Fl` | `FI` ❌ (`l`→`I`) | `Fl` ✅ |
| `SYN_FULL_05` | Uniform claim id | `0 T V E …` | `O TVE …` ❌ (`0`→`O`) | `0 T V E …` ✅ |
| `SYN_MIX_04` | Debtor 1 | `Nathan WIlliams` | `Nathan Wllliams` ❌ (`I`→`l`) | `Nathan WIlliams` ✅ |

All three misreads disappear once the text is in the content stream. The confusion
is glyph-driven and location-driven: same glyphs, but reading them from the content
stream instead of OCR'ing pixels fixes it.

> Reproduce: `python flatten_annot_to_content.py samples\ --out flattened\`, then run
> your CU `prebuilt-layout` call on `samples\` (before) and `flattened\` (after) and
> compare the field reads.

---

## When to use this

- ✅ **Fillable AcroForm PDFs** where users typed values into form fields
  (interactive widget count `> 0`).
- ✅ You want CU to read the values as digital text and avoid OCR glyph confusion.
- ❌ **Truly scanned / image-only PDFs** — there's no widget text to flatten; OCR is
  unavoidable and the fix doesn't apply.

## Notes / caveats

- Requires **PyMuPDF ≥ 1.24** (`Document.bake`). Tested on 1.27.
- `bake` is irreversible for the output file — the form stops being interactive
  (that's the point). Keep the original if you still need the editable form.
- `annots=False` leaves non-widget annotations (highlights, stamps) untouched; set
  `annots=True` if you also want those flattened.
- Checkboxes/radios/signatures are flattened too (their appearance is baked in).

---

*Background: this came out of a real customer case where a fillable Proof-of-Claim
form's field values were being OCR-misread. Root cause: field text lived in `/Annot`
widgets, not the content stream. Samples here are synthetic — no customer data.*
