from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import chromadb
from chromadb.api.models.Collection import Collection
from chromadb.config import Settings as ChromaSettings

from blastradius.config import Settings, get_settings
from blastradius.services.embeddings import Embedder

logger = logging.getLogger(__name__)

CODE_COLLECTION = "code_chunks"
INCIDENT_COLLECTION = "incident_chunks"


@dataclass
class VectorHit:
    id: str
    score: float
    text: str
    metadata: dict[str, Any]


class VectorStore:
    def __init__(self, settings: Settings | None = None, embedder: Embedder | None = None) -> None:
        from blastradius.services.embeddings import build_embedder

        self.settings = settings or get_settings()
        self.embedder = embedder or build_embedder(self.settings)
        self._client = chromadb.PersistentClient(
            path=self.settings.chroma_path,
            settings=ChromaSettings(anonymized_telemetry=False),
        )

    def _stamp(self) -> dict[str, str]:
        return {
            "embedding_model": self.embedder.model,
            "embedding_provider": self.embedder.provider,
            "created_at": datetime.now(UTC).isoformat(),
        }

    def _get_raw_collection(self, name: str) -> Collection | None:
        try:
            return self._client.get_collection(name=name)
        except Exception:  # noqa: BLE001
            return None

    def ensure_collection(self, name: str) -> Collection:
        """Drop+recreate if missing or embedding stamp mismatches."""
        existing = self._get_raw_collection(name)
        if existing is not None:
            meta = existing.metadata or {}
            if (
                meta.get("embedding_model") == self.embedder.model
                and meta.get("embedding_provider") == self.embedder.provider
            ):
                return existing
            logger.info(
                "chroma collection %s stamp mismatch (have=%s/%s want=%s/%s); dropping",
                name,
                meta.get("embedding_provider"),
                meta.get("embedding_model"),
                self.embedder.provider,
                self.embedder.model,
            )
            self._client.delete_collection(name)
        return self._client.create_collection(
            name=name,
            metadata={**self._stamp(), "hnsw:space": "cosine"},
        )

    def delete_where(self, name: str, where: dict[str, Any]) -> None:
        coll = self._get_raw_collection(name)
        if coll is None:
            return
        try:
            coll.delete(where=where)
        except Exception as exc:  # noqa: BLE001
            logger.debug("chroma delete_where failed: %s", exc)

    def upsert(
        self,
        name: str,
        *,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict[str, Any]],
    ) -> None:
        if not ids:
            return
        coll = self.ensure_collection(name)
        embeddings = self.embedder.embed(documents)
        # chroma metadata values must be scalars
        clean_meta = [_sanitize_metadata(m) for m in metadatas]
        coll.upsert(ids=ids, documents=documents, embeddings=embeddings, metadatas=clean_meta)

    def query(
        self,
        name: str,
        query_text: str,
        *,
        n_results: int = 20,
        where: dict[str, Any] | None = None,
    ) -> list[VectorHit]:
        coll = self._get_raw_collection(name)
        if coll is None:
            return []
        count = coll.count()
        if count == 0:
            return []
        n_results = min(n_results, count)
        qemb = self.embedder.embed([query_text])[0]
        kwargs: dict[str, Any] = {
            "query_embeddings": [qemb],
            "n_results": n_results,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where
        result = coll.query(**kwargs)
        hits: list[VectorHit] = []
        ids = (result.get("ids") or [[]])[0]
        docs = (result.get("documents") or [[]])[0]
        metas = (result.get("metadatas") or [[]])[0]
        dists = (result.get("distances") or [[]])[0]
        for i, doc_id in enumerate(ids):
            dist = float(dists[i]) if dists else 1.0
            # cosine distance → similarity
            score = max(0.0, 1.0 - dist)
            hits.append(
                VectorHit(
                    id=doc_id,
                    score=score,
                    text=docs[i] or "",
                    metadata=dict(metas[i] or {}),
                )
            )
        return hits


def _sanitize_metadata(meta: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in meta.items():
        if v is None:
            continue
        if isinstance(v, (str, int, float, bool)):
            out[k] = v
        else:
            out[k] = str(v)
    return out
