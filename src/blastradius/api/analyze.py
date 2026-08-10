from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from blastradius.config import Settings
from blastradius.deps import db_session_dep, settings_dep
from blastradius.domain.enums import AnalysisStatus
from blastradius.services.analyze import AnalyzeError, create_analysis, run_analysis

router = APIRouter(prefix="/api/v1", tags=["analyze"])

SessionDep = Annotated[AsyncSession, Depends(db_session_dep)]
SettingsDep = Annotated[Settings, Depends(settings_dep)]


class AnalyzeRequest(BaseModel):
    repo_id: UUID
    diff_text: str = Field(min_length=1)
    pr_title: str | None = None
    async_mode: bool = Field(default=False, alias="async")

    model_config = {"populate_by_name": True}


def _error(status: int, code: str, message: str, details: dict | None = None) -> HTTPException:
    return HTTPException(
        status_code=status,
        detail={"error": {"code": code, "message": message, "details": details or {}}},
    )


def _redis_settings(redis_url: str) -> RedisSettings:
    # redis://host:port/db
    return RedisSettings.from_dsn(redis_url)


@router.post("/analyze")
async def analyze_post(
    body: AnalyzeRequest,
    session: SessionDep,
    settings: SettingsDep,
) -> dict[str, Any]:
    try:
        analysis = await create_analysis(
            session,
            repo_id=body.repo_id,
            diff_text=body.diff_text,
            pr_title=body.pr_title,
            settings=settings,
        )
    except AnalyzeError as exc:
        status = 404 if exc.code == "REPO_NOT_FOUND" else 400
        raise _error(status, exc.code, exc.message, exc.details) from exc

    # Cache hit already completed
    if analysis.status == AnalysisStatus.COMPLETED.value and analysis.report_json:
        return analysis.report_json

    if body.async_mode:
        try:
            redis = await create_pool(_redis_settings(settings.redis_url))
            await redis.enqueue_job("run_analysis", str(analysis.id))
            await redis.aclose()
        except Exception as exc:  # noqa: BLE001
            raise _error(
                500,
                "ANALYZE_FAILED",
                f"could not enqueue analysis: {exc}",
            ) from exc
        return {
            "analysis_id": str(analysis.id),
            "repo_id": str(analysis.repo_id),
            "status": analysis.status,
        }

    try:
        analysis = await run_analysis(session, analysis.id, settings=settings)
    except AnalyzeError as exc:
        raise _error(400, exc.code, exc.message, exc.details) from exc
    return analysis.report_json or {"analysis_id": str(analysis.id), "status": analysis.status}


@router.get("/analyze/{analysis_id}")
async def analyze_get(analysis_id: UUID, session: SessionDep) -> dict[str, Any]:
    from blastradius.db.models import Analysis

    analysis = await session.get(Analysis, analysis_id)
    if analysis is None:
        raise _error(404, "NOT_FOUND", f"analysis {analysis_id} not found")
    if analysis.status == AnalysisStatus.COMPLETED.value and analysis.report_json:
        return analysis.report_json
    payload: dict[str, Any] = {
        "analysis_id": str(analysis.id),
        "repo_id": str(analysis.repo_id),
        "status": analysis.status,
        "mode": analysis.mode,
    }
    if analysis.error:
        payload["error"] = analysis.error
    if analysis.report_json and analysis.status == AnalysisStatus.FAILED.value:
        payload["report"] = analysis.report_json
    return payload
