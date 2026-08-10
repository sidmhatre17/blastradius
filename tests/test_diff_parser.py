from pathlib import Path

from blastradius.services.diff_parser import normalize_diff_path, parse_diff

PRS = Path(__file__).resolve().parents[1] / "data" / "sample_prs"


def test_normalize_strips_a_b_prefix() -> None:
    assert normalize_diff_path("a/packages/common/http_client.py") == (
        "packages/common/http_client.py"
    )
    assert normalize_diff_path("b/README.md") == "README.md"


def test_parse_auth_middleware_sample_pr() -> None:
    text = (PRS / "pr_auth_middleware.diff").read_text()
    files = parse_diff(text)
    assert len(files) == 1
    f = files[0]
    assert f.path == "services/api_gateway/auth/middleware.py"
    assert f.is_docs is False
    assert f.is_test is False
    assert f.is_config is False
    assert f.added_lines >= 1
    assert f.removed_lines >= 1


def test_docs_flag_on_safe_docs_pr() -> None:
    text = (PRS / "pr_safe_docs.diff").read_text()
    files = parse_diff(text)
    assert files[0].path == "README.md"
    assert files[0].is_docs is True


def test_parse_common_client_pr() -> None:
    text = (PRS / "pr_common_client.diff").read_text()
    files = parse_diff(text)
    assert files[0].path == "packages/common/http_client.py"
    assert files[0].is_docs is False


def test_config_flag_synthetic() -> None:
    diff = """\
--- a/config/app.yaml
+++ b/config/app.yaml
@@ -1,2 +1,3 @@
 x: 1
 y: 2
+z: 3
"""
    files = parse_diff(diff)
    assert files[0].path == "config/app.yaml"
    assert files[0].is_config is True
