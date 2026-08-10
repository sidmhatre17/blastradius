from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from blastradius.config import Settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(request: Request) -> dict[str, Any]:
    settings: Settings = request.app.state.settings
    # DB / redis / vector probes fill in once those layers exist.
    return {
        "status": "ok",
        "db": "unchecked",
        "redis": "unchecked",
        "vector": "unchecked",
        "mode": settings.app_mode,
    }
