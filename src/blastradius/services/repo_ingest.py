from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from blastradius.db.models import CodeChunk, Edge, FileNode, Repo
from blastradius.domain.enums import EdgeType, RepoStatus
from blastradius.services.code_graph import service_name_for_path
from blastradius.services.import_parser import build_import_edges

logger = logging.getLogger(__name__)

IGNORE_DIR_NAMES = {".git", "venv", ".venv", "node_modules", "__pycache__", ".mypy_cache"}
CHUNK_SIZE = 60
CHUNK_OVERLAP = 10


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def iter_repo_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in IGNORE_DIR_NAMES for part in path.parts):
            continue
        files.append(path)
    return sorted(files)


def chunk_lines(
    text: str,
    size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[tuple[int, int, str]]:
    lines = text.splitlines()
    if not lines:
        return []
    chunks: list[tuple[int, int, str]] = []
    step = max(1, size - overlap)
    start = 0
    while start < len(lines):
        end = min(len(lines), start + size)
        chunk_text = "\n".join(lines[start:end])
        chunks.append((start + 1, end, chunk_text))
        if end >= len(lines):
            break
        start += step
    return chunks


def language_for_path(path: str) -> str | None:
    if path.endswith(".py"):
        return "python"
    if path.endswith((".yaml", ".yml")):
        return "yaml"
    if path.endswith(".md"):
        return "markdown"
    if path.endswith(".json"):
        return "json"
    return None


def load_owners(root: Path) -> dict[str, Any] | None:
    owners_path = root / "SERVICE_OWNERS.yaml"
    if not owners_path.exists():
        return None
    data = yaml.safe_load(owners_path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


def resolve_allowed_path(path: str, sample_root: str, repos_path: str) -> Path:
    """Resolve ingest path; must stay under SAMPLE_ROOT or REPOS_PATH."""
    candidate = Path(path).expanduser().resolve()
    allowed_roots = [
        Path(sample_root).expanduser().resolve(),
        Path(repos_path).expanduser().resolve(),
    ]
    for root in allowed_roots:
        try:
            candidate.relative_to(root)
            if candidate.exists() and candidate.is_dir():
                return candidate
        except ValueError:
            continue
    raise PermissionError(f"path not allowed or missing: {path}")


async def ingest_repo(
    session: AsyncSession,
    *,
    name: str,
    root: Path,
) -> Repo:
    """Walk repo, upsert files/edges/code chunks in Postgres. Chroma deferred to next slice."""
    repo = Repo(
        name=name,
        root_path=str(root),
        status=RepoStatus.PENDING.value,
        owners_json=load_owners(root),
    )
    session.add(repo)
    await session.flush()

    try:
        abs_files = iter_repo_files(root)
        texts: dict[str, str] = {}
        path_to_node: dict[str, FileNode] = {}

        for abs_path in abs_files:
            rel = abs_path.relative_to(root).as_posix()
            try:
                text = abs_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                logger.debug("skip binary/non-utf8 %s", rel)
                continue
            texts[rel] = text
            node = FileNode(
                repo_id=repo.id,
                path=rel,
                language=language_for_path(rel),
                service_name=service_name_for_path(rel),
                is_shared_package=rel.startswith("packages/"),
                content_hash=content_hash(text),
            )
            session.add(node)
            path_to_node[rel] = node

        await session.flush()

        import_edges = build_import_edges(texts)
        for edge in import_edges:
            src = path_to_node.get(edge.src_path)
            dst = path_to_node.get(edge.dst_path)
            if src is None or dst is None:
                continue
            session.add(
                Edge(
                    repo_id=repo.id,
                    src_file_id=src.id,
                    dst_file_id=dst.id,
                    edge_type=EdgeType.IMPORTS.value,
                )
            )

        for rel, text in texts.items():
            if not rel.endswith(".py"):
                continue
            node = path_to_node[rel]
            for start, end, chunk_text in chunk_lines(text):
                session.add(
                    CodeChunk(
                        file_id=node.id,
                        text=chunk_text,
                        start_line=start,
                        end_line=end,
                        vector_id=None,
                    )
                )

        repo.status = RepoStatus.READY.value
        await session.commit()
        await session.refresh(repo)
        return repo
    except Exception:
        repo.status = RepoStatus.FAILED.value
        await session.commit()
        raise


async def get_repo(session: AsyncSession, repo_id) -> Repo | None:
    return await session.get(Repo, repo_id)


async def list_repos(session: AsyncSession) -> list[Repo]:
    result = await session.execute(select(Repo).order_by(Repo.created_at.desc()))
    return list(result.scalars().all())


async def load_import_edge_pairs(session: AsyncSession, repo_id) -> list[tuple[str, str]]:
    src = FileNode.__table__.alias("src")
    dst = FileNode.__table__.alias("dst")
    stmt = (
        select(src.c.path, dst.c.path)
        .select_from(Edge.__table__)
        .join(src, Edge.src_file_id == src.c.id)
        .join(dst, Edge.dst_file_id == dst.c.id)
        .where(Edge.repo_id == repo_id)
        .where(Edge.edge_type == EdgeType.IMPORTS.value)
    )
    result = await session.execute(stmt)
    return [(row[0], row[1]) for row in result.all()]


async def load_path_service_map(session: AsyncSession, repo_id) -> dict[str, str | None]:
    result = await session.execute(
        select(FileNode.path, FileNode.service_name).where(FileNode.repo_id == repo_id)
    )
    return {path: service for path, service in result.all()}


async def delete_repo_children(session: AsyncSession, repo_id) -> None:
    """Helper for re-ingest later; CASCADE handles most deletes via repo delete."""
    await session.execute(delete(Edge).where(Edge.repo_id == repo_id))
