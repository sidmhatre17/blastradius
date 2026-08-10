import math

from blastradius.services.embeddings import HashEmbedder
from blastradius.services.retrieval import overlap_boost


def test_hash_embedder_is_deterministic_and_unit() -> None:
    emb = HashEmbedder(dim=64)
    a = emb.embed_one("packages/common/http_client.py retries")
    b = emb.embed_one("packages/common/http_client.py retries")
    assert a == b
    norm = math.sqrt(sum(x * x for x in a))
    assert abs(norm - 1.0) < 1e-6


def test_overlap_boost_file_and_service() -> None:
    score, why = overlap_boost(
        0.5,
        incident_files=["packages/common/http_client.py"],
        incident_services=["common", "api_gateway"],
        changed_files=["packages/common/http_client.py"],
        affected_services=["api_gateway"],
    )
    assert abs(score - 0.75) < 1e-9  # 0.5 + 0.15 + 0.10
    assert "file_overlap" in why
    assert "service_overlap" in why


def test_overlap_boost_clamps_to_one() -> None:
    score, _ = overlap_boost(
        0.95,
        incident_files=["a.py"],
        incident_services=["svc"],
        changed_files=["a.py"],
        affected_services=["svc"],
    )
    assert score == 1.0
