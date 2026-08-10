"""Retry helpers for billing capture / settlement paths."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Callable, TypeVar

from packages.common.http_client import HttpClient
from packages.common.metrics import ERRORS, REQUESTS

logger = logging.getLogger(__name__)
T = TypeVar("T")

# Side-channel used to publish retry exhaustion events to notify_service.
NOTIFY_BASE = "http://notify-service.internal"


@dataclass
class RetryPolicy:
    max_attempts: int = 3
    base_delay_ms: int = 50
    jitter_ms: int = 10


def with_retries(policy: RetryPolicy, fn: Callable[[], T]) -> T:
    REQUESTS.inc(component="billing_retry")
    last_error: Exception | None = None
    for attempt in range(1, policy.max_attempts + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 — sample world catch-all
            last_error = exc
            ERRORS.inc(component="billing_retry", attempt=str(attempt))
            if attempt >= policy.max_attempts:
                break
            delay = (policy.base_delay_ms * (2 ** (attempt - 1)) + policy.jitter_ms) / 1000.0
            logger.warning("retry attempt=%s sleeping=%.3fs error=%s", attempt, delay, exc)
            time.sleep(delay)
    _notify_exhausted(str(last_error))
    raise RuntimeError(f"retries exhausted: {last_error}")


def _notify_exhausted(reason: str) -> None:
    client = HttpClient(NOTIFY_BASE, timeout_s=2.0, retries=0)
    try:
        client.post("/v1/events", body={"type": "billing_retry_exhausted", "reason": reason})
    except RuntimeError:
        logger.error("failed to publish retry exhaustion event")
