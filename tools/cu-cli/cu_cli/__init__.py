"""
cu-cli: A unified command-line interface and operations layer for Azure AI
Content Understanding (CU).

This package wraps `AzureContentUnderstandingClient` (tools/cu-client) with a
small set of high-level, retry/poll-aware operations (create-and-wait,
analyze-and-wait, classify-and-wait, safe delete, etc.) that represent every
"talk to the live CU service" action used across CU-Tools.

Other tools in this repo (cu-analyzer-run, create_and_test.py, ...) import
`cu_cli.operations` instead of re-implementing polling/create/delete logic
against the raw client, so there is a single, tested place where CU
operations happen. The CLI entry point (`cu_cli.cli` / `python -m cu_cli`)
exposes the same operations for direct interactive/script use.
"""

from .operations import (
    CUCliError,
    get_client,
    resolve_api_version,
    validate_setup,
    list_analyzers,
    get_analyzer,
    create_analyzer_and_wait,
    delete_analyzer_safe,
    delete_analyzer,
    analyze_file_and_wait,
    analyze_url_and_wait,
    create_classifier_and_wait,
    classify_and_wait,
    get_defaults,
    update_defaults,
)

__all__ = [
    "CUCliError",
    "get_client",
    "resolve_api_version",
    "validate_setup",
    "list_analyzers",
    "get_analyzer",
    "create_analyzer_and_wait",
    "delete_analyzer_safe",
    "delete_analyzer",
    "analyze_file_and_wait",
    "analyze_url_and_wait",
    "create_classifier_and_wait",
    "classify_and_wait",
    "get_defaults",
    "update_defaults",
]
