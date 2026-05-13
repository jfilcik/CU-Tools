"""
PDF Segment Visualizer — Annotates a PDF with CU segmentation results.

For each page, adds:
  - A colored banner at the top showing the segment category
  - A PDF comment/annotation with segment details
  - Color-coded page borders per category
  - Segment start/end markers
  - A summary page at the end showing the full segmentation map

Usage:
    python visualize_segments.py --pdf <source.pdf> --results <results.json> --output <annotated.pdf>
    python visualize_segments.py --pdf-dir <dir> --results-dir <dir> --output-dir <dir>
"""
import argparse
import json
import sys
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    print("ERROR: PyMuPDF is required. Install with: pip install pymupdf")
    sys.exit(1)

# Distinct colors for each category (RGB tuples, 0-1 range)
CATEGORY_COLORS = {
    "1003 Borrower":               (0.20, 0.47, 0.87),   # Blue
    "1003 Additional Borrower":    (0.13, 0.59, 0.95),   # Light Blue
    "1003 Lender Loan Information":(0.00, 0.74, 0.83),   # Teal
    "1004":                        (0.18, 0.80, 0.44),   # Green
    "1004C":                       (0.30, 0.69, 0.31),   # Dark Green
    "1004D":                       (0.40, 0.73, 0.42),   # Medium Green
    "1004 Hybrid":                 (0.55, 0.76, 0.29),   # Lime Green
    "1008":                        (0.61, 0.15, 0.69),   # Purple
    "1025":                        (0.91, 0.12, 0.39),   # Pink
    "1040":                        (0.83, 0.18, 0.18),   # Red
    "1073":                        (0.94, 0.33, 0.31),   # Coral
    "1120":                        (0.75, 0.22, 0.17),   # Dark Red
    "Credit Report":               (1.00, 0.60, 0.00),   # Orange
    "Bank Statements":             (1.00, 0.76, 0.03),   # Amber
    "Borrower Closing Disclosure": (0.80, 0.86, 0.22),   # Yellow-Green
    "DU Findings":                 (0.48, 0.12, 0.64),   # Deep Purple
    "LPA Findings":                (0.40, 0.23, 0.72),   # Indigo
    "W-2":                         (0.00, 0.59, 0.53),   # Teal Green
    "Pay Stub":                    (0.00, 0.47, 0.42),   # Dark Teal
    "Tax Returns":                 (0.47, 0.33, 0.28),   # Brown
    "Tax Transcript":              (0.62, 0.47, 0.40),   # Light Brown
    "VOE":                         (0.37, 0.49, 0.55),   # Blue Grey
    "4506T":                       (0.55, 0.55, 0.55),   # Grey
    "Appraisal - ACE+ PDR":       (0.00, 0.69, 0.31),   # Emerald
    "Other":                       (0.62, 0.62, 0.62),   # Light Grey
}


def get_color(category: str) -> tuple:
    """Get color for a category, with fallback."""
    return CATEGORY_COLORS.get(category, (0.5, 0.5, 0.5))


def build_page_map(segments: list) -> dict:
    """Build a mapping from page number to segment info."""
    page_map = {}
    for seg in segments:
        start = seg["startPageNumber"]
        end = seg["endPageNumber"]
        category = seg.get("category", "Unknown")
        seg_id = seg.get("segmentId", "")
        for pg in range(start, end + 1):
            page_map[pg] = {
                "category": category,
                "segmentId": seg_id,
                "startPage": start,
                "endPage": end,
                "isFirst": pg == start,
                "isLast": pg == end,
                "pageInSegment": pg - start + 1,
                "segmentPageCount": end - start + 1,
            }
    return page_map


def annotate_pdf(pdf_path: str, results_path: str, output_path: str):
    """Annotate a PDF with segmentation results."""
    with open(results_path) as f:
        data = json.load(f)

    result = data.get("result", data)
    contents = result.get("contents", [])
    if not contents:
        print(f"  Warning: No contents in results for {pdf_path}")
        return

    segments = contents[0].get("segments", [])
    if not segments:
        print(f"  Warning: No segments found in results for {pdf_path}")
        return

    page_map = build_page_map(segments)

    doc = fitz.open(pdf_path)
    total_pages = len(doc)

    print(f"  Pages: {total_pages}, Segments: {len(segments)}")

    for page_idx in range(total_pages):
        page_num = page_idx + 1
        page = doc[page_idx]
        rect = page.rect
        width = rect.width
        height = rect.height

        seg_info = page_map.get(page_num)
        if not seg_info:
            seg_info = {
                "category": "UNCLASSIFIED",
                "segmentId": "none",
                "startPage": page_num,
                "endPage": page_num,
                "isFirst": True,
                "isLast": True,
                "pageInSegment": 1,
                "segmentPageCount": 1,
            }

        category = seg_info["category"]
        color = get_color(category)

        # --- Colored banner at top ---
        banner_height = 22
        banner_rect = fitz.Rect(0, 0, width, banner_height)
        shape = page.new_shape()
        shape.draw_rect(banner_rect)
        shape.finish(color=color, fill=color, fill_opacity=0.75)
        shape.commit()

        banner_text = (
            f"[{seg_info['segmentId']}] {category}  |  "
            f"pages {seg_info['startPage']}-{seg_info['endPage']}  "
            f"({seg_info['pageInSegment']}/{seg_info['segmentPageCount']})"
        )
        page.insert_text(
            fitz.Point(8, banner_height - 6),
            banner_text,
            fontsize=9,
            fontname="helv",
            color=(1, 1, 1),
        )

        # --- Colored border ---
        border_width = 3
        border_rect = fitz.Rect(
            border_width / 2,
            banner_height + 1,
            width - border_width / 2,
            height - border_width / 2,
        )
        shape2 = page.new_shape()
        shape2.draw_rect(border_rect)
        shape2.finish(color=color, width=border_width, fill=None)
        shape2.commit()

        # --- Segment start marker ---
        if seg_info["isFirst"]:
            marker_rect = fitz.Rect(0, banner_height, 6, banner_height + 40)
            shape3 = page.new_shape()
            shape3.draw_rect(marker_rect)
            shape3.finish(color=(0, 0.7, 0), fill=(0, 0.7, 0), fill_opacity=0.9)
            shape3.commit()
            page.insert_text(
                fitz.Point(8, banner_height + 32),
                f">>> SEGMENT START: {category}",
                fontsize=8,
                fontname="helv",
                color=color,
            )

        # --- Segment end marker ---
        if seg_info["isLast"]:
            marker_rect = fitz.Rect(0, height - 40, 6, height)
            shape4 = page.new_shape()
            shape4.draw_rect(marker_rect)
            shape4.finish(color=(0.8, 0, 0), fill=(0.8, 0, 0), fill_opacity=0.9)
            shape4.commit()
            page.insert_text(
                fitz.Point(8, height - 10),
                f"<<< SEGMENT END: {category}",
                fontsize=8,
                fontname="helv",
                color=color,
            )

        # --- Sticky note annotation ---
        comment_lines = [
            f"Segment: {seg_info['segmentId']}",
            f"Category: {category}",
            f"Pages: {seg_info['startPage']} - {seg_info['endPage']}",
            f"Page {seg_info['pageInSegment']} of {seg_info['segmentPageCount']}",
        ]
        if seg_info["isFirst"]:
            comment_lines.append("\n>>> SEGMENT START")
        if seg_info["isLast"]:
            comment_lines.append("\n<<< SEGMENT END")

        comment_text = "\n".join(comment_lines)
        annot = page.add_text_annot(fitz.Point(width - 25, 2), comment_text)
        annot.set_info(title="CU Segmentation", subject=category)
        annot.set_colors({"stroke": color})
        annot.update()

    # --- Summary page ---
    _add_summary_pages(doc, segments, pdf_path, total_pages)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    doc.save(output_path)
    doc.close()
    print(f"  Saved: {output_path}")


def _add_summary_pages(doc, segments, pdf_path, total_pages):
    """Add summary page(s) at the end of the document."""
    summary_page = doc.new_page(width=612, height=792)
    y = 40

    summary_page.insert_text(
        fitz.Point(40, y),
        "CU Segmentation Summary",
        fontsize=16, fontname="helv", color=(0, 0, 0),
    )
    y += 25

    pdf_name = Path(pdf_path).name
    summary_page.insert_text(
        fitz.Point(40, y),
        f"Document: {pdf_name}  |  Total pages: {total_pages}  |  Segments: {len(segments)}",
        fontsize=10, fontname="helv", color=(0.3, 0.3, 0.3),
    )
    y += 30

    # Header
    summary_page.insert_text(
        fitz.Point(56, y),
        f"{'Seg':<12} {'Category':<34} {'Pages':<14} {'Count':<6}",
        fontsize=9, fontname="cour", color=(0, 0, 0),
    )
    y += 4
    shape_s = summary_page.new_shape()
    shape_s.draw_line(fitz.Point(40, y), fitz.Point(560, y))
    shape_s.finish(color=(0.5, 0.5, 0.5), width=0.5)
    shape_s.commit()
    y += 14

    for seg in segments:
        category = seg.get("category", "Unknown")
        seg_id = seg.get("segmentId", "")
        start = seg["startPageNumber"]
        end = seg["endPageNumber"]
        count = end - start + 1
        color = get_color(category)

        # Color swatch
        swatch_rect = fitz.Rect(40, y - 8, 52, y)
        shape_sw = summary_page.new_shape()
        shape_sw.draw_rect(swatch_rect)
        shape_sw.finish(color=color, fill=color)
        shape_sw.commit()

        row = f"{seg_id:<12} {category:<34} {start:>4} - {end:<4}     {count:>3}"
        summary_page.insert_text(
            fitz.Point(56, y), row,
            fontsize=9, fontname="cour", color=(0.1, 0.1, 0.1),
        )
        y += 16

        if y > 750:
            summary_page = doc.new_page(width=612, height=792)
            y = 40
            summary_page.insert_text(
                fitz.Point(40, y),
                "CU Segmentation Summary (continued)",
                fontsize=14, fontname="helv", color=(0, 0, 0),
            )
            y += 30

    # Legend
    y += 20
    if y < 720:
        summary_page.insert_text(
            fitz.Point(40, y), "Legend:",
            fontsize=10, fontname="helv", color=(0, 0, 0),
        )
        y += 16
        summary_page.insert_text(
            fitz.Point(40, y),
            "Green bar = Segment start  |  Red bar = Segment end  |  Banner = Category",
            fontsize=9, fontname="helv", color=(0.3, 0.3, 0.3),
        )
        y += 14
        summary_page.insert_text(
            fitz.Point(40, y),
            "Click sticky notes (top-right corner) for full segment details.",
            fontsize=9, fontname="helv", color=(0.3, 0.3, 0.3),
        )


def main():
    parser = argparse.ArgumentParser(
        description="Annotate PDF with CU segmentation results"
    )
    parser.add_argument("--pdf", help="Path to source PDF")
    parser.add_argument("--results", help="Path to CU results JSON")
    parser.add_argument("--output", help="Path for annotated output PDF")
    parser.add_argument("--pdf-dir", help="Directory of source PDFs")
    parser.add_argument("--results-dir", help="Directory of result JSONs")
    parser.add_argument("--output-dir", help="Directory for annotated PDFs")
    args = parser.parse_args()

    if args.pdf and args.results:
        output = args.output or str(Path(args.pdf).stem) + "_annotated.pdf"
        print(f"Annotating: {args.pdf}")
        annotate_pdf(args.pdf, args.results, output)
    elif args.pdf_dir and args.results_dir:
        pdf_dir = Path(args.pdf_dir)
        results_dir = Path(args.results_dir)
        output_dir = Path(args.output_dir or "annotated_output")
        output_dir.mkdir(parents=True, exist_ok=True)

        pdf_files = sorted(pdf_dir.glob("*.pdf"))
        print(f"Found {len(pdf_files)} PDFs in {pdf_dir}")

        for pdf_file in pdf_files:
            result_file = results_dir / f"{pdf_file.stem}.json"
            if not result_file.exists():
                print(f"  Skipping {pdf_file.name} — no matching results")
                continue
            output_file = output_dir / f"{pdf_file.stem}_segmented.pdf"
            print(f"\nAnnotating: {pdf_file.name}")
            try:
                annotate_pdf(str(pdf_file), str(result_file), str(output_file))
            except Exception as e:
                print(f"  Error: {e}")
                import traceback
                traceback.print_exc()
    else:
        parser.print_help()
        print("\nExamples:")
        print("  Single:  python visualize_segments.py --pdf doc.pdf --results result.json --output out.pdf")
        print("  Batch:   python visualize_segments.py --pdf-dir files/ --results-dir results/ --output-dir annotated/")


if __name__ == "__main__":
    main()
