from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from server.services.sheets import get_interactions

log = logging.getLogger(__name__)
router = APIRouter(tags=["interactions"])


@router.get("/api/interactions")
async def interactions() -> JSONResponse:
    try:
        rows = get_interactions()
        return JSONResponse(rows, status_code=200)
    except Exception as exc:
        log.exception("GET /api/interactions failed: %s", exc)
        return JSONResponse({"error": "Failed to fetch interactions"}, status_code=503)
