
import pytest

from blastradius.db.session import get_session_factory
from blastradius.services.code_graph import CodeGraph
from blastradius.services.repo_ingest import (
    ingest_repo,
    load_import_edge_pairs,
    load_path_service_map,
)


@pytest.mark.asyncio
async def test_ingest_payorbit_http_client_importers(chroma_tmpdir, sample_root) -> None:
    from blastradius.config import Settings
    from blastradius.services.embeddings import HashEmbedder
    from blastradius.services.vector_store import VectorStore

    root = sample_root / "sample_repo"
    settings = Settings(
        app_mode="ci",
        embedding_provider="hash",
        embedding_model="hash-v1",
        chroma_path=str(chroma_tmpdir),
        sample_root=str(sample_root),
    )
    store = VectorStore(settings=settings, embedder=HashEmbedder(dim=64))
    factory = get_session_factory()
    async with factory() as session:
        repo = await ingest_repo(session, name="payorbit-test", root=root, vector_store=store)
        assert repo.status == "ready"
        pairs = await load_import_edge_pairs(session, repo.id)
        path_map = await load_path_service_map(session, repo.id)
        graph = CodeGraph(pairs, path_map)
        assert graph.importer_count("packages/common/http_client.py") >= 6
        assert path_map["packages/common/http_client.py"] == "common"
        assert repo.owners_json is not None
        assert "services" in repo.owners_json
