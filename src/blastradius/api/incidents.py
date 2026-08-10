from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from blastradius.config import Settings
from blastradius.deps import db_session_dep, settings_dep
from blastradius.services.embeddings import build_embedder
from blastradius.services.incident_ingest import (
    get_incident_by_business_id,
    ingest_incidents_dir,
    list_incidents,
    resolve_incidents_path,
)
from blastradius.services.vector_store import VectorStore

router = APIRouter(prefix="/api/v1", tags=["incidents"])

SessionDep = Annotated[AsyncSession, Depends(db_session_dep)]
SettingsDep = Annotated[Settings, Depends(settings_dep)]


class IngestIncidentsRequest(BaseModel):
    path: str = Field(min_length=1)


class IncidentOut(BaseModel):
    id: UUID
    incident_id: str
    title: str
    severity: str
    services_json: list[Any] | None = None
    files_json: list[Any] | None = None

    model_config = {"from_attributes": True}


def _error(status: int, code: str, message: str, details: dict | None = None) -> HTTPException:
    return HTTPException(
        status_code=status,
        detail={"error": {"code": code, "message": message, "details": details or {}}},
    )


@router.post("/incidents/ingest", response_model=list[IncidentOut])
async def incidents_ingest(
    body: IngestIncidentsRequest,
    session: SessionDep,
    settings: SettingsDep,
) -> list[IncidentOut]:
    try:
        root = resolve_incidents_path(body.path, settings.sample_root, settings.repos_path)
    except PermissionError as exc:
        raise _error(400, "PATH_NOT_ALLOWED", str(exc)) from exc
    store = VectorStore(embedder=build_embedder(settings))
    incidents = await ingest_incidents_dir(session, root, vector_store=store)
    return [IncidentOut.model_validate(i) for i in incidents]


@router.get("/incidents", response_model=list[IncidentOut])
async def incidents_list(session: SessionDep) -> list[IncidentOut]:
    rows = await list_incidents(session)
    return [IncidentOut.model_validate(r) for r in rows]


@router.get("/incidents/{incident_id}", response_model=IncidentOut)
async def incidents_get(incident_id: str, session: SessionDep) -> IncidentOut:
    row = await get_incident_by_business_id(session, incident_id)
    if row is None:
        raise _error(404, "NOT_FOUND", f"incident {incident_id} not found")
    return IncidentOut.model_validate(row)
