from __future__ import annotations

import os
from pathlib import Path

import pytest

# Force CI embeddings for this package's tests unless overridden.
os.environ.setdefault("APP_MODE", "ci")
os.environ.setdefault("EMBEDDING_PROVIDER", "hash")
os.environ.setdefault("EMBEDDING_MODEL", "hash-v1")


@pytest.fixture()
def chroma_tmpdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    chroma = tmp_path / "chroma"
    chroma.mkdir()
    monkeypatch.setenv("CHROMA_PATH", str(chroma))
    monkeypatch.setenv("APP_MODE", "ci")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "hash")
    monkeypatch.setenv("EMBEDDING_MODEL", "hash-v1")
    # reset settings / embedder caches if any
    from blastradius.config import get_settings
    from blastradius.services import embeddings as emb

    get_settings.cache_clear() if hasattr(get_settings, "cache_clear") else None
    emb.get_cached_embedder.cache_clear()
    return chroma


@pytest.fixture()
def sample_root() -> Path:
    return Path(__file__).resolve().parents[1] / "data"


@pytest.fixture(autouse=True)
async def _reset_db_engine():
    from blastradius.db.session import reset_engine

    await reset_engine()
    yield
    await reset_engine()
