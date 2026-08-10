from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from blastradius.config import Settings
from blastradius.main import create_app


@pytest.mark.asyncio
async def test_demo_seed_idempotent(chroma_tmpdir: Path, sample_root: Path, monkeypatch) -> None:
    monkeypatch.setenv("CHROMA_PATH", str(chroma_tmpdir))
    monkeypatch.setenv("SAMPLE_ROOT", str(sample_root))
    monkeypatch.setenv("APP_MODE", "ci")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "hash")
    monkeypatch.setenv("LLM_PROVIDER", "template")

    # Rebuild settings-bound app with env
    settings = Settings(
        app_mode="ci",
        embedding_provider="hash",
        embedding_model="hash-v1",
        llm_provider="template",
        chroma_path=str(chroma_tmpdir),
        sample_root=str(sample_root),
    )
    app = create_app()
    app.state.settings = settings
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r1 = await client.post("/api/v1/demo/seed")
        assert r1.status_code == 200, r1.text
        body1 = r1.json()
        assert body1["repo_status"] == "ready"
        assert body1["incidents_ingested"] >= 12

        r2 = await client.post("/api/v1/demo/seed")
        assert r2.status_code == 200, r2.text
        body2 = r2.json()
        assert body2["repo_id"] == body1["repo_id"]
        assert body2["incidents_ingested"] >= 12
