"""Shared FastAPI dependencies (DB/redis/vector wired in later slices)."""

from blastradius.config import Settings, get_settings


def settings_dep() -> Settings:
    return get_settings()
