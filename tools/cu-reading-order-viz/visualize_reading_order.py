"""
Reading Order Visualizer for CU Layout Results

Creates annotated PDFs showing numbered bounding boxes with reading-order arrows
overlaid on the original PDF pages. Useful for diagnosing reading order issues
in Azure AI Content Understanding layout extraction.

Usage:
    # Single document
    python visualize_reading_order.py --pdf document.pdf --layout layout.json --output out/

    # Batch mode (folder of PDFs + matching layout JSONs)
    python visualize_reading_order.py --input-dir samples/ --layout-dir layout_results/ --output out/

    # Specific pages only
    python visualize_reading_order.py --pdf doc.pdf --layout doc.layout.json --output out/ --pages 1-3,5

    # Compare two layout sources (e.g., prod vs selfhost)
    python visualize_reading_order.py --pdf doc.pdf --layout-a prod.json --layout-b selfhost.json --output out/
"""

import argparse
import json
import math
import re
import sys
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    sys.exit("ERROR: PyMuPDF required. Install with: pip install PyMuPDF")

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    sys.exit("ERROR: Pillow required. Install with: pip install Pillow")


# ─── Configuration ───────────────────────────────────────────────────────────

GRADIENT_STOPS = [
    (220, 40, 40),    # red
    (240, 130, 30),   # orange
    (200, 190, 30),   # yellow
    (40, 180, 60),    # green
    (30, 180, 180),   # cyan
    (50, 80, 210),    # blue
    (140, 40, 200),   # purple
]

NUMBER_COLOR = (255, 255, 255, 255)
DPI = 150


# ─── Color Utilities ─────────────────────────────────────────────────────────

def get_gradient_color(index, total, alpha=70):
    """Get a color from the gradient based on position in sequence."""
    if total <= 1:
        return GRADIENT_STOPS[0] + (alpha,)
    t = index / (total - 1)
    pos = t * (len(GRADIENT_STOPS) - 1)
    idx = int(pos)
    frac = pos - idx
    if idx >= len(GRADIENT_STOPS) - 1:
        c = GRADIENT_STOPS[-1]
    else:
        c1 = GRADIENT_STOPS[idx]
        c2 = GRADIENT_STOPS[idx + 1]
        c = tuple(int(c1[i] + (c2[i] - c1[i]) * frac) for i in range(3))
    return c + (alpha,)


# ─── JSON Parsing ────────────────────────────────────────────────────────────

def parse_source_polygon(source_str):
    """Parse CU source string: D(page, x1,y1, x2,y2, x3,y3, x4,y4)"""
    m = re.match(
        r"D\((\d+),([\d.]+),([\d.]+),([\d.]+),([\d.]+),([\d.]+),([\d.]+),([\d.]+),([\d.]+)\)",
        source_str
    )
    if not m:
        return None, None
    page = int(m.group(1))
    polygon = [float(m.group(i)) for i in range(2, 10)]
    return page, polygon


def extract_paragraphs_cu(json_path):
    """Extract paragraphs from CU layout JSON (prod format)."""
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    # CU format: result.contents[0].paragraphs with source field
    content_obj = data.get("result", {}).get("contents", [{}])[0]

    pages_info = {}
    for p in content_obj.get("pages", []):
        pages_info[p["pageNumber"]] = {
            "width": p.get("width", 8.5),
            "height": p.get("height", 11)
        }

    paragraphs_by_page = {}
    for idx, para in enumerate(content_obj.get("paragraphs", [])):
        role = para.get("role", "")
        content_text = para.get("content", "")
        source = para.get("source", "")
        page, polygon = parse_source_polygon(source)
        if page is None:
            continue
        if page not in paragraphs_by_page:
            paragraphs_by_page[page] = []
        paragraphs_by_page[page].append({
            "idx": idx,
            "role": role,
            "content": content_text[:80],
            "polygon": polygon,
        })

    return pages_info, paragraphs_by_page


def extract_paragraphs_di(json_path):
    """Extract paragraphs from Document Intelligence (selfhost) JSON."""
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    ar = data.get("analyzeResult", {})
    pages_info = {}
    for p in ar.get("pages", []):
        pages_info[p["pageNumber"]] = {"width": p["width"], "height": p["height"]}

    paragraphs_by_page = {}
    for idx, para in enumerate(ar.get("paragraphs", [])):
        role = para.get("role", "")
        content = para.get("content", "")
        for br in para.get("boundingRegions", []):
            page = br["pageNumber"]
            polygon = br["polygon"]
            if page not in paragraphs_by_page:
                paragraphs_by_page[page] = []
            paragraphs_by_page[page].append({
                "idx": idx,
                "role": role,
                "content": content[:80],
                "polygon": polygon,
            })

    return pages_info, paragraphs_by_page


def detect_format(json_path):
    """Auto-detect whether JSON is CU (prod) or DI (selfhost) format."""
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    if "result" in data and "contents" in data.get("result", {}):
        return "cu"
    elif "analyzeResult" in data:
        return "di"
    else:
        return "unknown"


def extract_paragraphs(json_path):
    """Auto-detect format and extract paragraphs."""
    fmt = detect_format(json_path)
    if fmt == "cu":
        return extract_paragraphs_cu(json_path)
    elif fmt == "di":
        return extract_paragraphs_di(json_path)
    else:
        print(f"  ⚠️ Unknown JSON format: {json_path}")
        return {}, {}


# ─── Drawing ─────────────────────────────────────────────────────────────────

def polygon_to_rect(polygon, scale_x, scale_y):
    """Convert polygon [x1,y1,...x4,y4] to bounding rect in pixels."""
    xs = [polygon[i] * scale_x for i in range(0, 8, 2)]
    ys = [polygon[i] * scale_y for i in range(1, 8, 2)]
    return min(xs), min(ys), max(xs), max(ys)


def polygon_center(polygon, scale_x, scale_y):
    """Get center point of polygon in pixels."""
    xs = [polygon[i] * scale_x for i in range(0, 8, 2)]
    ys = [polygon[i] * scale_y for i in range(1, 8, 2)]
    return sum(xs) / 4, sum(ys) / 4


def draw_arrow(draw, start, end, color, width=2):
    """Draw an arrow from start to end."""
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    dist = math.sqrt(dx * dx + dy * dy)
    if dist < 10:
        return

    shorten = 8
    if dist > shorten * 2:
        ratio_start = shorten / dist
        ratio_end = 1 - shorten / dist
        sx = start[0] + dx * ratio_start
        sy = start[1] + dy * ratio_start
        ex = start[0] + dx * ratio_end
        ey = start[1] + dy * ratio_end
    else:
        sx, sy = start
        ex, ey = end

    draw.line([(sx, sy), (ex, ey)], fill=color, width=width)

    angle = math.atan2(ey - sy, ex - sx)
    arrow_len = 8
    a1 = angle + math.pi * 0.8
    a2 = angle - math.pi * 0.8
    draw.polygon([
        (ex, ey),
        (ex + arrow_len * math.cos(a1), ey + arrow_len * math.sin(a1)),
        (ex + arrow_len * math.cos(a2), ey + arrow_len * math.sin(a2)),
    ], fill=color)


def try_load_font(size):
    """Try to load a font, fallback to default."""
    for path in ["arial.ttf", "C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def render_page(page_img, paragraphs, page_width, page_height, label=""):
    """Render bboxes, numbers, and arrows on a page image."""
    img = page_img.copy().convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    img_w, img_h = img.size
    scale_x = img_w / page_width
    scale_y = img_h / page_height

    font_num = try_load_font(11)
    total = len(paragraphs)
    centers = []

    for i, para in enumerate(paragraphs):
        polygon = para["polygon"]
        rect = polygon_to_rect(polygon, scale_x, scale_y)
        center = polygon_center(polygon, scale_x, scale_y)
        centers.append(center)

        fill = get_gradient_color(i, total, alpha=60)
        border = get_gradient_color(i, total, alpha=200)
        num_bg = get_gradient_color(i, total, alpha=220)

        draw.rectangle(rect, fill=fill, outline=border, width=2)

        # Number badge
        num_str = str(i + 1)
        bbox = font_num.getbbox(num_str)
        tw = bbox[2] - bbox[0] + 6
        th = bbox[3] - bbox[1] + 4
        nx = rect[0]
        ny = rect[1] - th - 1
        if ny < 0:
            ny = rect[1] + 1
        draw.rectangle([nx, ny, nx + tw, ny + th], fill=num_bg)
        draw.text((nx + 3, ny + 1), num_str, fill=NUMBER_COLOR, font=font_num)

    # Arrows connecting sequential paragraphs
    for i in range(len(centers) - 1):
        arrow_c = get_gradient_color(i, total, alpha=100)
        draw_arrow(draw, centers[i], centers[i + 1], arrow_c, width=1)

    result = Image.alpha_composite(img, overlay).convert("RGB")

    if label:
        label_draw = ImageDraw.Draw(result)
        font_label = try_load_font(16)
        label_draw.rectangle([0, 0, img_w, 22], fill=(40, 40, 40))
        label_draw.text((5, 3), label, fill=(255, 255, 255), font=font_label)

    return result


# ─── PDF Generation ──────────────────────────────────────────────────────────

def render_pdf_pages(pdf_path, dpi=DPI):
    """Render PDF pages to PIL Images using PyMuPDF."""
    doc = fitz.open(str(pdf_path))
    images = []
    for page in doc:
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        images.append(img)
    doc.close()
    return images


def create_visualization_pdf(pdf_path, json_path, output_path, pages_filter=None, label_prefix=""):
    """Create annotated PDF with reading order bbox overlays."""
    fmt = detect_format(json_path)
    print(f"  Format: {fmt} | Rendering PDF pages...")
    page_images = render_pdf_pages(pdf_path)
    pages_info, paragraphs_by_page = extract_paragraphs(json_path)

    annotated_pages = []
    page_numbers = pages_filter or range(1, len(page_images) + 1)

    for page_num in page_numbers:
        if page_num > len(page_images):
            continue

        page_img = page_images[page_num - 1]
        info = pages_info.get(page_num, {"width": 8.5, "height": 11})
        paras = paragraphs_by_page.get(page_num, [])

        label = f"{label_prefix}Page {page_num} — {len(paras)} paragraphs"
        annotated = render_page(page_img, paras, info["width"], info["height"], label=label)
        annotated_pages.append(annotated)
        print(f"    Page {page_num}: {len(paras)} paragraphs")

    if annotated_pages:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        annotated_pages[0].save(
            str(output_path), "PDF", save_all=True,
            append_images=annotated_pages[1:], resolution=DPI
        )
        print(f"  ✓ Saved: {output_path} ({len(annotated_pages)} pages)")
    else:
        print(f"  ⚠️ No pages to render for {pdf_path.name}")


def create_comparison_pdf(pdf_path, json_a, json_b, output_path, pages_filter=None, doc_name=""):
    """Create side-by-side comparison PDF (source A then B per page)."""
    print(f"  Rendering comparison PDF...")
    page_images = render_pdf_pages(pdf_path)

    fmt_a = detect_format(json_a)
    fmt_b = detect_format(json_b)
    pages_info_a, paras_a = extract_paragraphs(json_a)
    pages_info_b, paras_b = extract_paragraphs(json_b)

    annotated_pages = []
    page_numbers = pages_filter or range(1, len(page_images) + 1)

    for page_num in page_numbers:
        if page_num > len(page_images):
            continue

        page_img = page_images[page_num - 1]

        # Source A
        info_a = pages_info_a.get(page_num, {"width": 8.5, "height": 11})
        p_a = paras_a.get(page_num, [])
        label_a = f"SOURCE A ({fmt_a}) | {doc_name} p.{page_num} | {len(p_a)} paragraphs"
        ann_a = render_page(page_img, p_a, info_a["width"], info_a["height"], label=label_a)

        # Source B
        info_b = pages_info_b.get(page_num, {"width": 8.5, "height": 11})
        p_b = paras_b.get(page_num, [])
        label_b = f"SOURCE B ({fmt_b}) | {doc_name} p.{page_num} | {len(p_b)} paragraphs"
        ann_b = render_page(page_img, p_b, info_b["width"], info_b["height"], label=label_b)

        annotated_pages.append(ann_a)
        annotated_pages.append(ann_b)
        print(f"    Page {page_num}: A={len(p_a)} paras, B={len(p_b)} paras")

    if annotated_pages:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        annotated_pages[0].save(
            str(output_path), "PDF", save_all=True,
            append_images=annotated_pages[1:], resolution=DPI
        )
        print(f"  ✓ Saved: {output_path} ({len(annotated_pages)} pages)")


# ─── Batch Mode ──────────────────────────────────────────────────────────────

def process_batch(input_dir, layout_dir, output_dir, pages_filter=None):
    """Process all PDFs in input_dir with matching layout JSONs."""
    input_dir = Path(input_dir)
    layout_dir = Path(layout_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(input_dir.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs found in {input_dir}")
        return

    print(f"Found {len(pdfs)} PDFs. Looking for layout JSONs in {layout_dir}...\n")

    processed = 0
    for pdf_path in pdfs:
        stem = pdf_path.stem
        # Try common naming patterns
        json_candidates = [
            layout_dir / f"{stem}.layout.json",
            layout_dir / f"{stem}.json",
        ]
        json_path = None
        for candidate in json_candidates:
            if candidate.exists():
                json_path = candidate
                break

        if not json_path:
            print(f"⚠️  No layout JSON found for {pdf_path.name}, skipping")
            continue

        print(f"[{stem}] Visualizing reading order...")
        output_path = output_dir / f"{stem}_reading_order.pdf"
        create_visualization_pdf(
            pdf_path, json_path, output_path,
            pages_filter=pages_filter, label_prefix=f"{stem} | "
        )
        processed += 1
        print()

    print(f"═══════════════════════════════════════")
    print(f"Done: {processed}/{len(pdfs)} documents visualized")
    print(f"Output: {output_dir}")


# ─── Main ────────────────────────────────────────────────────────────────────

def parse_pages(pages_str):
    """Parse page filter string like '1-3,5,7-9'."""
    pages = []
    for part in pages_str.split(","):
        part = part.strip()
        if "-" in part:
            s, e = part.split("-")
            pages.extend(range(int(s), int(e) + 1))
        else:
            pages.append(int(part))
    return pages


def main():
    parser = argparse.ArgumentParser(
        description="Visualize CU/DI layout reading order with numbered bboxes and arrows",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single document
  python visualize_reading_order.py --pdf doc.pdf --layout doc.layout.json -o output/

  # Batch mode (all PDFs in a folder)
  python visualize_reading_order.py --input-dir samples/ --layout-dir layout_results/ -o output/

  # Compare two layout sources
  python visualize_reading_order.py --pdf doc.pdf --layout-a prod.json --layout-b selfhost.json -o output/

  # Specific pages only
  python visualize_reading_order.py --pdf doc.pdf --layout doc.json -o output/ --pages 1-3,18
        """
    )

    # Single document mode
    parser.add_argument("--pdf", type=Path, help="Source PDF file")
    parser.add_argument("--layout", type=Path, help="Layout JSON file (auto-detects CU or DI format)")

    # Batch mode
    parser.add_argument("--input-dir", type=Path, help="Directory of source PDFs")
    parser.add_argument("--layout-dir", type=Path, help="Directory of layout JSON files")

    # Comparison mode
    parser.add_argument("--layout-a", type=Path, help="First layout JSON (for comparison)")
    parser.add_argument("--layout-b", type=Path, help="Second layout JSON (for comparison)")

    # Options
    parser.add_argument("-o", "--output", type=Path, required=True, help="Output directory")
    parser.add_argument("--pages", type=str, help="Page filter (e.g., '1-3,5,18')")
    parser.add_argument("--dpi", type=int, default=DPI, help=f"Rendering DPI (default: {DPI})")

    args = parser.parse_args()

    dpi = args.dpi

    pages_filter = parse_pages(args.pages) if args.pages else None

    # Batch mode
    if args.input_dir and args.layout_dir:
        process_batch(args.input_dir, args.layout_dir, args.output, pages_filter)
        return

    # Single/comparison mode
    if not args.pdf:
        parser.error("Either --pdf or (--input-dir + --layout-dir) is required")

    if not args.pdf.exists():
        sys.exit(f"ERROR: PDF not found: {args.pdf}")

    args.output.mkdir(parents=True, exist_ok=True)
    stem = args.pdf.stem

    # Comparison mode
    if args.layout_a and args.layout_b:
        print(f"Comparison visualization for {stem}...")
        create_comparison_pdf(
            args.pdf, args.layout_a, args.layout_b,
            args.output / f"{stem}_comparison.pdf",
            pages_filter=pages_filter, doc_name=stem
        )
    elif args.layout_a:
        print(f"Visualization for {stem} (source A)...")
        create_visualization_pdf(
            args.pdf, args.layout_a,
            args.output / f"{stem}_reading_order.pdf",
            pages_filter=pages_filter, label_prefix=f"{stem} | "
        )
    elif args.layout:
        print(f"Visualization for {stem}...")
        create_visualization_pdf(
            args.pdf, args.layout,
            args.output / f"{stem}_reading_order.pdf",
            pages_filter=pages_filter, label_prefix=f"{stem} | "
        )
    else:
        parser.error("Specify --layout, --layout-a, or (--layout-a + --layout-b)")


if __name__ == "__main__":
    main()
