from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

IMPORT_RE = re.compile(r"^(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))", re.MULTILINE)


@dataclass(frozen=True)
class ImportEdge:
    src_path: str
    dst_path: str
    module: str


def extract_import_modules(source: str) -> list[str]:
    modules: list[str] = []
    for match in IMPORT_RE.finditer(source):
        mod = match.group(1) or match.group(2)
        if mod:
            modules.append(mod)
    return modules


def module_to_path(module: str, repo_files: set[str]) -> str | None:
    """Map dotted module to a repo-relative file path using PayOrbit conventions."""
    parts = module.split(".")
    candidates: list[str] = []

    # packages.common.http_client → packages/common/http_client.py
    # services.auth_service.validate → services/auth_service/validate.py
    as_file = "/".join(parts) + ".py"
    candidates.append(as_file)
    # package init: services.api_gateway → services/api_gateway/__init__.py
    candidates.append("/".join(parts) + "/__init__.py")

    for cand in candidates:
        if cand in repo_files:
            return cand
    return None


def resolve_relative_import(
    src_path: str,
    module: str,
    repo_files: set[str],
) -> str | None:
    """Best-effort relative resolution within the same service directory."""
    if module.startswith("packages.") or module.startswith("services."):
        return module_to_path(module, repo_files)

    src = Path(src_path)
    parent = src.parent
    # Treat single-segment / dotted relative-ish names as same-dir or package walks.
    parts = module.split(".")
    candidate = parent.joinpath(*parts).with_suffix(".py").as_posix()
    if candidate in repo_files:
        return candidate
    init_candidate = parent.joinpath(*parts, "__init__.py").as_posix()
    if init_candidate in repo_files:
        return init_candidate
    return None


def parse_imports_for_file(
    src_path: str,
    source: str,
    repo_files: set[str],
) -> list[ImportEdge]:
    edges: list[ImportEdge] = []
    seen: set[tuple[str, str]] = set()
    for module in extract_import_modules(source):
        dst = resolve_relative_import(src_path, module, repo_files)
        if dst is None:
            logger.debug("unresolved import %s in %s", module, src_path)
            continue
        if dst == src_path:
            continue
        key = (src_path, dst)
        if key in seen:
            continue
        seen.add(key)
        edges.append(ImportEdge(src_path=src_path, dst_path=dst, module=module))
    return edges


def build_import_edges(
    files: dict[str, str],
) -> list[ImportEdge]:
    """files: path → source text."""
    repo_files = set(files)
    edges: list[ImportEdge] = []
    for path, source in files.items():
        if not path.endswith(".py"):
            continue
        edges.extend(parse_imports_for_file(path, source, repo_files))
    return edges
