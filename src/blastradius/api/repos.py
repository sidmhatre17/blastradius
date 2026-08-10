from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from blastradius.config import Settings
from blastradius.deps import db_session_dep, settings_dep
from blastradius.services.code_graph import CodeGraph
from blastradius.services.repo_ingest import (
    get_repo,
    ingest_repo,
    list_repos,
    load_import_edge_pairs,
    load_path_service_map,
    resolve_allowed_path,
)

router = APIRouter(prefix="/api/v1", tags=["repos"])

SessionDep = Annotated[AsyncSession, Depends(db_session_dep)]
SettingsDep = Annotated[Settings, Depends(settings_dep)]


class IngestRepoRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    path: str = Field(min_length=1)


class RepoOut(BaseModel):
    id: UUID
    name: str
    root_path: str
    status: str
    owners_json: dict[str, Any] | None = None

    model_config = {"from_attributes": True}


def _error(status: int, code: str, message: str, details: dict | None = None) -> HTTPException:
    return HTTPException(
        status_code=status,
        detail={"error": {"code": code, "message": message, "details": details or {}}},
    )


@router.post("/repos/ingest", response_model=RepoOut)
async def repos_ingest(
    body: IngestRepoRequest,
    session: SessionDep,
    settings: SettingsDep,
) -> RepoOut:
    try:
        root = resolve_allowed_path(body.path, settings.sample_root, settings.repos_path)
    except PermissionError as exc:
        raise _error(400, "PATH_NOT_ALLOWED", str(exc)) from exc
    repo = await ingest_repo(session, name=body.name, root=root)
    return RepoOut.model_validate(repo)


@router.get("/repos", response_model=list[RepoOut])
async def repos_list(session: SessionDep) -> list[RepoOut]:
    repos = await list_repos(session)
    return [RepoOut.model_validate(r) for r in repos]


@router.get("/repos/{repo_id}", response_model=RepoOut)
async def repos_get(repo_id: UUID, session: SessionDep) -> RepoOut:
    repo = await get_repo(session, repo_id)
    if repo is None:
        raise _error(404, "REPO_NOT_FOUND", f"repo {repo_id} not found")
    return RepoOut.model_validate(repo)


@router.get("/repos/{repo_id}/graph")
async def repos_graph(
    repo_id: UUID,
    session: SessionDep,
    depth: Annotated[int, Query(ge=0, le=5)] = 2,
    seed: Annotated[list[str] | None, Query()] = None,
) -> dict[str, Any]:
    repo = await get_repo(session, repo_id)
    if repo is None:
        raise _error(404, "REPO_NOT_FOUND", f"repo {repo_id} not found")
    pairs = await load_import_edge_pairs(session, repo_id)
    path_map = await load_path_service_map(session, repo_id)
    graph = CodeGraph(pairs, path_map)
    seeds = seed or sorted(path_map.keys())[:5]
    blast = graph.expand_blast_radius(seeds, depth=depth, cap=50)
    return {
        "repo_id": str(repo_id),
        "depth": depth,
        "seeds": seeds,
        "nodes": blast.nodes,
        "edges": blast.edges,
        "http_client_importers": graph.importer_count("packages/common/http_client.py"),
    }
