from __future__ import annotations

import hashlib
import math
import re
from abc import ABC, abstractmethod
from functools import lru_cache

import numpy as np

from blastradius.config import Settings, get_settings


class Embedder(ABC):
    provider: str
    model: str
    dim: int

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]


class HashEmbedder(Embedder):
    """Deterministic bag-of-tokens hashing for CI (no model download)."""

    def __init__(self, dim: int = 64) -> None:
        self.provider = "hash"
        self.model = "hash-v1"
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._one(t) for t in texts]

    def _one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        tokens = re.findall(r"[a-zA-Z0-9_./-]+", text.lower())
        if not tokens:
            tokens = ["empty"]
        for tok in tokens:
            digest = hashlib.sha256(tok.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "big") % self.dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


class STEmbedder(Embedder):
    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5") -> None:
        from sentence_transformers import SentenceTransformer

        self.provider = "sentence_transformers"
        self.model = model_name
        self._model = SentenceTransformer(model_name)
        self.dim = int(self._model.get_sentence_embedding_dimension())

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        arr = np.asarray(vectors, dtype=np.float32)
        return arr.tolist()


class OllamaEmbedder(Embedder):
    def __init__(self, base_url: str, model_name: str, dim: int = 768) -> None:
        self.provider = "ollama"
        self.model = model_name
        self.dim = dim
        self.base_url = base_url.rstrip("/")

    def embed(self, texts: list[str]) -> list[list[float]]:
        import httpx

        out: list[list[float]] = []
        with httpx.Client(timeout=30.0) as client:
            for text in texts:
                resp = client.post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": self.model, "prompt": text},
                )
                resp.raise_for_status()
                emb = resp.json()["embedding"]
                out.append(_l2_normalize(emb))
        return out


def _l2_normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def build_embedder(settings: Settings | None = None) -> Embedder:
    settings = settings or get_settings()
    mode = settings.app_mode.lower()
    provider = settings.embedding_provider.lower()
    if mode == "ci" or provider == "hash":
        return HashEmbedder(dim=min(settings.embed_dim, 64) if settings.embed_dim else 64)
    if provider == "ollama":
        return OllamaEmbedder(
            settings.ollama_base_url,
            settings.embedding_model,
            dim=settings.embed_dim,
        )
    return STEmbedder(settings.embedding_model)


@lru_cache(maxsize=4)
def get_cached_embedder(cache_key: str) -> Embedder:
    # cache_key encodes mode|provider|model
    settings = get_settings()
    return build_embedder(settings)


def embedder_cache_key(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    if settings.app_mode.lower() == "ci" or settings.embedding_provider.lower() == "hash":
        return "ci|hash|hash-v1"
    return f"{settings.app_mode}|{settings.embedding_provider}|{settings.embedding_model}"
