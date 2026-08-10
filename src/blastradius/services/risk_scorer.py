from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from typing import Any

from blastradius.services.diff_parser import ChangedFile
from blastradius.services.retrieval import SimilarIncident

SCORER_VERSION = "v1"

WEIGHTS: dict[str, float] = {
    "shared_library_touch": 0.25,
    "incident_heat": 0.25,
    "critical_service_touch": 0.15,
    "fan_out_degree": 0.15,
    "config_or_migration": 0.10,
    "test_gap": 0.10,
}

CRITICALITY_WEIGHT: dict[str, float] = {
    "low": 0.25,
    "medium": 0.5,
    "high": 0.75,
    "critical": 1.0,
}

SEVERITY_WEIGHT: dict[str, float] = {
    "low": 0.25,
    "medium": 0.5,
    "high": 0.75,
    "critical": 1.0,
}


@dataclass
class RiskFactor:
    name: str
    weight: float
    value: float
    contribution: float
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RiskResult:
    risk_score: int
    risk_tier: str
    risk_factors: list[RiskFactor]
    scorer_version: str = SCORER_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "risk_score": self.risk_score,
            "risk_tier": self.risk_tier,
            "risk_factors": [f.to_dict() for f in self.risk_factors],
            "scorer_version": self.scorer_version,
        }


def tier_for_score(score: int) -> str:
    if score <= 24:
        return "low"
    if score <= 49:
        return "medium"
    if score <= 74:
        return "high"
    return "critical"


def criticality_weight(level: str | None) -> float:
    if not level:
        return 0.0
    return CRITICALITY_WEIGHT.get(level.lower(), 0.0)


def severity_weight(level: str | None) -> float:
    if not level:
        return 0.0
    return SEVERITY_WEIGHT.get(level.lower(), 0.0)


def shared_library_touch(changed: Iterable[ChangedFile]) -> tuple[float, list[str]]:
    evidence = [f.path for f in changed if f.path.startswith("packages/")]
    return (1.0 if evidence else 0.0, evidence)


def incident_heat_value(
    changed: list[ChangedFile],
    similar: list[SimilarIncident],
) -> tuple[float, list[str]]:
    if changed and all(f.is_docs for f in changed):
        return 0.0, []
    heats: list[tuple[float, str]] = []
    for inc in similar[:3]:
        heat = float(inc.score) * severity_weight(inc.severity)
        heats.append((heat, inc.incident_id))
    if not heats:
        return 0.0, []
    best = max(heats, key=lambda x: x[0])
    return best[0], [best[1]]


def critical_service_touch_value(
    affected_services: list[str],
    owners: dict[str, Any] | None,
) -> tuple[float, list[str]]:
    services_meta = (owners or {}).get("services") or {}
    best = 0.0
    evidence: list[str] = []
    for svc in affected_services:
        meta = services_meta.get(svc) or {}
        level = meta.get("criticality") if isinstance(meta, dict) else None
        weight = criticality_weight(level if isinstance(level, str) else None)
        if weight > best:
            best = weight
            evidence = [f"{svc}:{level}"]
    return best, evidence


def fan_out_degree_value(
    changed: list[ChangedFile],
    importer_counts: dict[str, int],
) -> tuple[float, list[str]]:
    if not changed:
        return 0.0, []
    m = 0
    evidence_path = ""
    for f in changed:
        count = int(importer_counts.get(f.path, 0))
        if count > m:
            m = count
            evidence_path = f.path
    value = min(1.0, m / 6.0)
    evidence = [f"importers={m}"] + ([evidence_path] if evidence_path else [])
    return value, evidence


def config_or_migration_value(changed: list[ChangedFile]) -> tuple[float, list[str]]:
    evidence = [f.path for f in changed if f.is_config or f.is_migration]
    return (1.0 if evidence else 0.0, evidence)


def test_gap_value(changed: list[ChangedFile]) -> tuple[float, list[str]]:
    if not changed:
        return 0.0, []
    if all(f.is_docs for f in changed):
        return 0.0, []
    has_code = any(not f.is_docs for f in changed)
    has_test = any(f.is_test for f in changed)
    if has_code and not has_test:
        return 1.0, ["no tests in diff"]
    return 0.0, []


def score_risk(
    changed: list[ChangedFile],
    *,
    affected_services: list[str],
    importer_counts: dict[str, int],
    similar_incidents: list[SimilarIncident],
    owners_json: dict[str, Any] | None,
) -> RiskResult:
    factors: list[RiskFactor] = []

    def add(name: str, value: float, evidence: list[str]) -> None:
        weight = WEIGHTS[name]
        factors.append(
            RiskFactor(
                name=name,
                weight=weight,
                value=float(value),
                contribution=weight * float(value),
                evidence=evidence,
            )
        )

    v, e = shared_library_touch(changed)
    add("shared_library_touch", v, e)
    v, e = incident_heat_value(changed, similar_incidents)
    add("incident_heat", v, e)
    v, e = critical_service_touch_value(affected_services, owners_json)
    add("critical_service_touch", v, e)
    v, e = fan_out_degree_value(changed, importer_counts)
    add("fan_out_degree", v, e)
    v, e = config_or_migration_value(changed)
    add("config_or_migration", v, e)
    v, e = test_gap_value(changed)
    add("test_gap", v, e)

    # Ensure all six factors always present in locked order
    assert [f.name for f in factors] == list(WEIGHTS)

    raw = sum(f.contribution for f in factors)
    score = int(round(100 * raw))
    return RiskResult(risk_score=score, risk_tier=tier_for_score(score), risk_factors=factors)
