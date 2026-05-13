# cu-analyzer-run Tests

This directory contains comprehensive tests for the cu-analyzer-run tool.

## Test Files

| File | Purpose |
|------|---------|
| `test_pdf_protection.py` | Tests for PDF protection detection (encrypted, password-protected, MS Information Protected) |
| `test_parallel_processing.py` | Tests for parallel document processing with ThreadPoolExecutor |
| `test_run.py` | Tests for run.py core functionality (file discovery, client, layout extraction) |
| `test_create_and_test.py` | Tests for create_and_test.py workflow (validation, schema loading, analyzer creation) |
| `test_integration_customer_samples.py` | Integration tests using real customer sample files |

## Running Tests

### Run all tests
```bash
cd /workspaces/CU-Issue-Testing/tools/cu-analyzer-run
pytest tests/ -v
```

### Run specific test file
```bash
pytest tests/test_pdf_protection.py -v
```

### Run with coverage
```bash
pytest tests/ --cov=. --cov-report=html
```

### Run only unit tests (skip integration)
```bash
pytest tests/ -v -m "not integration"
```

### Run only tests that don't require PyPDF2
```bash
pytest tests/ -v -k "not pypdf"
```

## Test Categories

### Unit Tests
- PDF protection detection logic
- File discovery and filtering
- Schema validation and loading
- Result saving
- Metadata generation

### Integration Tests
- Processing customer sample files
- Parallel processing with real PDFs
- End-to-end workflow validation

## Fixtures

Key fixtures defined in `conftest.py`:

- `mock_client` - Mocked CU API client for testing without Azure calls
- `temp_output_dir` - Temporary directory for test outputs
- `sample_schema` / `sample_schema_file` - Sample analyzer schema for testing
- `crowne_po_samples` - Crowne PO sample PDFs
- `wk_k1_samples` - WK K-1 sample PDFs
- `any_sample_pdf` - Any available sample PDF
- `multiple_sample_pdfs` - Multiple PDFs for batch testing

## Issue Samples

Tests use PDFs from the `/Issues` directory:

- `Issues/Crowne_PO_Test/samples/` - Purchase order samples
- `Issues/WK_Runs/WK-K1-FirstPage/samples/` - K-1 tax form samples
- `Issues/LeftTurn/samples/` - Contract samples
- `data/` - General test documents

## Environment Setup

Tests can run without Azure credentials as they mock the API client.

For integration tests that actually call Azure (not included by default):
```bash
export AZURE_AI_ENDPOINT=your-endpoint
export AZURE_AI_API_KEY=your-key
```

## Adding New Tests

1. Add test functions to appropriate test file
2. Use fixtures from `conftest.py` for common setup
3. Mark integration tests with `@pytest.mark.integration`
4. Skip tests that require specific dependencies:
   ```python
   @pytest.mark.skipif(not PYPDF2_AVAILABLE, reason="PyPDF2 required")
   ```
