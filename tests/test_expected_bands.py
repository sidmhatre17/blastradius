from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from blastradius.config import Settings
from blastradius.db.session import get_session_factory
from blastradius.services.code_graph import CodeGraph, service_name_for_path
from blastradius.services.diff_parser import parse_diff
from blastradius.services.embeddings import HashEmbedder
from blastradius.services.import_parser import build_import_edges
from blastradius.services.incident_ingest import ingest_incidents_dir
from blastradius.services.retrieval import build_query_pack, retrieve_similar_incidents
from blastradius.services.risk_scorer import score_risk
from blastradius.services.vector_store import VectorStore


def _load_owners(sample_root: Path) -> dict:
    return yaml.safe_load((sample_root / "sample_repo" / "SERVICE_OWNERS.yaml").read_text())


def _payorbit_graph(sample_root: Path) -> CodeGraph:
    root = sample_root / "sample_repo"
    files = {
        p.relative_to(root).as_posix(): p.read_text(encoding="utf-8")
        for p in root.rglob("*.py")
    }
    edges = [(e.src_path, e.dst_path) for e in build_import_edges(files)]
    path_map = {path: service_name_for_path(path) for path in files}
    return CodeGraph(edges, path_map)


@pytest.mark.asyncio
async def test_expected_json_score_bands(chroma_tmpdir: Path, sample_root: Path) -> None:
    expected = json.loads((sample_root / "sample_prs" / "expected.json").read_text())
    owners = _load_owners(sample_root)
    graph = _payorbit_graph(sample_root)

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
        await ingest_incidents_dir(
            session,
            sample_root / "sample_incidents",
            vector_store=store,
        )

        for diff_name, rules in expected.items():
            diff_text = (sample_root / "sample_prs" / diff_name).read_text()
            changed = parse_diff(diff_text)
            paths = [c.path for c in changed]
            blast = graph.expand_blast_radius(paths, depth=2, cap=50)
            affected = sorted(
                {
                    n["label"]
                    for n in blast.nodes
                    if n["type"] == "service"
                }
                | {
                    service_name_for_path(p)
                    for p in paths
                    if service_name_for_path(p)
                }
            )
            pack = build_query_pack(
                pr_title=diff_name,
                changed_paths=paths,
                affected_services=affected,
                diff_excerpt=diff_text,
            )
            similar = await retrieve_similar_incidents(
                session,
                store,
                query_pack=pack,
                changed_files=paths,
                affected_services=affected,
                top_k=8,
            )
            importer_counts = {p: graph.importer_count(p) for p in paths}
            result = score_risk(
                changed,
                affected_services=affected,
                importer_counts=importer_counts,
                similar_incidents=similar,
                owners_json=owners,
            )

            if "tier_in" in rules:
                assert result.risk_tier in rules["tier_in"], (
                    diff_name,
                    result.risk_score,
                    result.risk_tier,
                    {f.name: f.value for f in result.risk_factors},
                )
            if "min_score" in rules:
                assert result.risk_score >= rules["min_score"], (diff_name, result.risk_score)
            if "max_score" in rules:
                assert result.risk_score <= rules["max_score"], (diff_name, result.risk_score)
            if "incident_top3" in rules:
                top3 = [s.incident_id for s in similar[:3]]
                for need in rules["incident_top3"]:
                    assert need in top3, (diff_name, top3, need)
