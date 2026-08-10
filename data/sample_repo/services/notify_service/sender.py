"""Outbound notification sender (email/webhook)."""

from __future__ import annotations

import logging
from typing import Any

from packages.common.http_client import HttpClient
from packages.common.metrics import ERRORS, REQUESTS
from services.notify_service.templates import render

logger = logging.getLogger(__name__)

WEBHOOK_BASE = "http://webhook-relay.internal"
MAILER_BASE = "http://mailer.internal"


class NotificationSender:
    def __init__(self) -> None:
        self.webhooks = HttpClient(WEBHOOK_BASE, timeout_s=4.0, retries=1)
        self.mailer = HttpClient(MAILER_BASE, timeout_s=6.0, retries=1)

    def send_template(
        self,
        channel: str,
        template_id: str,
        destination: str,
        fields: dict[str, str],
    ) -> dict[str, Any]:
        REQUESTS.inc(component="notify_sender", channel=channel)
        body_text = render(template_id, **fields)
        payload = {"to": destination, "body": body_text, "template_id": template_id}
        try:
            if channel == "webhook":
                return self.webhooks.post("/v1/deliver", body=payload)
            if channel == "email":
                return self.mailer.post("/v1/send", body=payload)
            ERRORS.inc(component="notify_sender", reason="bad_channel")
            return {"status": "error", "error": "unsupported_channel"}
        except RuntimeError as exc:
            ERRORS.inc(component="notify_sender", reason="delivery_failed")
            logger.error("notify delivery failed channel=%s: %s", channel, exc)
            return {"status": "error", "error": str(exc)}
