from __future__ import annotations

from fastapi import Request

from server.core.config import get_settings


def verify_vapi_secret(request: Request) -> bool:
    """Return True if request carries the correct VAPI_WEBHOOK_SECRET.

    VAPI sends the secret as either:
    - x-vapi-secret: <secret>          (custom header, configured in dashboard)
    - Authorization: Bearer <secret>   (default when no custom header set)
    """
    secret = get_settings().vapi_webhook_secret
    if not secret:
        return False
    if request.headers.get("x-vapi-secret") == secret:
        return True
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer ") and auth[len("Bearer "):] == secret:
        return True
    return False
