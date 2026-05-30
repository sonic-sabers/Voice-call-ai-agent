from fastapi import APIRouter, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from server.core.constants import RATE_LIMIT_CALL_END_WEBHOOK, RATE_LIMIT_TOOL_WEBHOOK
from server.services.call_end import handle_call_end
from server.services.tool_dispatch import handle_tool_call

router = APIRouter(tags=["webhooks"])
limiter = Limiter(key_func=get_remote_address)


@router.post("/webhook/tool")
@limiter.limit(RATE_LIMIT_TOOL_WEBHOOK)
async def webhook_tool(request: Request):  # type: ignore[return]
    return await handle_tool_call(request)


@router.post("/webhook/call-end")
@limiter.limit(RATE_LIMIT_CALL_END_WEBHOOK)
async def webhook_call_end(request: Request):  # type: ignore[return]
    return await handle_call_end(request)
