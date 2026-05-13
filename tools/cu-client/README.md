# CU Client

Core Azure Content Understanding client used by all other tools.

## Purpose

This is the base client that wraps Azure Content Understanding REST API calls. All other tools in this repository use this client for CU operations.

## Source

Originally from `python/content_understanding_client.py`, this is the foundational client that provides:
- Analyzer creation and management
- Document analysis (sync and async)
- Result polling
- SAS token generation for blob storage
- Error handling and retries

## Usage

This client is imported and used by other tools:

```python
from tools.cu_client.content_understanding_client import AzureContentUnderstandingClient

# Initialize client
client = AzureContentUnderstandingClient(
    endpoint=AZURE_AI_ENDPOINT,
    api_key=AZURE_AI_API_KEY,
    api_version="2025-11-01"
)

# Create analyzer
client.begin_create_analyzer(analyzer_id, analyzer_template=schema)

# Analyze document
response = client.begin_analyze_binary(analyzer_id, document_path)
result = client.poll_result(response)
```

## Key Methods

### Analyzer Management
- `begin_create_analyzer(analyzer_id, analyzer_template)` - Create new analyzer
- `get_analyzer_detail_by_id(analyzer_id)` - Get analyzer details
- `delete_analyzer(analyzer_id)` - Delete analyzer
- `list_analyzers()` - List all analyzers

### Analysis
- `begin_analyze_binary(analyzer_id, file_path)` - Analyze local file
- `begin_analyze_url(analyzer_id, document_url)` - Analyze from URL
- `poll_result(response, timeout_seconds)` - Poll for analysis result

### Storage
- `generate_sas_token(container_name)` - Generate SAS token for blob storage
- `upload_to_blob_storage(file_path, blob_name)` - Upload file to storage

## Configuration

Set environment variables:
```env
AZURE_AI_ENDPOINT=https://your-resource.services.ai.azure.com/
AZURE_AI_API_KEY=your-api-key
# Or use Azure AD authentication (DefaultAzureCredential)
```

## Related Tools

Tools that use this client:
- `cu-analyzer-create` - Create analyzers
- `cu-analyzer-run` - Run analysis
- `cu-analyzer-validate` - Validate schemas
- All other cu-analyzer-* tools
