from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import frontmatter
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from blastradius.db.models import Incident, IncidentChunk
from blastradius.services.embeddings import Embedder, build_embedder
from blastradius.services.repo_ingest import resolve_allowed_path
from blastradius.services.vector_store import INCIDENT_COLLECTION, VectorStore

logger = logging.getLogger(__name__)

REQUIRED_KEYS = {"id", "date", "services", "files", "severity"}
CHUNK_CHARS = 500
CHUNK_OVERLAP = 80


def chunk_text(text: str, size: int = CHUNK_CHARS, overlap: int = CHUNK_OVERLAP) -> list[str]:
    body = text.strip()
    if not body:
        return []
    if len(body) <= size:
        return [body]
    chunks: list[str] = []
    step = max(1, size - overlap)
    start = 0
    while start < len(body):
        end = min(len(body), start + size)
        chunks.append(body[start:end])
        if end >= len(body):
            break
        start += step
    return chunks


def parse_incident_file(path: Path) -> dict[str, Any]:
    post = frontmatter.load(path)
    meta = dict(post.metadata)
    missing = REQUIRED_KEYS - set(meta)
    if missing:
        raise ValueError(f"{path.name}: missing frontmatter keys {sorted(missing)}")
    title = meta.get("title")
    if not title:
        for line in str(post.content).splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                break
        title = title or str(meta["id"])
    return {
        "incident_id": str(meta["id"]),
        "title": str(title),
        "severity": str(meta["severity"]),
        "services": list(meta.get("services") or []),
        "files": list(meta.get("files") or []),
        "body": str(post.content).strip(),
        "date": str(meta.get("date")),
    }


async def ingest_incidents_dir(
    session: AsyncSession,
    directory: Path,
    *,
    vector_store: VectorStore | None = None,
    embedder: Embedder | None = None,
) -> list[Incident]:
    store = vector_store or VectorStore(embedder=embedder or build_embedder())
    store.ensure_collection(INCIDENT_COLLECTION)

    paths = sorted(directory.glob("*.md"))
    if not paths:
        raise FileNotFoundError(f"no incident markdown files in {directory}")

    ingested: list[Incident] = []
    for path in paths:
        parsed = parse_incident_file(path)
        incident = await _upsert_incident(session, store, parsed)
        ingested.append(incident)
    await session.commit()
    return ingested


async def _upsert_incident(
    session: AsyncSession,
    store: VectorStore,
    parsed: dict[str, Any],
) -> Incident:
    incident_id = parsed["incident_id"]
    existing = await session.scalar(
        select(Incident)
        .where(Incident.incident_id == incident_id)
        .options(selectinload(Incident.chunks))
    )
    if existing is not None:
        store.delete_where(INCIDENT_COLLECTION, {"incident_id": incident_id})
        await session.delete(existing)
        await session.flush()

    incident = Incident(
        incident_id=incident_id,
        title=parsed["title"],
        severity=parsed["severity"],
        services_json=parsed["services"],
        files_json=parsed["files"],
        body=parsed["body"],
    )
    session.add(incident)
    await session.flush()

    hint = (
        f"incident {incident_id}\n"
        f"files: {', '.join(parsed['files'])}\n"
        f"services: {', '.join(parsed['services'])}\n"
        f"title: {parsed['title']}\n\n"
    )
    parts = chunk_text(parsed["body"]) or [parsed["body"] or incident_id]
    pending: list[tuple[IncidentChunk, int, str]] = []
    for ordinal, part in enumerate(parts):
        chunk = IncidentChunk(incident_id=incident.id, text=part, ordinal=ordinal)
        session.add(chunk)
        pending.append((chunk, ordinal, part))
    await session.flush()

    ids: list[str] = []
    docs: list[str] = []
    metas: list[dict[str, Any]] = []
    for chunk, ordinal, part in pending:
        vector_id = str(chunk.id)
        chunk.vector_id = vector_id
        ids.append(vector_id)
        docs.append(hint + part)
        metas.append(
            {
                "incident_id": incident_id,
                "incident_pk": str(incident.id),
                "chunk_id": vector_id,
                "ordinal": ordinal,
                "severity": incident.severity,
                "title": incident.title,
            }
        )
    store.upsert(INCIDENT_COLLECTION, ids=ids, documents=docs, metadatas=metas)
    return incident


async def list_incidents(session: AsyncSession) -> list[Incident]:
    result = await session.execute(select(Incident).order_by(Incident.incident_id))
    return list(result.scalars().all())


async def get_incident_by_business_id(session: AsyncSession, incident_id: str) -> Incident | None:
    return await session.scalar(select(Incident).where(Incident.incident_id == incident_id))


async def delete_all_incidents(session: AsyncSession, store: VectorStore | None = None) -> None:
    if store is not None:
        coll = store._get_raw_collection(INCIDENT_COLLECTION)
        if coll is not None:
            store._client.delete_collection(INCIDENT_COLLECTION)
    await session.execute(delete(Incident))
    await session.commit()


def resolve_incidents_path(path: str, sample_root: str, repos_path: str) -> Path:
    return resolve_allowed_path(path, sample_root, repos_path)
