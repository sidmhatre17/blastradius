from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from blastradius.config import Settings
from blastradius.db.models import Repo
from blastradius.deps import db_session_dep, settings_dep
from blastradius.services.embeddings import build_embedder
from blastradius.services.incident_ingest import ingest_incidents_dir, list_incidents
from blastradius.services.repo_ingest import ingest_repo
from blastradius.services.vector_store import VectorStore

router = APIRouter(prefix="/api/v1", tags=["demo"])

SessionDep = Annotated[AsyncSession, Depends(db_session_dep)]
SettingsDep = Annotated[Settings, Depends(settings_dep)]


class DemoSeedResponse(BaseModel):
    repo_id: str
    repo_name: str
    repo_status: str
    incidents_ingested: int
    sample_root: str
    idempotent: bool = True


@router.post("/demo/seed", response_model=DemoSeedResponse)
async def demo_seed(session: SessionDep, settings: SettingsDep) -> DemoSeedResponse:
    """Idempotent seed of PayOrbit sample repo + incidents."""
    sample_root = Path(settings.sample_root).expanduser().resolve()
    repo_path = sample_root / "sample_repo"
    incidents_path = sample_root / "sample_incidents"
    if not repo_path.is_dir() or not incidents_path.is_dir():
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "PATH_NOT_ALLOWED",
                    "message": f"sample data missing under {sample_root}",
                    "details": {},
                }
            },
        )

    store = VectorStore(settings=settings, embedder=build_embedder(settings))

    existing = await session.scalar(
        select(Repo).where(Repo.name == "payorbit").order_by(Repo.created_at.desc()).limit(1)
    )
    if existing is not None and existing.status == "ready":
        repo = existing
    else:
        repo = await ingest_repo(
            session,
            name="payorbit",
            root=repo_path,
            vector_store=store,
        )

    await ingest_incidents_dir(session, incidents_path, vector_store=store)
    all_incidents = await list_incidents(session)
    return DemoSeedResponse(
        repo_id=str(repo.id),
        repo_name=repo.name,
        repo_status=repo.status,
        incidents_ingested=len(all_incidents),
        sample_root=str(sample_root),
        idempotent=True,
    )
