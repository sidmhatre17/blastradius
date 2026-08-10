from pathlib import Path

from blastradius.services.code_graph import CodeGraph, service_name_for_path
from blastradius.services.import_parser import build_import_edges


def test_service_name_for_path() -> None:
    assert service_name_for_path("services/api_gateway/app.py") == "api_gateway"
    assert service_name_for_path("packages/common/http_client.py") == "common"


def test_blast_radius_includes_importers_for_shared_package() -> None:
    root = Path(__file__).resolve().parents[1] / "data" / "sample_repo"
    files = {
        p.relative_to(root).as_posix(): p.read_text(encoding="utf-8")
        for p in root.rglob("*.py")
    }
    edges = [(e.src_path, e.dst_path) for e in build_import_edges(files)]
    path_map = {
        path: service_name_for_path(path) for path in files
    }
    graph = CodeGraph(edges, path_map)
    blast = graph.expand_blast_radius(
        ["packages/common/http_client.py"],
        depth=2,
        cap=50,
    )
    node_ids = {n["id"] for n in blast.nodes}
    assert "file:packages/common/http_client.py" in node_ids
    assert "svc:common" in node_ids
    # aggressive fan-out should pull importers
    assert "file:services/api_gateway/app.py" in node_ids
    assert "file:services/billing_worker/worker.py" in node_ids
    assert graph.importer_count("packages/common/http_client.py") >= 6


def test_reverse_bfs_prefers_importers() -> None:
    edges = [
        ("gateway.py", "lib.py"),
        ("worker.py", "lib.py"),
        ("lib.py", "leaf.py"),
    ]
    path_map = {p: None for p in ("gateway.py", "worker.py", "lib.py", "leaf.py")}
    graph = CodeGraph(edges, path_map)
    blast = graph.expand_blast_radius(["lib.py"], depth=1, cap=50)
    ids = {n["id"] for n in blast.nodes}
    assert "file:gateway.py" in ids
    assert "file:worker.py" in ids
    # outbound context at depth 0 also includes leaf
    assert "file:leaf.py" in ids
