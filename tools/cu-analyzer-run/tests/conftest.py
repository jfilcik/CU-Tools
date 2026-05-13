"""
Pytest configuration and shared fixtures for cu-analyzer-run tests.

These tests focus on core tool functionality using files from the data/ folder.
"""

import os
import sys
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch
from typing import Dict, Any, List

import pytest

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "cu-client"))

# Import modules under test
from run import (
    is_pdf_protected,
    check_files_for_protection,
    get_supported_files,
    get_client,
    run_analysis,
    save_result,
    create_run_metadata,
    process_single_document,
    PYPDF2_AVAILABLE
)


# =============================================================================
# Test Data Paths (using data/ folder only)
# =============================================================================

REPO_ROOT = Path(__file__).parent.parent.parent.parent

# Files from data folder for testing
DATA_FOLDER = REPO_ROOT / "data"
PROTECTED_PDF_PATH = DATA_FOLDER / "protected sample PDF.pdf"

DATA_FOLDER_SAMPLES = {
    "invoice": DATA_FOLDER / "invoice.pdf",
    "mixed_financial": DATA_FOLDER / "mixed_financial_docs.pdf",
    "protected": DATA_FOLDER / "protected sample PDF.pdf",
    "receipt_image": DATA_FOLDER / "receipt.png",
    "chart_image": DATA_FOLDER / "pieChart.jpg",
}


def get_available_data_files() -> List[Path]:
    """Get all available test files from data folder (excluding protected)."""
    available = []
    for key, path in DATA_FOLDER_SAMPLES.items():
        if key != "protected" and path.exists():
            available.append(path)
    return available


# =============================================================================
# Core Fixtures
# =============================================================================

@pytest.fixture
def temp_output_dir():
    """Create a temporary directory for test outputs."""
    temp_dir = tempfile.mkdtemp(prefix="cu_test_")
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_client():
    """Create a mock CU client for testing."""
    client = MagicMock()
    
    # Mock successful analysis result
    client.begin_analyze_binary.return_value = {"operationId": "test-op-123"}
    client.poll_result.return_value = {
        "status": "succeeded",
        "result": {
            "contents": [
                {
                    "kind": "document",
                    "fields": {
                        "InvoiceNumber": {"value": "INV-001", "confidence": 0.95},
                        "TotalAmount": {"value": "1234.56", "confidence": 0.92}
                    },
                    "startPageNumber": 1,
                    "endPageNumber": 1
                }
            ]
        }
    }
    
    # Mock analyzer operations
    client.get_analyzer_detail_by_id.return_value = {"status": "succeeded"}
    client.delete_analyzer.return_value = None
    client.begin_create_analyzer.return_value = {"status": "creating"}
    
    return client


@pytest.fixture
def mock_layout_result():
    """Create a mock layout analysis result."""
    return {
        "status": "succeeded",
        "result": {
            "contents": [
                {
                    "kind": "text",
                    "markdown": "# Test Document\n\nThis is test content.",
                    "startPageNumber": 1,
                    "endPageNumber": 2
                }
            ]
        }
    }


@pytest.fixture
def sample_schema() -> Dict[str, Any]:
    """Create a sample analyzer schema for testing."""
    return {
        "description": "Test invoice analyzer",
        "baseAnalyzerId": "prebuilt-document",
        "models": {"completion": "gpt-4.1"},
        "config": {
            "returnDetails": True,
            "estimateFieldSourceAndConfidence": True
        },
        "fieldSchema": {
            "fields": {
                "InvoiceNumber": {
                    "type": "string",
                    "method": "extract",
                    "description": "The invoice number from the document"
                },
                "TotalAmount": {
                    "type": "number",
                    "method": "extract",
                    "description": "The total amount due"
                }
            }
        }
    }


@pytest.fixture
def sample_schema_file(temp_output_dir, sample_schema):
    """Create a sample schema file for testing."""
    schema_path = temp_output_dir / "test_schema.json"
    with open(schema_path, "w") as f:
        json.dump(sample_schema, f, indent=2)
    return schema_path


# =============================================================================
# Data Folder File Fixtures
# =============================================================================

@pytest.fixture
def protected_pdf():
    """Get the actual protected PDF from data folder."""
    if not PROTECTED_PDF_PATH.exists():
        pytest.skip("Protected PDF sample not available in data folder")
    return PROTECTED_PDF_PATH


@pytest.fixture
def data_folder_invoice():
    """Get the invoice PDF from data folder."""
    invoice_path = DATA_FOLDER_SAMPLES["invoice"]
    if not invoice_path.exists():
        pytest.skip("Invoice PDF not available in data folder")
    return invoice_path


@pytest.fixture
def data_folder_mixed_docs():
    """Get the mixed financial docs PDF from data folder."""
    mixed_path = DATA_FOLDER_SAMPLES["mixed_financial"]
    if not mixed_path.exists():
        pytest.skip("Mixed financial docs PDF not available in data folder")
    return mixed_path


@pytest.fixture
def data_folder_images():
    """Get image files from data folder."""
    images = []
    for key in ["receipt_image", "chart_image"]:
        path = DATA_FOLDER_SAMPLES.get(key)
        if path and path.exists():
            images.append(path)
    if not images:
        pytest.skip("No image files available in data folder")
    return images


@pytest.fixture
def all_data_folder_files():
    """Get all processable files from data folder (excluding protected PDF)."""
    files = get_available_data_files()
    if not files:
        pytest.skip("No files available in data folder")
    return files


@pytest.fixture
def any_sample_pdf():
    """Get any available sample PDF for testing."""
    for key in ["invoice", "mixed_financial"]:
        path = DATA_FOLDER_SAMPLES.get(key)
        if path and path.exists():
            return path
    pytest.skip("No sample PDFs available in data folder")


@pytest.fixture
def multiple_sample_pdfs():
    """Get multiple sample files for batch testing."""
    available = get_available_data_files()
    if len(available) < 2:
        pytest.skip("Need at least 2 sample files for batch testing")
    return available


# =============================================================================
# Environment Fixtures
# =============================================================================

@pytest.fixture
def mock_env_vars():
    """Set up mock environment variables for testing."""
    with patch.dict(os.environ, {
        "AZURE_AI_ENDPOINT": "https://test.cognitiveservices.azure.com",
        "AZURE_AI_API_KEY": "test-api-key-12345",
        "CU_API_VERSION": "2025-11-01"
    }):
        yield

# =============================================================================
# Credential Detection for CI
# =============================================================================

def has_azure_credentials():
    """Check if Azure credentials are available (not empty)."""
    endpoint = os.environ.get('AZURE_AI_ENDPOINT', '')
    api_key = os.environ.get('AZURE_AI_API_KEY', '')
    return bool(endpoint and api_key)


@pytest.fixture
def requires_credentials():
    """Skip test if Azure credentials are not available."""
    if not has_azure_credentials():
        pytest.skip("Azure credentials not available")


def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers", "requires_credentials: mark test as requiring Azure credentials"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )


def pytest_collection_modifyitems(config, items):
    """Automatically skip tests that require credentials when not available."""
    if has_azure_credentials():
        return
    
    skip_credentials = pytest.mark.skip(reason="Azure credentials not available")
    
    for item in items:
        # Skip tests marked with requires_credentials
        if "requires_credentials" in item.keywords:
            item.add_marker(skip_credentials)
        
        # Skip tests in integration test files
        if "test_integration" in str(item.fspath):
            item.add_marker(skip_credentials)