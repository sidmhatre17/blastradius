from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from blastradius.config import Settings
from blastradius.db.session import check_db

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(request: Request) -> dict[str, Any]:
    settings: Settings = request.app.state.settings
    db_status = await check_db()
    overall = "ok" if db_status == "ok" else "degraded"
    return {
        "status": overall,
        "db": db_status,
        "redis": "unchecked",
        "vector": "unchecked",
        "mode": settings.app_mode,
    }
