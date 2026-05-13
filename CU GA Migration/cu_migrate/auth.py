"""Authentication helpers for Azure Content Understanding.

Supports two modes:
1. Entra ID via ``DefaultAzureCredential`` (preferred)
2. Subscription key fallback
"""

from __future__ import annotations

import httpx
from azure.identity import DefaultAzureCredential

_SCOPE = "https://cognitiveservices.azure.com/.default"


class EntraIDAuth(httpx.Auth):
    """httpx auth flow using Entra ID / DefaultAzureCredential."""

    def __init__(self) -> None:
        self._credential = DefaultAzureCredential()

    def auth_flow(self, request: httpx.Request):
        token = self._credential.get_token(_SCOPE)
        request.headers["Authorization"] = f"Bearer {token.token}"
        yield request


class SubscriptionKeyAuth(httpx.Auth):
    """httpx auth flow using a subscription key header."""

    def __init__(self, key: str) -> None:
        self._key = key

    def auth_flow(self, request: httpx.Request):
        request.headers["Ocp-Apim-Subscription-Key"] = self._key
        yield request


def get_auth(subscription_key: str | None = None) -> httpx.Auth:
    """Return the appropriate auth handler.

    Prefers Entra ID; falls back to subscription key when provided.
    """
    if subscription_key:
        return SubscriptionKeyAuth(subscription_key)
    return EntraIDAuth()
