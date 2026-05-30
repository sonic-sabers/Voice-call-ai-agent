from fastapi import APIRouter, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from server.core.constants import RATE_LIMIT_CALL_END_WEBHOOK, RATE_LIMIT_TOOL_WEBHOOK
from server.services.call_end import handle_call_end
from server.services.tool_dispatch import handle_tool_call

router = APIRouter(tags=["webhooks"])
limiter = Limiter(key_func=get_remote_address)


# Multiple path aliases because VAPI changed its webhook URL convention across
# assistant versions (/tool-calls, /tool_calls, /tool). All route to the same handler.
@router.post("/webhook/tool")
@router.post("/webhook/tool-calls")
@router.post("/webhook/tool_calls")
@limiter.limit(RATE_LIMIT_TOOL_WEBHOOK)
async def webhook_tool(request: Request):  # type: ignore[return]
    return await handle_tool_call(request)


# /end-of-call-report is the VAPI serverUrl convention; /call-end is our own alias.
@router.post("/webhook/call-end")
@router.post("/webhook/end-of-call-report")
@limiter.limit(RATE_LIMIT_CALL_END_WEBHOOK)
async def webhook_call_end(request: Request):  # type: ignore[return]
    return await handle_call_end(request)
