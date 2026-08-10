"""Billing routes exposed through the API gateway."""

from __future__ import annotations

from typing import Any, Callable

from packages.common.http_client import HttpClient
from packages.common.metrics import ERRORS, REQUESTS


class BillingRouter:
    def __init__(self, client: HttpClient) -> None:
        self.client = client

    def list_invoices(self, principal: dict[str, Any]) -> dict[str, Any]:
        REQUESTS.inc(route="billing.list_invoices")
        customer_id = principal.get("sub")
        if not customer_id:
            ERRORS.inc(route="billing.list_invoices", reason="missing_sub")
            return {"status": 400, "error": "missing_subject"}
        data = self.client.get(f"/v1/customers/{customer_id}/invoices")
        return {"status": 200, "invoices": data.get("items", [])}

    def create_charge(self, principal: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
        REQUESTS.inc(route="billing.create_charge")
        amount = body.get("amount_cents")
        currency = body.get("currency", "USD")
        if not isinstance(amount, int) or amount <= 0:
            ERRORS.inc(route="billing.create_charge", reason="invalid_amount")
            return {"status": 400, "error": "invalid_amount"}
        payload = {
            "customer_id": principal.get("sub"),
            "amount_cents": amount,
            "currency": currency,
            "idempotency_key": body.get("idempotency_key"),
        }
        result = self.client.post("/v1/charges", body=payload)
        return {"status": 202, "charge_id": result.get("id")}

    def dispatch(
        self,
        method: str,
        path: str,
        principal: dict[str, Any],
        body: dict[str, Any],
    ) -> dict[str, Any]:
        if method == "GET" and path.endswith("/invoices"):
            return self.list_invoices(principal)
        if method == "POST" and path.endswith("/charges"):
            return self.create_charge(principal, body)
        return {"status": 404, "error": "billing_route_not_found"}


def billing_router(client: HttpClient) -> BillingRouter:
    return BillingRouter(client)


Handler = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]
