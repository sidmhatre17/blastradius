"""Gateway auth middleware — validates bearer tokens via auth_service."""

from __future__ import annotations

import logging
from typing import Any

from packages.common.http_client import HttpClient
from packages.common.metrics import ERRORS, REQUESTS
from services.auth_service.validate import validate_token

logger = logging.getLogger(__name__)

# Soft deadline used when auth_service is slow; historically caused cascades
# when set below auth p95 latency (see INC-1042).
AUTH_DEADLINE_MS = 800


class AuthMiddleware:
    def __init__(self, client: HttpClient) -> None:
        self.client = client
        self.deadline_ms = AUTH_DEADLINE_MS

    def _extract_bearer(self, headers: dict[str, str]) -> str | None:
        value = headers.get("Authorization") or headers.get("authorization")
        if not value:
            return None
        parts = value.split(" ", 1)
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None
        return parts[1].strip() or None

    def authenticate(self, headers: dict[str, str]) -> dict[str, Any] | None:
        REQUESTS.inc(component="auth_middleware")
        token = self._extract_bearer(headers)
        if token is None:
            ERRORS.inc(component="auth_middleware", reason="missing_token")
            return None
        # Prefer local validation when possible; fall back to remote introspect.
        local = validate_token(token)
        if local.get("valid"):
            return local.get("principal")
        try:
            remote = self.client.post(
                "/v1/introspect",
                body={"token": token, "deadline_ms": self.deadline_ms},
            )
        except RuntimeError as exc:
            logger.error("auth introspect failed under deadline=%sms: %s", self.deadline_ms, exc)
            ERRORS.inc(component="auth_middleware", reason="timeout")
            return None
        if not remote.get("active"):
            ERRORS.inc(component="auth_middleware", reason="inactive")
            return None
        return {
            "sub": remote.get("sub"),
            "scopes": remote.get("scopes", []),
            "exp": remote.get("exp"),
        }
