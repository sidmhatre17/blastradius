from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from blastradius.db.models import Incident
from blastradius.services.vector_store import CODE_COLLECTION, INCIDENT_COLLECTION, VectorStore

FILE_OVERLAP_BOOST = 0.15
SERVICE_OVERLAP_BOOST = 0.10


@dataclass
class SimilarIncident:
    incident_id: str
    title: str
    score: float
    why: str
    snippet: str
    severity: str = "medium"
    services: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)


@dataclass
class CodeHit:
    path: str
    score: float
    snippet: str
    file_id: str | None = None


def build_query_pack(
    *,
    pr_title: str = "",
    changed_paths: list[str] | None = None,
    affected_services: list[str] | None = None,
    diff_excerpt: str = "",
) -> str:
    changed_paths = changed_paths or []
    affected_services = affected_services or []
    return "\n".join(
        [
            pr_title or "",
            " ".join(changed_paths),
            " ".join(affected_services),
            (diff_excerpt or "")[:2000],
        ]
    ).strip()


def overlap_boost(
    base_score: float,
    *,
    incident_files: list[str],
    incident_services: list[str],
    changed_files: list[str],
    affected_services: list[str],
) -> tuple[float, str]:
    reasons: list[str] = []
    score = base_score
    if set(incident_files) & set(changed_files):
        score += FILE_OVERLAP_BOOST
        reasons.append("file_overlap")
    if set(incident_services) & set(affected_services):
        score += SERVICE_OVERLAP_BOOST
        reasons.append("service_overlap")
    if not reasons:
        reasons.append("semantic")
    elif "file_overlap" in reasons or "service_overlap" in reasons:
        # keep semantic tag when base came from vectors
        if base_score > 0:
            reasons.append("semantic")
    why = "+".join(dict.fromkeys(reasons))
    return min(1.0, score), why


async def retrieve_similar_incidents(
    session: AsyncSession,
    store: VectorStore,
    *,
    query_pack: str,
    changed_files: list[str],
    affected_services: list[str],
    top_k: int = 8,
    vector_pool: int = 20,
) -> list[SimilarIncident]:
    hits = store.query(INCIDENT_COLLECTION, query_pack, n_results=vector_pool)
    by_id: dict[str, dict[str, Any]] = {}
    for hit in hits:
        iid = str(hit.metadata.get("incident_id") or "")
        if not iid:
            continue
        prev = by_id.get(iid)
        if prev is None or hit.score > prev["score"]:
            by_id[iid] = {
                "score": hit.score,
                "snippet": hit.text[:280],
                "title": hit.metadata.get("title") or iid,
                "severity": hit.metadata.get("severity") or "medium",
            }

    # Metadata candidate expansion (critical for HashEmbedder / CI recall).
    incidents = list((await session.execute(select(Incident))).scalars().all())
    for inc in incidents:
        files = [str(x) for x in (inc.files_json or [])]
        services = [str(x) for x in (inc.services_json or [])]
        overlaps_files = bool(set(files) & set(changed_files))
        overlaps_services = bool(set(services) & set(affected_services))
        overlaps = overlaps_files or overlaps_services
        if not overlaps and inc.incident_id not in by_id:
            continue
        if inc.incident_id not in by_id:
            by_id[inc.incident_id] = {
                "score": 0.01 if overlaps else 0.0,
                "snippet": (inc.body or "")[:280],
                "title": inc.title,
                "severity": inc.severity,
            }
        # Exact file overlap is strong evidence (esp. HashEmbedder / CI).
        if overlaps_files:
            by_id[inc.incident_id]["score"] = max(float(by_id[inc.incident_id]["score"]), 0.85)
        by_id[inc.incident_id]["files"] = files
        by_id[inc.incident_id]["services"] = services
        by_id[inc.incident_id]["title"] = inc.title
        by_id[inc.incident_id]["severity"] = inc.severity
        if not by_id[inc.incident_id].get("snippet"):
            by_id[inc.incident_id]["snippet"] = (inc.body or "")[:280]

    # Fill metadata for vector-only hits
    missing = [iid for iid, row in by_id.items() if "files" not in row]
    if missing:
        rows = (
            await session.execute(select(Incident).where(Incident.incident_id.in_(missing)))
        ).scalars()
        for inc in rows:
            by_id[inc.incident_id]["files"] = [str(x) for x in (inc.files_json or [])]
            by_id[inc.incident_id]["services"] = [str(x) for x in (inc.services_json or [])]
            by_id[inc.incident_id]["title"] = inc.title
            by_id[inc.incident_id]["severity"] = inc.severity

    ranked: list[SimilarIncident] = []
    for iid, row in by_id.items():
        files = list(row.get("files") or [])
        services = list(row.get("services") or [])
        score, why = overlap_boost(
            float(row["score"]),
            incident_files=files,
            incident_services=services,
            changed_files=changed_files,
            affected_services=affected_services,
        )
        ranked.append(
            SimilarIncident(
                incident_id=iid,
                title=str(row.get("title") or iid),
                score=score,
                why=why,
                snippet=str(row.get("snippet") or ""),
                severity=str(row.get("severity") or "medium"),
                services=services,
                files=files,
            )
        )
    ranked.sort(key=lambda x: x.score, reverse=True)
    return ranked[:top_k]


def retrieve_code_chunks(
    store: VectorStore,
    *,
    query_pack: str,
    repo_id: str | None = None,
    top_k: int = 8,
) -> list[CodeHit]:
    where = {"repo_id": repo_id} if repo_id else None
    hits = store.query(CODE_COLLECTION, query_pack, n_results=top_k, where=where)
    out: list[CodeHit] = []
    for hit in hits:
        out.append(
            CodeHit(
                path=str(hit.metadata.get("path") or ""),
                score=hit.score,
                snippet=hit.text[:280],
                file_id=str(hit.metadata.get("file_id") or "") or None,
            )
        )
    return out
