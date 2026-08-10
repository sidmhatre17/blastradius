from __future__ import annotations

from pathlib import Path

import pytest

from blastradius.config import Settings
from blastradius.db.session import get_session_factory
from blastradius.services.embeddings import HashEmbedder
from blastradius.services.incident_ingest import ingest_incidents_dir, parse_incident_file
from blastradius.services.retrieval import build_query_pack, retrieve_similar_incidents
from blastradius.services.vector_store import VectorStore


def test_parse_incident_requires_keys(tmp_path: Path) -> None:
    bad = tmp_path / "bad.md"
    bad.write_text("---\nid: X\n---\nbody\n")
    with pytest.raises(ValueError):
        parse_incident_file(bad)


@pytest.mark.asyncio
async def test_incident_ingest_and_gold_recall(chroma_tmpdir: Path, sample_root: Path) -> None:
    settings = Settings(
        app_mode="ci",
        embedding_provider="hash",
        embedding_model="hash-v1",
        chroma_path=str(chroma_tmpdir),
        sample_root=str(sample_root),
    )
    embedder = HashEmbedder(dim=64)
    store = VectorStore(settings=settings, embedder=embedder)

    factory = get_session_factory()
    async with factory() as session:
        incidents = await ingest_incidents_dir(
            session,
            sample_root / "sample_incidents",
            vector_store=store,
            embedder=embedder,
        )
        assert len(incidents) >= 12

        cases = [
            (
                "pr_common_client",
                ["packages/common/http_client.py"],
                ["common", "api_gateway", "billing_worker"],
                "INC-0991",
            ),
            (
                "pr_auth_middleware",
                ["services/api_gateway/auth/middleware.py"],
                ["api_gateway", "auth_service"],
                "INC-1042",
            ),
            (
                "pr_billing_retry",
                ["services/billing_worker/retry.py"],
                ["billing_worker", "notify_service"],
                "INC-0888",
            ),
        ]
        hits_ok = 0
        for name, files, services, expected in cases:
            pack = build_query_pack(
                pr_title=name,
                changed_paths=files,
                affected_services=services,
                diff_excerpt="\n".join(files),
            )
            ranked = await retrieve_similar_incidents(
                session,
                store,
                query_pack=pack,
                changed_files=files,
                affected_services=services,
                top_k=3,
            )
            top_ids = [r.incident_id for r in ranked]
            assert expected in top_ids, (name, top_ids)
            hits_ok += 1
        assert hits_ok == 3
