#!/usr/bin/env python3
"""Convert PDF pages to PNG images using PyMuPDF."""

import sys
from pathlib import Path
import fitz  # PyMuPDF
import argparse


def pdf_to_images(pdf_path: str, output_dir: str = None, zoom: float = 1.5):
    """Convert PDF to page images.
    
    Args:
        pdf_path: Path to PDF file
        output_dir: Directory to save images. If None, uses PDF directory
        zoom: Zoom level for image quality (default 1.5, approximately 150 DPI)
    """
    pdf_path = Path(pdf_path).resolve()
    
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    
    if output_dir is None:
        output_dir = pdf_path.parent
    else:
        output_dir = Path(output_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Converting: {pdf_path}")
    print(f"Output dir: {output_dir}")
    print(f"Zoom: {zoom}")
    
    # Open PDF
    pdf = fitz.open(str(pdf_path))
    num_pages = len(pdf)
    
    # Convert each page to image
    stem = pdf_path.stem
    for page_num in range(num_pages):
        page = pdf[page_num]
        
        # Render page to image
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        
        output_file = output_dir / f"{stem}_page_{page_num + 1:03d}.png"
        pix.save(str(output_file))
        print(f"  Saved: {output_file.name}")
    
    pdf.close()
    print(f"\nConverted {num_pages} pages from {pdf_path.name}")
    return num_pages


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert PDF pages to PNG images")
    parser.add_argument("pdf_path", help="Path to PDF file")
    parser.add_argument("--output-dir", help="Output directory for images (default: PDF directory)")
    parser.add_argument("--zoom", type=float, default=1.5, help="Zoom level for quality (default: 1.5, ~150 DPI)")
    
    args = parser.parse_args()
    
    try:
        pdf_to_images(args.pdf_path, args.output_dir, args.zoom)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
