"""Shared FastAPI dependencies."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from blastradius.config import Settings, get_settings
from blastradius.db.session import get_session


def settings_dep() -> Settings:
    return get_settings()


async def db_session_dep() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_session():
        yield session
