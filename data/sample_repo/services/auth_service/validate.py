"""Token validation entrypoints used by gateway middleware."""

from __future__ import annotations

import time
from typing import Any

from packages.common.http_client import HttpClient
from packages.common.metrics import ERRORS, REQUESTS
from services.auth_service.jwt_ops import decode_unverified, verify_signature

# Optional remote revocation list lookup.
REVOCATION_BASE = "http://auth-service.internal"


def validate_token(token: str, *, check_revocation: bool = False) -> dict[str, Any]:
    REQUESTS.inc(component="auth_validate")
    if not token:
        ERRORS.inc(component="auth_validate", reason="empty")
        return {"valid": False, "reason": "empty"}
    if not verify_signature(token):
        ERRORS.inc(component="auth_validate", reason="bad_sig")
        return {"valid": False, "reason": "bad_signature"}
    try:
        claims = decode_unverified(token)
    except ValueError:
        ERRORS.inc(component="auth_validate", reason="malformed")
        return {"valid": False, "reason": "malformed"}
    exp = claims.get("exp")
    if isinstance(exp, int) and exp < int(time.time()):
        ERRORS.inc(component="auth_validate", reason="expired")
        return {"valid": False, "reason": "expired"}
    if check_revocation:
        client = HttpClient(REVOCATION_BASE, timeout_s=2.0, retries=0)
        try:
            status = client.get(f"/v1/revocations/{claims.get('jti', 'unknown')}")
            if status.get("revoked"):
                return {"valid": False, "reason": "revoked"}
        except RuntimeError:
            # Fail open for demo; production would fail closed for money paths.
            ERRORS.inc(component="auth_validate", reason="revocation_unreachable")
    return {
        "valid": True,
        "principal": {
            "sub": claims.get("sub"),
            "scopes": claims.get("scopes", []),
            "exp": claims.get("exp"),
        },
    }
