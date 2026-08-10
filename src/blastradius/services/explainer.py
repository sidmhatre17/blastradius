from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import httpx

from blastradius.config import Settings, get_settings

logger = logging.getLogger(__name__)


@dataclass
class Explanation:
    summary: str
    suggested_tests: list[str]
    residual_risks: list[str]
    provider: str


class Explainer(ABC):
    @abstractmethod
    def explain(self, evidence: dict[str, Any]) -> Explanation:
        raise NotImplementedError


class TemplateExplainer(Explainer):
    """Deterministic fallback — never invents services/files/incidents."""

    def explain(self, evidence: dict[str, Any]) -> Explanation:
        score = evidence.get("risk_score")
        tier = evidence.get("risk_tier")
        changed = evidence.get("changed_files") or []
        services = evidence.get("affected_services") or []
        incidents = evidence.get("similar_incidents") or []
        factors = evidence.get("risk_factors") or []

        top_inc = incidents[0]["incident_id"] if incidents else None
        summary_parts = [
            f"Risk {score}/100 ({tier}).",
            f"Changed {len(changed)} file(s); affected services: {', '.join(services) or 'none'}.",
        ]
        if top_inc:
            summary_parts.append(f"Closest prior incident: {top_inc}.")
        hot = [
            f["name"]
            for f in factors
            if float(f.get("value") or 0) >= 0.5
        ]
        if hot:
            summary_parts.append("Elevated factors: " + ", ".join(hot) + ".")

        tests: list[str] = []
        for svc in services[:4]:
            tests.append(f"Regression: critical paths in {svc}")
        if any(p.startswith("packages/") for p in changed):
            tests.append("Integration: shared package consumers after HttpClient/timeout changes")
        if not tests:
            tests.append("Smoke: verify docs/copy renders; no service behavior change expected")

        residuals = [
            "Import graph is static (dynamic imports not modeled).",
            "Incident matches are retrieval-assisted heuristics, not proof of recurrence.",
        ]
        return Explanation(
            summary=" ".join(summary_parts),
            suggested_tests=tests,
            residual_risks=residuals,
            provider="template",
        )


class OllamaExplainer(Explainer):
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def explain(self, evidence: dict[str, Any]) -> Explanation:
        compact = {
            "risk_score": evidence.get("risk_score"),
            "risk_tier": evidence.get("risk_tier"),
            "changed_files": (evidence.get("changed_files") or [])[:20],
            "affected_services": evidence.get("affected_services") or [],
            "similar_incidents": (evidence.get("similar_incidents") or [])[:5],
            "risk_factors": evidence.get("risk_factors") or [],
        }
        prompt = (
            "You are BlastRadius. Using ONLY this evidence JSON, return JSON with keys "
            "summary (string), suggested_tests (array of strings), "
            "residual_risks (array of strings). "
            "Do not invent services, files, or incident IDs not present in evidence.\n\n"
            f"{json.dumps(compact)[:6000]}"
        )
        url = f"{self.settings.ollama_base_url.rstrip('/')}/api/chat"
        payload = {
            "model": self.settings.llm_model,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0},
            "messages": [
                {"role": "system", "content": "Reply with JSON only."},
                {"role": "user", "content": prompt},
            ],
        }
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
        content = (data.get("message") or {}).get("content") or "{}"
        parsed = json.loads(content)
        return Explanation(
            summary=str(parsed.get("summary") or "").strip() or "Analysis complete.",
            suggested_tests=[str(x) for x in (parsed.get("suggested_tests") or [])][:8],
            residual_risks=[str(x) for x in (parsed.get("residual_risks") or [])][:8],
            provider="ollama",
        )


def build_explainer(settings: Settings | None = None) -> Explainer:
    settings = settings or get_settings()
    mode = settings.app_mode.lower()
    provider = settings.llm_provider.lower()
    if mode == "ci" or provider == "template":
        return TemplateExplainer()
    if provider == "ollama":
        return OllamaExplainer(settings)
    return TemplateExplainer()


def explain_with_fallback(
    evidence: dict[str, Any],
    settings: Settings | None = None,
) -> Explanation:
    settings = settings or get_settings()
    primary = build_explainer(settings)
    try:
        return primary.explain(evidence)
    except Exception as exc:  # noqa: BLE001
        logger.warning("explainer failed (%s); falling back to template", exc)
        return TemplateExplainer().explain(evidence)
