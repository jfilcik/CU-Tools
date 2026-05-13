"""REST client for the Azure Content Understanding API.

Covers analyzer CRUD operations needed for migration:
- List analyzers
- Get analyzer definition
- Create a new GA analyzer
"""

from __future__ import annotations

from typing import Any

import httpx

from cu_migrate.auth import get_auth

_API_VERSION_PREVIEW = "2025-11-01"
_API_VERSION_GA = "2025-11-01"


class CUClient:
    """Thin REST wrapper around the Content Understanding API."""

    def __init__(
        self,
        endpoint: str,
        subscription_key: str | None = None,
        api_version_read: str = _API_VERSION_PREVIEW,
        api_version_write: str = _API_VERSION_GA,
        timeout: float = 60.0,
    ) -> None:
        if not endpoint:
            raise ValueError(
                "Endpoint is required. Provide --endpoint or set CU_ENDPOINT environment variable.\n"
                "Example: https://<your-resource>.cognitiveservices.azure.com"
            )
        if not endpoint.startswith(("http://", "https://")):
            raise ValueError(
                f"Endpoint must start with 'http://' or 'https://'. Got: {endpoint!r}\n"
                "Example: https://<your-resource>.cognitiveservices.azure.com"
            )
        self.endpoint = endpoint.rstrip("/")
        self._api_version_read = api_version_read
        self._api_version_write = api_version_write
        auth = get_auth(subscription_key)
        self._http = httpx.Client(auth=auth, timeout=timeout)

    # ------------------------------------------------------------------
    # Read operations (against Preview to inspect existing analyzers)
    # ------------------------------------------------------------------

    def list_analyzers(self) -> list[dict[str, Any]]:
        """Return all analyzers in the resource."""
        url = f"{self.endpoint}/contentunderstanding/analyzers"
        params = {"api-version": self._api_version_read}
        resp = self._http.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        return data.get("value", [])

    def get_analyzer(self, analyzer_id: str) -> dict[str, Any]:
        """Return the full definition of one analyzer."""
        url = f"{self.endpoint}/contentunderstanding/analyzers/{analyzer_id}"
        params = {"api-version": self._api_version_read}
        resp = self._http.get(url, params=params)
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Write operations (against GA to create new analyzers)
    # ------------------------------------------------------------------

    def create_analyzer(self, analyzer_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Create a new GA analyzer via PUT."""
        url = f"{self.endpoint}/contentunderstanding/analyzers/{analyzer_id}"
        params = {"api-version": self._api_version_write}
        resp = self._http.put(url, params=params, json=payload)
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "CUClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
