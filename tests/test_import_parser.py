from pathlib import Path

from blastradius.services.import_parser import build_import_edges, module_to_path


def _load_payorbit() -> dict[str, str]:
    root = Path(__file__).resolve().parents[1] / "data" / "sample_repo"
    files: dict[str, str] = {}
    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        files[rel] = path.read_text(encoding="utf-8")
    return files


def test_module_to_path_packages_common_http_client() -> None:
    files = set(_load_payorbit())
    assert (
        module_to_path("packages.common.http_client", files)
        == "packages/common/http_client.py"
    )


def test_module_to_path_services_auth_validate() -> None:
    files = set(_load_payorbit())
    assert (
        module_to_path("services.auth_service.validate", files)
        == "services/auth_service/validate.py"
    )


def test_http_client_importers_at_least_six() -> None:
    files = _load_payorbit()
    edges = build_import_edges(files)
    importers = sorted(
        {e.src_path for e in edges if e.dst_path == "packages/common/http_client.py"}
    )
    assert len(importers) >= 6, importers
    required = {
        "services/api_gateway/app.py",
        "services/api_gateway/auth/middleware.py",
        "services/api_gateway/routes/billing.py",
        "services/billing_worker/worker.py",
        "services/billing_worker/retry.py",
        "services/notify_service/sender.py",
        "services/auth_service/validate.py",
    }
    assert required.issubset(set(importers))


def test_fan_out_counts_importers_not_imports() -> None:
    edges = [
        ("a.py", "packages/common/http_client.py"),
        ("b.py", "packages/common/http_client.py"),
        ("packages/common/http_client.py", "other.py"),
    ]
    from blastradius.services.code_graph import count_importers

    assert count_importers(edges, "packages/common/http_client.py") == 2
