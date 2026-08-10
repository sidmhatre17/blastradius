from __future__ import annotations

import re
from dataclasses import dataclass

from unidiff import PatchSet

TEST_RE = re.compile(r"(^|/)tests?/|(^|/)test_|_test\.py$")
CONFIG_RE = re.compile(r"\.(ya?ml|json|env|toml)$")
MIGRATION_RE = re.compile(r"alembic/|migrations/")
DOCS_RE = re.compile(r"README|\.md$", re.IGNORECASE)


@dataclass(frozen=True)
class ChangedFile:
    path: str
    is_added: bool
    is_removed: bool
    is_modified: bool
    is_test: bool
    is_config: bool
    is_migration: bool
    is_docs: bool
    added_lines: int
    removed_lines: int


def normalize_diff_path(path: str) -> str:
    """Strip leading a/ or b/ and normalize separators."""
    cleaned = path.replace("\\", "/")
    if cleaned.startswith("a/") or cleaned.startswith("b/"):
        cleaned = cleaned[2:]
    while cleaned.startswith("./"):
        cleaned = cleaned[2:]
    return cleaned.lstrip("/")


def _flags_for_path(path: str) -> tuple[bool, bool, bool, bool]:
    return (
        bool(TEST_RE.search(path)),
        bool(CONFIG_RE.search(path)),
        bool(MIGRATION_RE.search(path)),
        bool(DOCS_RE.search(path)),
    )


def parse_diff(diff_text: str) -> list[ChangedFile]:
    """Parse a unified diff into ChangedFile rows."""
    if not diff_text or not diff_text.strip():
        return []

    # unidiff expects PatchSet from string; tolerate missing git headers.
    patch = PatchSet(diff_text.splitlines(keepends=True))
    changed: list[ChangedFile] = []
    for file in patch:
        raw_path = file.path
        # Prefer target path for renames/new files; fall back to source.
        if file.is_removed_file:
            raw_path = file.source_file or file.path
        elif file.target_file and file.target_file != "/dev/null":
            raw_path = file.target_file
        elif file.source_file and file.source_file != "/dev/null":
            raw_path = file.source_file
        path = normalize_diff_path(raw_path)
        is_test, is_config, is_migration, is_docs = _flags_for_path(path)
        changed.append(
            ChangedFile(
                path=path,
                is_added=bool(file.is_added_file),
                is_removed=bool(file.is_removed_file),
                is_modified=bool(file.is_modified_file),
                is_test=is_test,
                is_config=is_config,
                is_migration=is_migration,
                is_docs=is_docs,
                added_lines=int(file.added),
                removed_lines=int(file.removed),
            )
        )
    return changed
