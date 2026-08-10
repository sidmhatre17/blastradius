from enum import StrEnum


class RepoStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"


class EdgeType(StrEnum):
    IMPORTS = "imports"
    SAME_SERVICE = "same_service"


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskTier(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AnalysisStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AppMode(StrEnum):
    LOCAL = "local"
    CI = "ci"
    CLOUD = "cloud"
