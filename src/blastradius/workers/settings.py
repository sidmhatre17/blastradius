from __future__ import annotations

import logging
from uuid import UUID

from arq.connections import RedisSettings

from blastradius.config import get_settings
from blastradius.db.session import get_session_factory, reset_engine
from blastradius.services.analyze import run_analysis as run_analysis_service

logger = logging.getLogger(__name__)


async def run_analysis(ctx: dict, analysis_id: str) -> str:
    """arq job: execute a queued analysis by id."""
    settings = get_settings()
    await reset_engine()
    factory = get_session_factory(settings)
    async with factory() as session:
        analysis = await run_analysis_service(session, UUID(analysis_id), settings=settings)
        logger.info("analysis %s -> %s", analysis_id, analysis.status)
        return analysis.status


class WorkerSettings:
    functions = [run_analysis]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    job_timeout = 300
    max_jobs = 2
