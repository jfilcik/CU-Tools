"""
cu_cli.operations - High-level operations against the live Content
Understanding (CU) service.

Every function here either talks directly to
`AzureContentUnderstandingClient` (tools/cu-client) or composes a small
number of its calls into a single "do the whole thing and wait for it to
finish" operation (create analyzer + poll until ready, analyze + poll for
result, classify + poll for result, safe delete, etc.).

This module is the single place in CU-Tools where the actual network calls
to CU happen. Higher-level workflow tools (schema validation, scale/
stability test orchestration, comparison reports, CSV export, ...) should
import these functions instead of re-implementing polling/create/delete
logic against the raw client.
"""

import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

# Make the shared cu-client library importable regardless of caller cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "cu-client"))

from content_understanding_client import AzureContentUnderstandingClient  # noqa: E402

DEFAULT_API_VERSION = "2025-11-01"
DEFAULT_CREATE_MAX_WAIT_SECONDS = 120
DEFAULT_CREATE_POLL_INTERVAL_SECONDS = 3
DEFAULT_ANALYZE_TIMEOUT_SECONDS = 180


class CUCliError(Exception):
    """Raised for cu-cli operation failures that are not raw HTTP errors."""


def resolve_api_version(api_version: Optional[str] = None) -> str:
    """Resolve an explicit API version without changing the GA default."""
    resolved = api_version or os.getenv("CU_API_VERSION") or DEFAULT_API_VERSION
    if not isinstance(resolved, str) or not resolved.strip():
        raise CUCliError("CU API version must be a non-empty string")
    return resolved.strip()


def get_client(
    api_version: Optional[str] = None,
    endpoint: Optional[str] = None,
    api_key: Optional[str] = None,
    x_ms_useragent: str = "cu-cli",
    load_env: bool = True,
) -> AzureContentUnderstandingClient:
    """
    Build a CU client from explicit args, falling back to environment
    variables (and a `.env` file, if present) for endpoint/API key/version.
    """
    if load_env:
        load_dotenv()

    endpoint = endpoint or os.getenv("AZURE_AI_ENDPOINT")
    api_key = api_key or os.getenv("AZURE_AI_API_KEY")
    resolved_api_version = resolve_api_version(api_version)

    if not endpoint:
        raise CUCliError("AZURE_AI_ENDPOINT environment variable not set")
    if not api_key:
        raise CUCliError("AZURE_AI_API_KEY environment variable not set")

    return AzureContentUnderstandingClient(
        endpoint=endpoint,
        api_version=resolved_api_version,
        subscription_key=api_key,
        x_ms_useragent=x_ms_useragent,
    )


def validate_setup(
    client: AzureContentUnderstandingClient, verbose: bool = False
) -> Dict[str, Any]:
    """Validate connectivity/authentication against the CU service."""
    return client.validate_setup(verbose=verbose)


def list_analyzers(client: AzureContentUnderstandingClient) -> List[Dict[str, Any]]:
    """List all analyzers on the configured CU resource."""
    return client.get_all_analyzers().get("value", [])


def get_analyzer(
    client: AzureContentUnderstandingClient, analyzer_id: str
) -> Dict[str, Any]:
    """Get a single analyzer's detail by ID."""
    return client.get_analyzer_detail_by_id(analyzer_id)


def create_analyzer_and_wait(
    client: AzureContentUnderstandingClient,
    analyzer_id: str,
    schema: dict,
    max_wait: int = DEFAULT_CREATE_MAX_WAIT_SECONDS,
    poll_interval: int = DEFAULT_CREATE_POLL_INTERVAL_SECONDS,
    replace_existing: bool = True,
    on_progress: Optional[callable] = None,
) -> Dict[str, Any]:
    """
    Create an analyzer from `schema` and poll until it is ready.

    Args:
        client: An initialized AzureContentUnderstandingClient.
        analyzer_id: The analyzer ID to create.
        schema: The analyzer schema/template dict.
        max_wait: Maximum seconds to wait for the analyzer to become ready.
        poll_interval: Seconds between status polls.
        replace_existing: If True (default), best-effort delete any existing
            analyzer with the same ID before creating (useful for retries).
        on_progress: Optional callback(status: str, elapsed: int) invoked on
            every poll, for callers that want to print/log progress.

    Returns:
        The analyzer detail dict once its status is succeeded/ready.

    Raises:
        CUCliError: If the analyzer creation fails or times out.
    """
    if poll_interval <= 0:
        raise CUCliError("poll_interval must be greater than 0 to avoid an infinite poll loop")

    if replace_existing:
        try:
            client.delete_analyzer(analyzer_id)
            time.sleep(2)
        except Exception:
            pass  # Analyzer doesn't exist yet - that's fine.

    client.begin_create_analyzer(analyzer_id, analyzer_template=schema)

    elapsed = 0
    while elapsed < max_wait:
        try:
            detail = client.get_analyzer_detail_by_id(analyzer_id)
        except Exception:
            # Tolerate transient polling errors (e.g. brief network blips);
            # a genuine failure is reported via the analyzer's own status.
            time.sleep(poll_interval)
            elapsed += poll_interval
            continue

        status = detail.get("status", "Unknown")

        if on_progress:
            on_progress(status, elapsed)

        if status.lower() in ("succeeded", "ready"):
            return detail
        if status.lower() == "failed":
            raise CUCliError(f"Analyzer creation failed: {detail.get('error', detail)}")

        time.sleep(poll_interval)
        elapsed += poll_interval

    raise CUCliError(f"Analyzer '{analyzer_id}' not ready after {max_wait} seconds")


def delete_analyzer(client: AzureContentUnderstandingClient, analyzer_id: str) -> None:
    """Delete an analyzer, raising on failure."""
    client.delete_analyzer(analyzer_id)


def delete_analyzer_safe(
    client: AzureContentUnderstandingClient,
    analyzer_id: str,
    on_error: Optional[callable] = None,
) -> bool:
    """
    Delete an analyzer, swallowing errors (e.g. already deleted).

    Returns:
        True if the delete call succeeded, False if it raised (the
        exception is passed to `on_error` if provided).
    """
    try:
        client.delete_analyzer(analyzer_id)
        return True
    except Exception as e:  # noqa: BLE001 - intentional best-effort cleanup
        if on_error:
            on_error(e)
        return False


def cleanup_analyzer_set(
    client: AzureContentUnderstandingClient,
    analyzer_ids: List[str],
    on_error: Optional[callable] = None,
) -> None:
    """Delete a set of analyzers in reverse creation order (best-effort)."""
    for analyzer_id in reversed(analyzer_ids):
        delete_analyzer_safe(client, analyzer_id, on_error=on_error)


def analyze_file_and_wait(
    client: AzureContentUnderstandingClient,
    analyzer_id: str,
    file_path: Path,
    timeout: int = DEFAULT_ANALYZE_TIMEOUT_SECONDS,
    diagnostics: bool = False,
) -> Dict[str, Any]:
    """Submit a local file for analysis and poll until the result is ready."""
    response = client.begin_analyze_binary(
        analyzer_id, str(file_path), diagnostics=diagnostics
    )
    return client.poll_result(response, timeout_seconds=timeout, diagnostics=diagnostics)


def analyze_url_and_wait(
    client: AzureContentUnderstandingClient,
    analyzer_id: str,
    url: str,
    timeout: int = DEFAULT_ANALYZE_TIMEOUT_SECONDS,
    diagnostics: bool = False,
) -> Dict[str, Any]:
    """Submit a document URL for analysis and poll until the result is ready."""
    response = client.begin_analyze_url(analyzer_id, url, diagnostics=diagnostics)
    return client.poll_result(response, timeout_seconds=timeout, diagnostics=diagnostics)


def create_classifier_and_wait(
    client: AzureContentUnderstandingClient,
    classifier_id: str,
    schema: dict,
    max_wait: int = DEFAULT_CREATE_MAX_WAIT_SECONDS,
    poll_interval: int = DEFAULT_CREATE_POLL_INTERVAL_SECONDS,
    replace_existing: bool = True,
) -> Dict[str, Any]:
    """Create a classifier from `schema` and poll until it is ready."""
    if poll_interval <= 0:
        raise CUCliError("poll_interval must be greater than 0 to avoid an infinite poll loop")

    if replace_existing:
        try:
            client.delete_analyzer(classifier_id)
            time.sleep(2)
        except Exception:
            pass

    client.begin_create_classifier(classifier_id, classifier_schema=schema)

    elapsed = 0
    while elapsed < max_wait:
        detail = client.get_analyzer_detail_by_id(classifier_id)
        status = detail.get("status", "Unknown")

        if status.lower() in ("succeeded", "ready"):
            return detail
        if status.lower() == "failed":
            raise CUCliError(f"Classifier creation failed: {detail.get('error', detail)}")

        time.sleep(poll_interval)
        elapsed += poll_interval

    raise CUCliError(f"Classifier '{classifier_id}' not ready after {max_wait} seconds")


def classify_and_wait(
    client: AzureContentUnderstandingClient,
    classifier_id: str,
    file_location: str,
    timeout: int = DEFAULT_ANALYZE_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    """Submit a file/URL for classification and poll until the result is ready."""
    response = client.begin_classify(classifier_id, file_location)
    return client.poll_result(response, timeout_seconds=timeout)


def get_defaults(client: AzureContentUnderstandingClient) -> Dict[str, Any]:
    """Get default model deployment mappings for the CU resource."""
    return client.get_defaults()


def update_defaults(
    client: AzureContentUnderstandingClient, model_deployments: Dict[str, Optional[str]]
) -> Dict[str, Any]:
    """Update default model deployment mappings for the CU resource."""
    return client.update_defaults(model_deployments)
