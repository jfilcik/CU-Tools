# =============================================================================
# Tool: cu-analyzer-run/run.py
# Status: ✅ IMPLEMENTED - Production operations and layout extraction
# Last Updated: 2026-01-28
# =============================================================================
"""
CU Analyzer Run Tool - Production Operations

⚡ Use this tool when:
  - You have an EXISTING analyzer ID
  - You need layout extraction (common first step)
  - You're running production batch processing
  - You need fine-grained control
  - You want to test prebuilt analyzers (layout, search, etc.)

🔧 For schema development/testing, use create_and_test.py instead:
  - Validates schema before creating analyzer
  - Creates analyzer from schema file
  - Optionally cleans up after testing

Capabilities:
- Run analysis with existing analyzer
- Extract layout for schema development
- Test prebuilt analyzers (layout, search)
- Batch analysis (folder of documents)
- Stability testing (multiple iterations)
- Validation of Azure setup

Usage:
    # VALIDATION: Check Azure setup and connectivity
    python run.py --validate
    
    # LAYOUT: Extract layout (first step before schema development)
    python run.py --layout --input samples/ --output layout/
    
    # READ: Extract text in reading order (left-to-right, top-to-bottom)
    python run.py --read --input samples/ --output read_results/
    
    # PREBUILT SEARCH: Test document search capabilities
    python run.py --analyzer-id prebuilt-documentSearch --input doc.pdf --output results/
    
    # Use existing analyzer on single document
    python run.py --analyzer-id invoice-v1 --input doc.pdf --output results/
    
    # Batch processing with parallel execution (3 workers)
    python run.py --analyzer-id invoice-v1 --input docs/ --output results/ --max-workers 3
    
    # Stability test (10 iterations per document)
    python run.py --analyzer-id invoice-v1 --input doc.pdf --output results/ --iterations 10

See Also:
    create_and_test.py - For schema development workflow
    ../cu-results-export/export.py - Export results to CSV
"""

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import uuid

# Add parent directories to path for imports (cu-client should take precedence)
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "python"))
sys.path.insert(0, str(Path(__file__).parent.parent / "cu-client"))

from content_understanding_client import AzureContentUnderstandingClient
from dotenv import load_dotenv

# Try to import PyPDF2 for PDF protection detection
try:
    from PyPDF2 import PdfReader
    import logging
    # Suppress PyPDF2 warnings about unknown font widths
    logging.getLogger("PyPDF2").setLevel(logging.ERROR)
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False


def is_pdf_protected(file_path: Path) -> Tuple[bool, str]:
    """
    Check if a PDF file is password-protected, encrypted, or uses content protection.
    
    This function detects:
    1. Standard PDF encryption (requires password to open)
    2. Owner-password protection (restricts printing/editing)
    3. Microsoft-style content protection (PDF renders but contains only a protection message)
    
    Returns:
        Tuple of (is_protected: bool, reason: str)
        - is_protected: True if the PDF cannot be read or has content protection
        - reason: Description of the protection type or empty string
    """
    if file_path.suffix.lower() != '.pdf':
        return False, ""
    
    if not PYPDF2_AVAILABLE:
        # Can't check, assume it's fine
        return False, ""
    
    try:
        with open(file_path, 'rb') as f:
            reader = PdfReader(f)
            
            # Check if encrypted
            if reader.is_encrypted:
                # Try to decrypt with empty password (some PDFs have owner password only)
                try:
                    if reader.decrypt('') == 0:
                        return True, "Password-protected (requires password)"
                    # Decrypted with empty password - readable but was encrypted
                except Exception:
                    return True, "Password-protected (requires password)"
            
            # Check for Microsoft-style content protection
            # These PDFs open but contain only a protection warning message
            if len(reader.pages) > 0:
                try:
                    first_page_text = reader.pages[0].extract_text() or ""
                    # Check for common protection warning patterns
                    protection_markers = [
                        "this pdf file is protected",
                        "you'll need a different reader",
                        "this pdf document has been protected",
                        "download a compatible pdf reader",
                        "microsoft information protection",
                    ]
                    text_lower = first_page_text.lower()
                    for marker in protection_markers:
                        if marker in text_lower:
                            return True, "Content-protected (Microsoft Office protection)"
                except Exception as e:
                    error_str = str(e).lower()
                    if "encrypted" in error_str or "decrypt" in error_str:
                        return True, f"Encrypted: {str(e)[:50]}"
            
            return False, ""
            
    except Exception as e:
        error_str = str(e).lower()
        if "encrypt" in error_str or "password" in error_str or "protected" in error_str:
            return True, f"Protected: {str(e)[:50]}"
        # Other errors (corrupted file, etc.) - let CU handle it
        return False, ""


def check_files_for_protection(files: List[Path], verbose: bool = False) -> Tuple[List[Path], List[Tuple[Path, str]]]:
    """
    Check a list of files for PDF protection.
    
    Args:
        files: List of file paths to check
        verbose: If True, print progress for each file (default: False)
    
    Returns:
        Tuple of (valid_files, protected_files)
        - valid_files: List of files that can be processed
        - protected_files: List of (file_path, reason) tuples for protected files
    """
    valid_files = []
    protected_files = []
    
    for file_path in files:
        is_protected, reason = is_pdf_protected(file_path)
        if is_protected:
            protected_files.append((file_path, reason))
            if verbose:
                print(f"  ⚠️ SKIPPING (protected): {file_path.name}")
                print(f"     Reason: {reason}")
        else:
            valid_files.append(file_path)
    
    return valid_files, protected_files


DEFAULT_API_VERSION = "2025-11-01"
AGENTIC_PREVIEW_API_VERSION = "2026-06-01-preview"


def resolve_api_version(api_version: Optional[str] = None) -> str:
    """Resolve an explicit API version without changing the GA default."""
    resolved = api_version or os.getenv("CU_API_VERSION") or DEFAULT_API_VERSION
    if not isinstance(resolved, str) or not resolved.strip():
        raise ValueError("CU API version must be a non-empty string")
    return resolved.strip()


def get_client(api_version: str = None) -> AzureContentUnderstandingClient:
    """Create CU client from environment variables."""
    load_dotenv()
    
    endpoint = os.getenv("AZURE_AI_ENDPOINT")
    api_key = os.getenv("AZURE_AI_API_KEY")
    api_version = resolve_api_version(api_version)
    
    if not endpoint:
        raise ValueError("AZURE_AI_ENDPOINT environment variable not set")
    if not api_key:
        raise ValueError("AZURE_AI_API_KEY environment variable not set")
    
    return AzureContentUnderstandingClient(
        endpoint=endpoint,
        api_version=api_version,
        subscription_key=api_key,
        x_ms_useragent="cu-issue-testing"
    )


def get_supported_files(input_path: Path, pattern: str = "*.*") -> List[Path]:
    """Get list of supported document files from input path."""
    supported_extensions = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".heif", ".docx", ".xlsx", ".pptx", ".txt", ".html", ".md", ".eml", ".msg", ".xml", ".mp4", ".mov", ".avi", ".mkv", ".webm", ".wav", ".mp3"}
    
    if input_path.is_file():
        if input_path.suffix.lower() in supported_extensions:
            return [input_path]
        else:
            print(f"Warning: {input_path} is not a supported document type")
            return []
    
    if input_path.is_dir():
        # Use a set to avoid duplicates on case-insensitive filesystems (Windows)
        files_set = set()
        for ext in supported_extensions:
            files_set.update(input_path.glob(f"*{ext}"))
            files_set.update(input_path.glob(f"*{ext.upper()}"))
        return sorted(files_set)
    
    return []


def check_files_for_size_limits(files: List[Path]) -> Tuple[List[Path], List[Tuple[Path, str]]]:
    """
    Check a list of files against CU service size limits.
    
    CU enforces different size limits per file type:
    - Text/email (.eml, .msg, .txt, .html, .md, .xml): 1 MB
    - Document (.pdf, .docx, .xlsx, .pptx): 20 MB
    - Image (.tiff, .jpg, .png, .bmp, .heif): 20 MB
    
    Both :analyzeBinary and :analyze (URL-based) endpoints enforce
    the same limits — there is no endpoint workaround.
    
    Args:
        files: List of file paths to check
    
    Returns:
        Tuple of (valid_files, oversized_files)
        - valid_files: List of files within size limits
        - oversized_files: List of (file_path, reason) tuples for files that exceed limits
    """
    valid_files = []
    oversized_files = []
    
    for file_path in files:
        warning = AzureContentUnderstandingClient.check_file_size(file_path)
        if warning:
            oversized_files.append((file_path, warning))
        else:
            valid_files.append(file_path)
    
    return valid_files, oversized_files


def run_analysis(
    client: AzureContentUnderstandingClient,
    analyzer_id: str,
    file_path: Path,
    timeout: int = 180
) -> Dict[str, Any]:
    """Run analysis on a single file and return result."""
    response = client.begin_analyze_binary(analyzer_id, str(file_path))
    result = client.poll_result(response, timeout_seconds=timeout)
    return result


def run_layout_analysis(
    client: AzureContentUnderstandingClient,
    file_path: Path,
    timeout: int = 180
) -> tuple:
    """Run prebuilt-layout analysis to extract document structure.
    
    Returns:
        tuple: (response, result) - response is needed for extracting page images
    """
    # Use prebuilt-layout analyzer for document structure extraction
    response = client.begin_analyze_binary("prebuilt-layout", str(file_path))
    result = client.poll_result(response, timeout_seconds=timeout)
    return response, result


def run_read_analysis(
    client: AzureContentUnderstandingClient,
    file_path: Path,
    timeout: int = 180
) -> tuple:
    """Run prebuilt-read analysis for simple text extraction in reading order.
    
    Unlike prebuilt-layout, prebuilt-read extracts text in natural reading order
    (left-to-right, top-to-bottom) without respecting document layout/columns.
    This is useful when you need interleaved text that follows reading sequence.
    
    Returns:
        tuple: (response, result) - response is needed for extracting page images
    """
    # Use prebuilt-read analyzer for simple text extraction
    response = client.begin_analyze_binary("prebuilt-read", str(file_path))
    result = client.poll_result(response, timeout_seconds=timeout)
    return response, result


def extract_page_images(
    client: AzureContentUnderstandingClient,
    analyze_response,
    result: Dict[str, Any],
    output_dir: Path,
    doc_name: str
) -> List[str]:
    """Extract page images from layout analysis result.
    
    Uses the /files/pages/{pageNumber} endpoint to retrieve rendered page images.
    For a PDF, /files/pages/1 returns page 1 image, /files/pages/2 returns page 2, etc.
    
    Docs: https://learn.microsoft.com/en-us/rest/api/contentunderstanding/content-analyzers/get-result-file
    """
    saved_images = []
    
    # Get page count from the result
    contents = result.get("result", {}).get("contents", [])
    if not contents:
        return saved_images
    
    # Find the document content to get page range
    for content in contents:
        start_page = content.get("startPageNumber", 1)
        end_page = content.get("endPageNumber", 1)
        
        # Extract each page image
        for page_num in range(start_page, end_page + 1):
            try:
                # Use /files/pages/{pageNumber} endpoint to get page image
                image_bytes = client.get_result_file(analyze_response, f"pages/{page_num}")
                if image_bytes:
                    image_path = output_dir / f"{doc_name}_page_{page_num:03d}.png"
                    with open(image_path, "wb") as f:
                        f.write(image_bytes)
                    saved_images.append(str(image_path))
                    print(f"    Extracted page {page_num} image")
            except Exception as e:
                # Page image extraction is optional, don't fail the whole operation
                print(f"    Warning: Could not extract page {page_num} image: {e}")
        
        # Only process first document content block
        break
    
    return saved_images


def save_result(
    result: Dict[str, Any],
    output_path: Path,
    document: str,
    iteration: int,
    run_id: str,
    analyzer_id: str
) -> Path:
    """Save analysis result with metadata."""
    # Add metadata to result
    enriched_result = {
        "_metadata": {
            "run_id": run_id,
            "document": document,
            "iteration": iteration,
            "analyzer_id": analyzer_id,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        },
        **result
    }
    
    # Determine filename
    if iteration > 1:
        filename = f"{Path(document).stem}_iter{iteration:03d}.json"
    else:
        filename = f"{Path(document).stem}.json"
    
    result_path = output_path / filename
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(enriched_result, f, indent=2, ensure_ascii=False)
    
    return result_path


def save_layout_result(
    client: AzureContentUnderstandingClient,
    response,
    result: Dict[str, Any],
    output_path: Path,
    document: str
) -> Path:
    """Save layout analysis result including JSON, markdown, and page images."""
    doc_stem = Path(document).stem
    
    # Save full JSON result
    json_path = output_path / f"{doc_stem}.layout.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    # Extract and save markdown content
    markdown_content = extract_markdown_from_layout(result)
    if markdown_content:
        md_path = output_path / f"{doc_stem}.layout.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)
    
    # Extract page images
    print(f"  Extracting page images...")
    page_images = extract_page_images(client, response, result, output_path, doc_stem)
    if page_images:
        print(f"  ✓ Extracted {len(page_images)} page image(s)")
    
    return json_path


def extract_markdown_from_layout(result: Dict[str, Any]) -> str:
    """Extract markdown representation from layout result."""
    contents = result.get("result", {}).get("contents", [])
    
    markdown_parts = []
    for content in contents:
        # The markdown is directly on the content object for layout results
        markdown = content.get("markdown")
        if markdown:
            markdown_parts.append(markdown)
        # Also check for text kind with markdown/text field (older format)
        elif content.get("kind") == "text":
            text = content.get("markdown") or content.get("text", "")
            if text:
                markdown_parts.append(text)
    
    return "\n\n".join(markdown_parts)


def create_run_metadata(
    run_id: str,
    analyzer_id: str,
    input_path: str,
    documents: List[str],
    iterations: int,
    test_type: str,
    api_version: Optional[str] = None,
) -> Dict[str, Any]:
    """Create metadata file for the run."""
    return {
        "run_id": run_id,
        "analyzer_id": analyzer_id,
        "input_path": input_path,
        "documents": documents,
        "iterations": iterations,
        "test_type": test_type,  # "single", "batch", "stability", "layout"
        "started_at": datetime.utcnow().isoformat() + "Z",
        "document_count": len(documents),
        "total_runs": len(documents) * iterations,
        "api_version": resolve_api_version(api_version),
    }


def process_single_document(
    client: AzureContentUnderstandingClient,
    file_path: Path,
    file_idx: int,
    total_files: int,
    iteration: int,
    total_iterations: int,
    analyzer_id: str,
    run_id: str,
    results_dir: Path,
    timeout: int,
    is_layout: bool,
    is_read: bool = False
) -> Tuple[bool, Dict[str, Any]]:
    """
    Process a single document (used for parallel processing).
    Returns (success, result_dict)
    """
    iter_label = f" (iteration {iteration}/{total_iterations})" if total_iterations > 1 else ""
    
    try:
        start_time = time.time()
        
        if is_layout:
            response, result = run_layout_analysis(client, file_path, timeout)
            result_path = save_layout_result(client, response, result, results_dir, file_path.name)
        elif is_read:
            response, result = run_read_analysis(client, file_path, timeout)
            # Save read results using the same layout format (JSON + markdown)
            result_path = save_layout_result(client, response, result, results_dir, file_path.name)
        else:
            result = run_analysis(client, analyzer_id, file_path, timeout)
            result_path = save_result(
                result, results_dir, file_path.name, 
                iteration, run_id, analyzer_id
            )
        
        elapsed = time.time() - start_time
        
        return True, {
            "document": file_path.name,
            "iteration": iteration,
            "status": "success",
            "elapsed_seconds": elapsed,
            "result_file": result_path.name,
            "file_idx": file_idx
        }
        
    except Exception as e:
        return False, {
            "document": file_path.name,
            "iteration": iteration,
            "status": "failed",
            "error": str(e),
            "file_idx": file_idx
        }


def main():
    parser = argparse.ArgumentParser(
        description="Run Content Understanding analysis on documents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate Azure setup and connectivity
  python run.py --validate
  
  # Test layout extraction
  python run.py --layout --input documents/ --output layout_results/
  
  # Test document search (prebuilt analyzer)
  python run.py --analyzer-id prebuilt-documentSearch --input doc.pdf --output search_results/
  
  # Single document analysis with custom analyzer
  python run.py --analyzer-id invoice-v1 --input invoice.pdf --output results/
  
  # Batch analysis (folder of documents)
  python run.py --analyzer-id invoice-v1 --input invoices/ --output results/
  
  # Stability test (10 iterations per document)
  python run.py --analyzer-id invoice-v1 --input invoice.pdf --output results/ --iterations 10
        """
    )
    
    # Input/Output (not required for --validate)
    parser.add_argument("--input", "-i", help="Input file or directory")
    parser.add_argument("--output", "-o", help="Output directory for results")
    
    # Analyzer options
    parser.add_argument("--analyzer-id", "-a", help="Analyzer ID to use (required unless --layout, --read, or --delete-analyzer)")
    parser.add_argument("--layout", action="store_true", help="Run prebuilt-layout analysis for document structure")
    parser.add_argument("--read", action="store_true", help="Run prebuilt-read analysis for simple text extraction (reading order, no layout)")
    parser.add_argument("--delete-analyzer", help="Delete analyzer with the specified ID and exit")
    
    # Test configuration
    parser.add_argument("--iterations", "-n", type=int, default=1, 
                        help="Number of iterations per document (for stability testing)")
    parser.add_argument("--timeout", "-t", type=int, default=180,
                        help="Timeout in seconds for each analysis (default: 180)")
    
    # Run identification
    parser.add_argument("--run-id", help="Custom run ID (auto-generated if not specified)")
    parser.add_argument(
        "--api-version",
        help=(
            f"CU API version (default: CU_API_VERSION or {DEFAULT_API_VERSION}). "
            f"Use {AGENTIC_PREVIEW_API_VERSION} for agentic preview analyzers."
        ),
    )
    parser.add_argument("--max-workers", type=int, default=1,
                        help="Number of parallel workers for processing documents (default: 1, recommended: 3-5)")
    
    # Validation
    parser.add_argument("--validate", action="store_true", 
                        help="Run setup validation checks (connectivity, authentication, etc.)")
    parser.add_argument("--skip-validation", action="store_true",
                        help="Skip automatic validation checks before operations")
    
    args = parser.parse_args()
    
    # Handle validate-only command
    if args.validate:
        print("Running Content Understanding setup validation...")
        try:
            client = get_client(api_version=args.api_version)
            client.validate_setup(verbose=True)
            sys.exit(0)
        except Exception as e:
            print(f"\n❌ Validation failed: {e}")
            sys.exit(1)
    
    # Handle delete-analyzer command
    if args.delete_analyzer:
        print(f"Deleting analyzer: {args.delete_analyzer}")
        try:
            client = get_client(api_version=args.api_version)
            client.delete_analyzer(args.delete_analyzer)
            print(f"✓ Analyzer deleted successfully")
            sys.exit(0)
        except Exception as e:
            print(f"✗ Error deleting analyzer: {e}")
            sys.exit(1)
    
    # For normal operations, input and output are required
    if not args.input or not args.output:
        parser.error("--input and --output are required for analysis operations")
    
    # Validate arguments for normal run
    if not args.layout and not args.read and not args.analyzer_id:
        parser.error("--analyzer-id is required unless --layout, --read, or --delete-analyzer is specified")
    
    input_path = Path(args.input)
    output_path = Path(args.output)
    
    if not input_path.exists():
        print(f"Error: Input path does not exist: {input_path}")
        sys.exit(1)
    
    # Create output directory
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Get list of files to process
    files = get_supported_files(input_path)
    if not files:
        print(f"Error: No supported documents found in {input_path}")
        sys.exit(1)
    
    # Check for protected PDFs and filter them out
    processable_files, protected_files = check_files_for_protection(files)
    
    if protected_files:
        print(f"\n⚠️  Found {len(protected_files)} protected/encrypted PDF(s) - these will be skipped:")
        for pf, reason in protected_files:
            print(f"   - {pf.name}: {reason}")
        print()
    
    # Check for files exceeding CU service size limits
    processable_files, oversized_files = check_files_for_size_limits(processable_files)
    
    if oversized_files:
        print(f"\n⚠️  Found {len(oversized_files)} file(s) exceeding CU size limits - these will be skipped:")
        for of, reason in oversized_files:
            print(f"   - {of.name}: {reason}")
        print()
    
    skipped_count = len(protected_files) + len(oversized_files)
    
    if not processable_files:
        print(f"Error: All {len(files)} document(s) are protected, oversized, or unreadable. Cannot proceed.")
        sys.exit(1)
    
    files = processable_files  # Use only processable files from here on
    print(f"Found {len(files)} processable document(s) ({skipped_count} skipped)")
    
    # Initialize client
    try:
        client = get_client(api_version=args.api_version)
        
        # Run validation unless explicitly skipped
        if not args.skip_validation:
            print("🔍 Validating setup...")
            try:
                client.validate_setup(verbose=False)
                print("✅ Validation passed\n")
            except Exception as e:
                print(f"❌ Validation failed: {e}")
                print("\nTip: Fix the issues above or use --skip-validation to bypass checks")
                sys.exit(1)
    except Exception as e:
        print(f"Error initializing CU client: {e}")
        sys.exit(1)
    
    # Generate run ID
    run_id = args.run_id or f"run_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    
    # Determine test type
    if args.layout:
        test_type = "layout"
        analyzer_id = "prebuilt-layout"
    elif args.read:
        test_type = "read"
        analyzer_id = "prebuilt-read"
    elif args.iterations > 1:
        test_type = "stability"
        analyzer_id = args.analyzer_id
    elif len(files) > 1:
        test_type = "batch"
        analyzer_id = args.analyzer_id
    else:
        test_type = "single"
        analyzer_id = args.analyzer_id
    
    # Create and save run metadata
    metadata = create_run_metadata(
        run_id=run_id,
        analyzer_id=analyzer_id,
        input_path=str(input_path),
        documents=[f.name for f in files],
        iterations=args.iterations,
        test_type=test_type,
        api_version=args.api_version,
    )
    
    # Add protected files info to metadata
    if protected_files:
        metadata["skipped_protected_files"] = [
            {"file": pf.name, "reason": reason} for pf, reason in protected_files
        ]
    
    # Add oversized files info to metadata
    if oversized_files:
        metadata["skipped_oversized_files"] = [
            {"file": of.name, "reason": reason} for of, reason in oversized_files
        ]
    
    metadata_path = output_path / "metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    
    print(f"\nRun ID: {run_id}")
    print(f"Test type: {test_type}")
    print(f"Output: {output_path}")
    print("-" * 50)
    
    # Process files
    # For layout and read modes, output directly to output_path; otherwise use results subfolder
    results_dir = output_path / "results" if not (args.layout or args.read) else output_path
    results_dir.mkdir(parents=True, exist_ok=True)
    
    successful = 0
    failed = 0
    results_summary = []
    
    # Create list of all tasks (document + iteration combinations)
    tasks = []
    for file_idx, file_path in enumerate(files, 1):
        for iteration in range(1, args.iterations + 1):
            tasks.append((file_path, file_idx, iteration))
    
    total_tasks = len(tasks)
    print(f"Processing {total_tasks} task(s) with {args.max_workers} worker(s)...")
    
    if args.max_workers == 1:
        # Sequential processing (original behavior)
        for file_idx, file_path in enumerate(files, 1):
            print(f"\n[{file_idx}/{len(files)}] Processing: {file_path.name}")
            
            for iteration in range(1, args.iterations + 1):
                iter_label = f" (iteration {iteration}/{args.iterations})" if args.iterations > 1 else ""
                
                success, result_dict = process_single_document(
                    client, file_path, file_idx, len(files),
                    iteration, args.iterations, analyzer_id, run_id,
                    results_dir, args.timeout, args.layout, args.read
                )
                
                if success:
                    print(f"  ✓ Done ({result_dict['elapsed_seconds']:.1f}s) - Saved: {result_dict['result_file']}")
                    successful += 1
                else:
                    print(f"  ✗ Error: {result_dict['error']}")
                    failed += 1
                
                results_summary.append(result_dict)
    else:
        # Parallel processing
        print()  # Blank line before parallel output
        with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
            # Submit all tasks
            futures = {
                executor.submit(
                    process_single_document,
                    client, file_path, file_idx, len(files),
                    iteration, args.iterations, analyzer_id, run_id,
                    results_dir, args.timeout, args.layout, args.read
                ): (file_path, file_idx, iteration)
                for file_path, file_idx, iteration in tasks
            }
            
            # Process completed tasks
            completed = 0
            for future in as_completed(futures):
                file_path, file_idx, iteration = futures[future]
                completed += 1
                
                try:
                    success, result_dict = future.result()
                    
                    if success:
                        print(f"✅ [{completed}/{total_tasks}] {file_path.name} - {result_dict['elapsed_seconds']:.1f}s - {result_dict['result_file']}")
                        successful += 1
                    else:
                        print(f"❌ [{completed}/{total_tasks}] {file_path.name} - Error: {result_dict['error']}")
                        failed += 1
                    
                    results_summary.append(result_dict)
                    
                except Exception as e:
                    print(f"❌ [{completed}/{total_tasks}] {file_path.name} - Exception: {e}")
                    failed += 1
                    results_summary.append({
                        "document": file_path.name,
                        "iteration": iteration,
                        "status": "failed",
                        "error": str(e),
                        "file_idx": file_idx
                    })
    
    # Update metadata with results
    metadata["completed_at"] = datetime.utcnow().isoformat() + "Z"
    metadata["successful"] = successful
    metadata["failed"] = failed
    metadata["results"] = results_summary
    
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    
    # Print summary
    print("\n" + "=" * 50)
    print(f"COMPLETED: {successful} successful, {failed} failed")
    print(f"Results saved to: {output_path}")
    print(f"Metadata: {metadata_path}")
    
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
