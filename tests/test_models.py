from blastradius.db.base import Base
from blastradius.db.models import Analysis, CodeChunk, Edge, FileNode, Incident
from blastradius.domain.enums import AnalysisStatus, EdgeType, RepoStatus


def test_metadata_includes_core_tables() -> None:
    tables = set(Base.metadata.tables)
    assert {
        "repos",
        "file_nodes",
        "edges",
        "incidents",
        "incident_chunks",
        "code_chunks",
        "analyses",
    } <= tables


def test_repo_delete_cascades_declared() -> None:
    repo_fk = next(iter(FileNode.__table__.c.repo_id.foreign_keys))
    assert repo_fk.ondelete == "CASCADE"

    edge_fk = next(iter(Edge.__table__.c.repo_id.foreign_keys))
    assert edge_fk.ondelete == "CASCADE"

    analysis_fk = next(iter(Analysis.__table__.c.repo_id.foreign_keys))
    assert analysis_fk.ondelete == "CASCADE"

    chunk_fk = next(iter(CodeChunk.__table__.c.file_id.foreign_keys))
    assert chunk_fk.ondelete == "CASCADE"


def test_incidents_have_no_repo_fk() -> None:
    assert "repo_id" not in Incident.__table__.c


def test_enum_defaults() -> None:
    assert RepoStatus.PENDING.value == "pending"
    assert EdgeType.IMPORTS.value == "imports"
    assert AnalysisStatus.QUEUED.value == "queued"
