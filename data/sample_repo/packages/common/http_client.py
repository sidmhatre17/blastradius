"""Shared HTTP client used across PayOrbit services."""

from __future__ import annotations

import json
import logging
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_S = 5.0
DEFAULT_RETRIES = 2


class HttpClient:
    """Thin urllib wrapper with retries and JSON helpers.

    Hot path for gateway auth calls, billing settlement posts, and notify webhooks.
    Timeout/retry changes here fan out to every importer.
    """

    def __init__(
        self,
        base_url: str,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        retries: int = DEFAULT_RETRIES,
        default_headers: dict[str, str] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.retries = retries
        self.default_headers = default_headers or {"Content-Type": "application/json"}

    def _url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        return f"{self.base_url}/{path.lstrip('/')}"

    def request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        payload = None if body is None else json.dumps(body).encode("utf-8")
        merged = {**self.default_headers, **(headers or {})}
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            req = Request(self._url(path), data=payload, headers=merged, method=method.upper())
            try:
                with urlopen(req, timeout=self.timeout_s) as resp:
                    raw = resp.read().decode("utf-8")
                    return json.loads(raw) if raw else {}
            except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc
                logger.warning("http_client attempt=%s failed: %s", attempt, exc)
                time.sleep(0.05 * (attempt + 1))
        raise RuntimeError(f"request failed after retries: {last_error}")

    def get(self, path: str, **kwargs: Any) -> dict[str, Any]:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, body: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
        return self.request("POST", path, body=body, **kwargs)
