from pathlib import Path

import pytest

from blastradius.db.session import get_session_factory
from blastradius.services.code_graph import CodeGraph
from blastradius.services.repo_ingest import (
    ingest_repo,
    load_import_edge_pairs,
    load_path_service_map,
)


@pytest.mark.asyncio
async def test_ingest_payorbit_http_client_importers() -> None:
    root = Path(__file__).resolve().parents[1] / "data" / "sample_repo"
    factory = get_session_factory()
    async with factory() as session:
        repo = await ingest_repo(session, name="payorbit-test", root=root)
        assert repo.status == "ready"
        pairs = await load_import_edge_pairs(session, repo.id)
        path_map = await load_path_service_map(session, repo.id)
        graph = CodeGraph(pairs, path_map)
        assert graph.importer_count("packages/common/http_client.py") >= 6
        assert path_map["packages/common/http_client.py"] == "common"
        assert repo.owners_json is not None
        assert "services" in repo.owners_json
