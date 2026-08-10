"""JWT encode/decode helpers for auth_service."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

DEFAULT_TTL_S = 3600
# Demo signing secret — not used in production; sample world only.
DEMO_SECRET = b"payorbit-demo-secret"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_json(payload: dict[str, Any]) -> str:
    return _b64url(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))


def sign_token(claims: dict[str, Any], secret: bytes = DEMO_SECRET, ttl_s: int = DEFAULT_TTL_S) -> str:
    body = dict(claims)
    now = int(time.time())
    body.setdefault("iat", now)
    body.setdefault("exp", now + ttl_s)
    header = _b64url_json({"alg": "HS256", "typ": "JWT"})
    payload = _b64url_json(body)
    signing_input = f"{header}.{payload}".encode("ascii")
    sig = hmac.new(secret, signing_input, hashlib.sha256).digest()
    return f"{header}.{payload}.{_b64url(sig)}"


def decode_unverified(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("malformed token")
    padded = parts[1] + "=" * (-len(parts[1]) % 4)
    raw = base64.urlsafe_b64decode(padded.encode("ascii"))
    return json.loads(raw.decode("utf-8"))


def verify_signature(token: str, secret: bytes = DEMO_SECRET) -> bool:
    parts = token.split(".")
    if len(parts) != 3:
        return False
    signing_input = f"{parts[0]}.{parts[1]}".encode("ascii")
    expected = hmac.new(secret, signing_input, hashlib.sha256).digest()
    padded = parts[2] + "=" * (-len(parts[2]) % 4)
    actual = base64.urlsafe_b64decode(padded.encode("ascii"))
    return hmac.compare_digest(expected, actual)
