"""Notification copy templates."""

from __future__ import annotations

TEMPLATES = {
    "payment_succeeded": "Hi {name}, your payment of {amount} {currency} succeeded.",
    "payment_failed": "Hi {name}, we could not process {amount} {currency}. Please update your card.",
    "retry_exhausted": "Ops alert: billing retry exhausted for charge {charge_id}: {reason}",
    "welcome": "Welcome to PayOrbit, {name}!",
}


def render(template_id: str, **fields: str) -> str:
    template = TEMPLATES.get(template_id)
    if template is None:
        raise KeyError(f"unknown template: {template_id}")
    return template.format(**fields)
