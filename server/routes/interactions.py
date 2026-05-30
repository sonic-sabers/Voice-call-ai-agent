from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from server.core.config import get_settings
from server.services.sheets import get_interactions

log = logging.getLogger(__name__)
router = APIRouter(tags=["interactions"])


def _check_dashboard_auth(request: Request) -> bool:
    """Return True if request is authorized to view interactions.

    When DASHBOARD_SECRET is unset the endpoint is open (dev convenience).
    When set, require Authorization: Bearer <secret> or X-Dashboard-Secret header.
    """
    secret = get_settings().dashboard_secret
    if not secret:
        return True
    header_secret = request.headers.get("x-dashboard-secret", "")
    if header_secret == secret:
        return True
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer ") and auth[len("Bearer "):] == secret:
        return True
    return False


@router.get("/api/interactions")
async def interactions(request: Request) -> JSONResponse:
    if not _check_dashboard_auth(request):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    try:
        rows = get_interactions()
        return JSONResponse(rows, status_code=200)
    except Exception as exc:
        log.exception("GET /api/interactions failed: %s", exc)
        return JSONResponse({"error": "Failed to fetch interactions"}, status_code=503)
