"""Billing worker — settles charges and posts ledger entries."""

from __future__ import annotations

import logging
from typing import Any

from packages.common.http_client import HttpClient
from packages.common.metrics import ERRORS, LATENCY, REQUESTS
from services.billing_worker.retry import RetryPolicy, with_retries

logger = logging.getLogger(__name__)

LEDGER_BASE = "http://ledger.internal"
PROCESSOR_BASE = "http://card-processor.internal"


class BillingWorker:
    def __init__(self) -> None:
        self.ledger = HttpClient(LEDGER_BASE, timeout_s=5.0, retries=1)
        self.processor = HttpClient(PROCESSOR_BASE, timeout_s=10.0, retries=0)
        self.retry = RetryPolicy(max_attempts=5, base_delay_ms=100)

    def settle_charge(self, charge: dict[str, Any]) -> dict[str, Any]:
        REQUESTS.inc(component="billing_worker", op="settle")
        with LATENCY.time():
            def _capture() -> dict[str, Any]:
                return self.processor.post("/v1/capture", body=charge)

            try:
                capture = with_retries(self.retry, _capture)
            except RuntimeError as exc:
                ERRORS.inc(component="billing_worker", reason="capture_failed")
                logger.exception("capture failed for charge=%s", charge.get("id"))
                raise RuntimeError(f"capture failed: {exc}") from exc

            ledger_entry = self.ledger.post(
                "/v1/entries",
                body={
                    "charge_id": charge.get("id"),
                    "amount_cents": charge.get("amount_cents"),
                    "processor_ref": capture.get("ref"),
                    "status": "settled",
                },
            )
            return {"status": "settled", "ledger_id": ledger_entry.get("id")}


def main() -> None:
    worker = BillingWorker()
    demo = {"id": "chg_demo", "amount_cents": 2500, "currency": "USD"}
    print(worker.settle_charge(demo))


if __name__ == "__main__":
    main()
