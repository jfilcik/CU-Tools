"""
Tests for PDF protection detection functionality.

Tests the is_pdf_protected() and check_files_for_protection() functions
that detect Microsoft Information Protection and other PDF security features.

Note: is_pdf_protected() returns a tuple (is_protected: bool, reason: str)
      check_files_for_protection() takes List[Path] and returns (valid_files, protected_files)
      where protected_files is List[Tuple[Path, str]]
"""

import pytest
from pathlib import Path
from unittest.mock import patch
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from run import is_pdf_protected, check_files_for_protection


# Test data paths
DATA_FOLDER = Path(__file__).parent.parent.parent.parent / "data"
PROTECTED_PDF_PATH = DATA_FOLDER / "protected sample PDF.pdf"
INVOICE_PDF_PATH = DATA_FOLDER / "invoice.pdf"
MIXED_DOCS_PATH = DATA_FOLDER / "mixed_financial_docs.pdf"


class TestIsPdfProtected:
    """Tests for the is_pdf_protected() function.
    
    Note: is_pdf_protected() returns a tuple (is_protected: bool, reason: str)
    """

    def test_real_protected_pdf(self):
        """Test detection of real MS Information Protected PDF from data folder."""
        if not PROTECTED_PDF_PATH.exists():
            pytest.skip(f"Protected PDF not found at {PROTECTED_PDF_PATH}")
        
        is_protected, reason = is_pdf_protected(PROTECTED_PDF_PATH)
        assert is_protected is True, "Should detect real protected PDF as protected"
        assert reason != "", "Should provide a reason for protected PDF"

    def test_unprotected_pdf_invoice(self):
        """Test that regular invoice PDF is not detected as protected."""
        if not INVOICE_PDF_PATH.exists():
            pytest.skip(f"Invoice PDF not found at {INVOICE_PDF_PATH}")
        
        is_protected, reason = is_pdf_protected(INVOICE_PDF_PATH)
        assert is_protected is False, "Regular invoice PDF should not be detected as protected"
        assert reason == "", "Unprotected PDF should have empty reason"

    def test_unprotected_pdf_mixed_docs(self):
        """Test that mixed_financial_docs PDF is not detected as protected."""
        if not MIXED_DOCS_PATH.exists():
            pytest.skip(f"Mixed docs PDF not found at {MIXED_DOCS_PATH}")
        
        is_protected, reason = is_pdf_protected(MIXED_DOCS_PATH)
        assert is_protected is False, "Regular PDF should not be detected as protected"

    def test_non_pdf_file_returns_false(self, tmp_path):
        """Test that non-PDF files return False."""
        text_file = tmp_path / "test.txt"
        text_file.write_text("This is not a PDF")
        
        is_protected, reason = is_pdf_protected(text_file)
        assert is_protected is False, "Non-PDF file should return False"

    def test_nonexistent_file_returns_false(self, tmp_path):
        """Test that non-existent files return False."""
        non_existent = tmp_path / "nonexistent.pdf"
        is_protected, reason = is_pdf_protected(non_existent)
        assert is_protected is False, "Non-existent file should return False"

    def test_corrupted_pdf_returns_false(self, tmp_path):
        """Test that corrupted/invalid PDF files return False."""
        fake_pdf = tmp_path / "corrupted.pdf"
        fake_pdf.write_bytes(b"This is not valid PDF content")
        
        is_protected, reason = is_pdf_protected(fake_pdf)
        assert is_protected is False, "Corrupted PDF should return False (not raise exception)"

    def test_empty_file_returns_false(self, tmp_path):
        """Test that empty files return False."""
        empty_pdf = tmp_path / "empty.pdf"
        empty_pdf.write_bytes(b"")
        
        is_protected, reason = is_pdf_protected(empty_pdf)
        assert is_protected is False, "Empty file should return False"

    def test_image_file_returns_false(self):
        """Test that image files return False."""
        receipt_path = DATA_FOLDER / "receipt.png"
        if not receipt_path.exists():
            pytest.skip("Receipt image not found")
        
        is_protected, reason = is_pdf_protected(receipt_path)
        assert is_protected is False, "Image file should return False"


class TestCheckFilesForProtection:
    """Tests for the check_files_for_protection() function.
    
    Note: Takes List[Path] and returns (valid_files: List[Path], protected_files: List[Tuple[Path, str]])
    """

    def test_separates_protected_from_unprotected(self):
        """Test that function correctly separates protected and unprotected files."""
        if not PROTECTED_PDF_PATH.exists():
            pytest.skip("Protected PDF not found")
        if not INVOICE_PDF_PATH.exists():
            pytest.skip("Invoice PDF not found")
        
        files = [PROTECTED_PDF_PATH, INVOICE_PDF_PATH]
        valid_files, protected_files = check_files_for_protection(files)
        
        assert len(protected_files) == 1, "Should have 1 protected file"
        assert len(valid_files) == 1, "Should have 1 processable file"
        # protected_files is list of (Path, reason) tuples
        protected_paths = [pf[0] for pf in protected_files]
        assert PROTECTED_PDF_PATH in protected_paths
        assert INVOICE_PDF_PATH in valid_files

    def test_all_unprotected_files(self):
        """Test with all unprotected files."""
        available_files = []
        for path in [INVOICE_PDF_PATH, MIXED_DOCS_PATH]:
            if path.exists():
                available_files.append(path)
        
        if len(available_files) < 1:
            pytest.skip("No unprotected PDFs available for testing")
        
        valid_files, protected_files = check_files_for_protection(available_files)
        
        assert len(protected_files) == 0, "Should have no protected files"
        assert len(valid_files) == len(available_files)

    def test_empty_input_list(self):
        """Test with empty file list."""
        valid_files, protected_files = check_files_for_protection([])
        
        assert valid_files == []
        assert protected_files == []

    def test_all_protected_files(self):
        """Test with all protected files."""
        if not PROTECTED_PDF_PATH.exists():
            pytest.skip("Protected PDF not found")
        
        files = [PROTECTED_PDF_PATH]
        valid_files, protected_files = check_files_for_protection(files)
        
        assert len(protected_files) == 1
        assert len(valid_files) == 0

    def test_includes_non_pdf_files_as_processable(self):
        """Test that non-PDF files pass through as processable."""
        receipt_path = DATA_FOLDER / "receipt.png"
        chart_path = DATA_FOLDER / "pieChart.jpg"
        
        available_files = []
        for path in [receipt_path, chart_path]:
            if path.exists():
                available_files.append(path)
        
        if not available_files:
            pytest.skip("No image files available")
        
        valid_files, protected_files = check_files_for_protection(available_files)
        
        assert protected_files == [], "Non-PDF files should not be marked as protected"
        assert len(valid_files) == len(available_files)

    def test_mixed_pdf_and_images(self):
        """Test batch with mixed PDFs and images."""
        files = []
        expected_protected = 0
        
        if PROTECTED_PDF_PATH.exists():
            files.append(PROTECTED_PDF_PATH)
            expected_protected = 1
        
        if INVOICE_PDF_PATH.exists():
            files.append(INVOICE_PDF_PATH)
        
        receipt_path = DATA_FOLDER / "receipt.png"
        if receipt_path.exists():
            files.append(receipt_path)
        
        if len(files) < 2:
            pytest.skip("Need at least 2 test files")
        
        valid_files, protected_files = check_files_for_protection(files)
        
        assert len(protected_files) == expected_protected
        assert len(valid_files) == len(files) - expected_protected


class TestProtectionDetectionEdgeCases:
    """Edge case tests for protection detection."""

    def test_pdf_with_encryption_metadata(self, tmp_path):
        """Test PDF that has encryption-like metadata but isn't protected."""
        pdf_content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>
endobj
xref
0 4
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
trailer
<< /Size 4 /Root 1 0 R >>
startxref
196
%%EOF"""
        
        test_pdf = tmp_path / "fake_encrypt_mention.pdf"
        test_pdf.write_bytes(pdf_content)
        
        is_protected, reason = is_pdf_protected(test_pdf)
        assert is_protected is False


class TestProtectionDetectionPerformance:
    """Performance-related tests for protection detection."""

    def test_quick_detection_does_not_read_entire_file(self, tmp_path):
        """Test that protection detection doesn't need to read entire large file."""
        pdf_header = b"%PDF-1.4\n"
        pdf_content = b"x" * 1024 * 100  # 100KB of content
        pdf_footer = b"\n%%EOF"
        
        large_pdf = tmp_path / "large.pdf"
        large_pdf.write_bytes(pdf_header + pdf_content + pdf_footer)
        
        import time
        start = time.time()
        is_protected, reason = is_pdf_protected(large_pdf)
        elapsed = time.time() - start
        
        assert elapsed < 1.0, f"Detection took too long: {elapsed:.2f}s"
        assert is_protected is False

    def test_batch_check_efficiency(self):
        """Test that batch checking multiple files is efficient."""
        test_files = []
        for path in [INVOICE_PDF_PATH, MIXED_DOCS_PATH, PROTECTED_PDF_PATH]:
            if path.exists():
                test_files.append(path)
        
        if len(test_files) < 2:
            pytest.skip("Need at least 2 test files for batch test")
        
        import time
        start = time.time()
        valid_files, protected_files = check_files_for_protection(test_files)
        elapsed = time.time() - start
        
        assert elapsed < 5.0, f"Batch check took too long: {elapsed:.2f}s"
        assert len(valid_files) + len(protected_files) == len(test_files)
