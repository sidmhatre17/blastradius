from __future__ import annotations

from pathlib import Path

import pytest

from blastradius.config import Settings
from blastradius.db.session import get_session_factory
from blastradius.services.analyze import create_analysis, run_analysis
from blastradius.services.embeddings import HashEmbedder
from blastradius.services.incident_ingest import ingest_incidents_dir
from blastradius.services.repo_ingest import ingest_repo
from blastradius.services.vector_store import VectorStore


@pytest.mark.asyncio
async def test_analyze_safe_vs_common(chroma_tmpdir: Path, sample_root: Path) -> None:
    settings = Settings(
        app_mode="ci",
        embedding_provider="hash",
        embedding_model="hash-v1",
        llm_provider="template",
        chroma_path=str(chroma_tmpdir),
        sample_root=str(sample_root),
    )
    store = VectorStore(settings=settings, embedder=HashEmbedder(dim=64))
    factory = get_session_factory(settings)

    async with factory() as session:
        repo = await ingest_repo(
            session,
            name="payorbit",
            root=sample_root / "sample_repo",
            vector_store=store,
        )
        await ingest_incidents_dir(
            session,
            sample_root / "sample_incidents",
            vector_store=store,
        )

        safe_diff = (sample_root / "sample_prs" / "pr_safe_docs.diff").read_text()
        common_diff = (sample_root / "sample_prs" / "pr_common_client.diff").read_text()

        a_safe = await create_analysis(
            session,
            repo_id=repo.id,
            diff_text=safe_diff,
            pr_title="docs",
            settings=settings,
        )
        a_safe = await run_analysis(
            session, a_safe.id, settings=settings, vector_store=store
        )
        assert a_safe.status == "completed"
        assert a_safe.risk_tier == "low"
        assert a_safe.report_json is not None
        assert a_safe.report_json["summary"]
        assert len(a_safe.report_json["risk_factors"]) == 6
        assert a_safe.report_json["cost_usd"] == 0.0
        assert a_safe.report_json["mode"] == "ci"

        a_common = await create_analysis(
            session,
            repo_id=repo.id,
            diff_text=common_diff,
            pr_title="http client",
            settings=settings,
        )
        a_common = await run_analysis(
            session, a_common.id, settings=settings, vector_store=store
        )
        assert a_common.status == "completed"
        assert a_common.risk_tier in {"high", "critical"}
        assert a_common.risk_score >= 60
        top = [x["incident_id"] for x in a_common.report_json["similar_incidents"][:3]]
        assert "INC-0991" in top
        assert a_common.risk_score > a_safe.risk_score
