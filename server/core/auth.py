from __future__ import annotations

from fastapi import Request

from server.core.config import get_settings


def verify_vapi_secret(request: Request) -> bool:
    """Return True if x-vapi-secret header matches VAPI_WEBHOOK_SECRET."""
    import logging
    log = logging.getLogger(__name__)
    secret = get_settings().vapi_webhook_secret
    if not secret:
        return False
    log.info("auth headers: %s", dict(request.headers))
    return request.headers.get("x-vapi-secret") == secret
