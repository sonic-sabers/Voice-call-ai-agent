from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from server.core.logging_config import configure_logging
from server.core.middleware import RequestIDMiddleware
from server.routes.health import router as health_router
from server.routes.interactions import router as interactions_router
from server.routes.webhooks import router as webhooks_router

configure_logging()
log = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Observe Insurance VoiceAI", version="1.0.0")

# ── middleware (outermost first) ───────────────────────────────────────────────
app.add_middleware(RequestIDMiddleware)

# ── rate limiting ──────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ── global exception handler ───────────────────────────────────────────────────
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    req_id = getattr(request.state, "request_id", "unknown")
    log.exception(
        "Unhandled exception",
        extra={
            "request_id": req_id,
            "method": request.method,
            "path": request.url.path,
            "error": str(exc),
        },
    )
    return JSONResponse(
        {"error": "Internal server error", "request_id": req_id},
        status_code=500,
    )


# ── routers ────────────────────────────────────────────────────────────────────
app.include_router(health_router)
app.include_router(interactions_router)
app.include_router(webhooks_router)

# ── static client dashboard ────────────────────────────────────────────────────
# Served at http://localhost:3000/client/
app.mount("/client", StaticFiles(directory="client", html=True), name="client")
