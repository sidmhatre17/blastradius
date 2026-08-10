"""API gateway entrypoint — routes traffic and bootstraps shared clients."""

from __future__ import annotations

import logging
from typing import Any

from packages.common.http_client import HttpClient
from packages.common.metrics import ERRORS, LATENCY, REQUESTS
from services.api_gateway.auth.middleware import AuthMiddleware
from services.api_gateway.routes.billing import billing_router

logger = logging.getLogger(__name__)

AUTH_BASE = "http://auth-service.internal"
BILLING_BASE = "http://billing-worker.internal"


class GatewayApp:
    def __init__(self) -> None:
        self.auth_client = HttpClient(AUTH_BASE, timeout_s=3.0, retries=1)
        self.billing_client = HttpClient(BILLING_BASE, timeout_s=8.0, retries=2)
        self.auth = AuthMiddleware(self.auth_client)
        self.billing = billing_router(self.billing_client)

    def handle(self, method: str, path: str, headers: dict[str, str], body: dict[str, Any] | None = None) -> dict[str, Any]:
        REQUESTS.inc(route=path, method=method)
        with LATENCY.time():
            principal = self.auth.authenticate(headers)
            if principal is None:
                ERRORS.inc(route=path, reason="unauthorized")
                return {"status": 401, "error": "unauthorized"}
            if path.startswith("/v1/billing"):
                return self.billing.dispatch(method, path, principal, body or {})
            return {"status": 404, "error": "not_found"}


def create_app() -> GatewayApp:
    logger.info("starting api_gateway")
    return GatewayApp()


def main() -> None:
    app = create_app()
    # Demo loop only — ingest never executes this.
    sample_headers = {"Authorization": "Bearer demo-token"}
    print(app.handle("GET", "/v1/billing/invoices", sample_headers))


if __name__ == "__main__":
    main()
