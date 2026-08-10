from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path
from typing import Any
from uuid import UUID

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from blastradius.config import Settings, get_settings
from blastradius.db.models import Analysis, Repo
from blastradius.domain.enums import AnalysisStatus
from blastradius.services.code_graph import CodeGraph, service_name_for_path
from blastradius.services.diff_parser import parse_diff
from blastradius.services.embeddings import build_embedder
from blastradius.services.explainer import explain_with_fallback
from blastradius.services.repo_ingest import load_import_edge_pairs, load_path_service_map
from blastradius.services.retrieval import (
    build_query_pack,
    retrieve_code_chunks,
    retrieve_similar_incidents,
)
from blastradius.services.risk_scorer import SCORER_VERSION, score_risk
from blastradius.services.vector_store import VectorStore

logger = logging.getLogger(__name__)

MAX_DIFF_BYTES = 500 * 1024


class AnalyzeError(Exception):
    def __init__(self, code: str, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def diff_cache_key(repo_id: UUID | str, diff_text: str, app_mode: str) -> str:
    material = f"{repo_id}|{diff_text}|{app_mode}|{SCORER_VERSION}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _load_owners_from_repo(repo: Repo) -> dict[str, Any] | None:
    if repo.owners_json:
        return repo.owners_json
    owners_path = Path(repo.root_path) / "SERVICE_OWNERS.yaml"
    if owners_path.exists():
        data = yaml.safe_load(owners_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    return None


async def find_cached_analysis(
    session: AsyncSession,
    *,
    repo_id: UUID,
    diff_hash: str,
) -> Analysis | None:
    return await session.scalar(
        select(Analysis)
        .where(Analysis.repo_id == repo_id)
        .where(Analysis.diff_hash == diff_hash)
        .where(Analysis.status == AnalysisStatus.COMPLETED.value)
        .order_by(Analysis.created_at.desc())
        .limit(1)
    )


async def run_analysis(
    session: AsyncSession,
    analysis_id: UUID,
    *,
    settings: Settings | None = None,
    vector_store: VectorStore | None = None,
) -> Analysis:
    settings = settings or get_settings()
    analysis = await session.get(Analysis, analysis_id)
    if analysis is None:
        raise AnalyzeError("ANALYZE_FAILED", f"analysis {analysis_id} not found")

    analysis.status = AnalysisStatus.RUNNING.value
    await session.commit()

    started = time.perf_counter()
    try:
        repo = await session.get(Repo, analysis.repo_id)
        if repo is None:
            raise AnalyzeError("REPO_NOT_FOUND", f"repo {analysis.repo_id} not found")

        report = analysis.report_json or {}
        diff_text = str(report.get("_diff_text") or "")
        pr_title = analysis.pr_title or ""
        if not diff_text:
            raise AnalyzeError("INVALID_DIFF", "missing diff_text on analysis")

        store = vector_store or VectorStore(settings=settings, embedder=build_embedder(settings))
        pairs = await load_import_edge_pairs(session, repo.id)
        path_map = await load_path_service_map(session, repo.id)
        graph = CodeGraph(pairs, path_map)

        try:
            changed = parse_diff(diff_text)
        except Exception as exc:  # noqa: BLE001
            raise AnalyzeError("INVALID_DIFF", f"could not parse diff: {exc}") from exc

        paths = [c.path for c in changed]
        blast = graph.expand_blast_radius(paths, depth=2, cap=50)
        affected = sorted(
            {n["label"] for n in blast.nodes if n["type"] == "service"}
            | {s for p in paths if (s := service_name_for_path(p))}
        )
        pack = build_query_pack(
            pr_title=pr_title,
            changed_paths=paths,
            affected_services=affected,
            diff_excerpt=diff_text,
        )
        similar = await retrieve_similar_incidents(
            session,
            store,
            query_pack=pack,
            changed_files=paths,
            affected_services=affected,
            top_k=8,
        )
        code_hits = retrieve_code_chunks(
            store, query_pack=pack, repo_id=str(repo.id), top_k=8
        )
        importer_counts = {p: graph.importer_count(p) for p in paths}
        risk = score_risk(
            changed,
            affected_services=affected,
            importer_counts=importer_counts,
            similar_incidents=similar,
            owners_json=_load_owners_from_repo(repo),
        )

        similar_payload = [
            {
                "incident_id": s.incident_id,
                "title": s.title,
                "score": round(s.score, 4),
                "why": s.why,
                "snippet": s.snippet,
            }
            for s in similar
        ]
        evidence = {
            "risk_score": risk.risk_score,
            "risk_tier": risk.risk_tier,
            "changed_files": paths,
            "affected_services": affected,
            "similar_incidents": similar_payload,
            "risk_factors": [f.to_dict() for f in risk.risk_factors],
        }
        explanation = explain_with_fallback(evidence, settings)

        latency_ms = int((time.perf_counter() - started) * 1000)
        report_out = {
            "analysis_id": str(analysis.id),
            "repo_id": str(repo.id),
            "status": AnalysisStatus.COMPLETED.value,
            "risk_score": risk.risk_score,
            "risk_tier": risk.risk_tier,
            "summary": explanation.summary,
            "changed_files": paths,
            "affected_services": affected,
            "blast_radius": {"nodes": blast.nodes, "edges": blast.edges},
            "similar_incidents": similar_payload,
            "risk_factors": [f.to_dict() for f in risk.risk_factors],
            "suggested_tests": explanation.suggested_tests,
            "residual_risks": explanation.residual_risks,
            "mode": settings.app_mode,
            "latency_ms": latency_ms,
            "cost_usd": 0.0,
            "explainer": explanation.provider,
            "code_context": [
                {"path": c.path, "score": c.score, "snippet": c.snippet} for c in code_hits
            ],
            "scorer_version": SCORER_VERSION,
        }

        analysis.status = AnalysisStatus.COMPLETED.value
        analysis.risk_score = risk.risk_score
        analysis.risk_tier = risk.risk_tier
        analysis.report_json = report_out
        analysis.latency_ms = latency_ms
        analysis.cost_usd = 0.0
        analysis.mode = settings.app_mode
        analysis.error = None
        await session.commit()
        await session.refresh(analysis)
        return analysis
    except AnalyzeError as exc:
        analysis.status = AnalysisStatus.FAILED.value
        analysis.error = exc.message
        analysis.report_json = {
            **(analysis.report_json or {}),
            "status": AnalysisStatus.FAILED.value,
            "error": {"code": exc.code, "message": exc.message, "details": exc.details},
        }
        await session.commit()
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("analyze failed")
        analysis.status = AnalysisStatus.FAILED.value
        analysis.error = str(exc)
        analysis.report_json = {
            **(analysis.report_json or {}),
            "status": AnalysisStatus.FAILED.value,
            "error": {"code": "ANALYZE_FAILED", "message": str(exc), "details": {}},
        }
        await session.commit()
        raise AnalyzeError("ANALYZE_FAILED", str(exc)) from exc


async def create_analysis(
    session: AsyncSession,
    *,
    repo_id: UUID,
    diff_text: str,
    pr_title: str | None,
    settings: Settings | None = None,
) -> Analysis:
    settings = settings or get_settings()
    if len(diff_text.encode("utf-8")) > MAX_DIFF_BYTES:
        raise AnalyzeError("DIFF_TOO_LARGE", "diff exceeds 500KB limit")
    repo = await session.get(Repo, repo_id)
    if repo is None:
        raise AnalyzeError("REPO_NOT_FOUND", f"repo {repo_id} not found")

    diff_hash = diff_cache_key(repo_id, diff_text, settings.app_mode)
    cached = await find_cached_analysis(session, repo_id=repo_id, diff_hash=diff_hash)
    if cached is not None:
        return cached

    analysis = Analysis(
        repo_id=repo_id,
        status=AnalysisStatus.QUEUED.value,
        diff_hash=diff_hash,
        pr_title=pr_title,
        mode=settings.app_mode,
        cost_usd=0.0,
        report_json={"_diff_text": diff_text},
    )
    session.add(analysis)
    await session.commit()
    await session.refresh(analysis)
    return analysis
