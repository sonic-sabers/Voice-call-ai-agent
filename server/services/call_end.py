"""Post-call webhook handler — logs interaction to Google Sheets."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import Request
from fastapi.responses import JSONResponse

from server.core.auth import verify_vapi_secret
from server.core.constants import SUMMARY_FALLBACK_LENGTH
from server.core.state import call_session, pending_callers
from server.services.sentiment import classify_sentiment
from server.services.sheets import log_interaction
from server.services.summary import generate_summary

log = logging.getLogger(__name__)


def derive_outcome(transcript: str) -> str:
    """Derive call outcome from transcript keywords."""
    t = transcript.lower()
    if "escalat" in t or "representative" in t:
        return "escalated"
    if any(
        p in t
        for p in (
            "unable to verify",
            "wasn't able to locate",
            "not able to locate",
            "auth_fail",
        )
    ):
        return "auth_failed"
    return "resolved"


async def handle_call_end(request: Request, prefetched_body: dict | None = None) -> JSONResponse:
    # Two entry points share this handler:
    #   1. Direct POST to /webhook/call-end — auth check required.
    #   2. Routed from handle_tool_call (end-of-call-report in tool webhook) — body
    #      already parsed + secret already verified, passed as prefetched_body.
    if prefetched_body is None and not verify_vapi_secret(request):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    if prefetched_body is not None:
        body = prefetched_body
    else:
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    msg = body.get("message", {})
    if not isinstance(msg, dict):
        return JSONResponse({"error": "message must be an object"}, status_code=422)

    artifact = msg.get("artifact", {})
    call = msg.get("call", {})

    if not isinstance(artifact, dict) or not isinstance(call, dict):
        return JSONResponse({"error": "Malformed payload"}, status_code=422)

    transcript: str = artifact.get("transcript", "") or ""
    call_id: str = call.get("id") or "unknown"
    session = call_session.get(call_id, {})
    pending = pending_callers.get(call_id, {})
    # customer.number only present for PSTN calls — fall back to phone stored during lookup_caller.
    # customer field may be absent or null on browser/web calls.
    customer = call.get("customer") or {}
    caller_phone: str = (
        (customer.get("number") if isinstance(customer, dict) else None)
        or session.get("phone")
        or pending.get("phone")
        or "unknown"
    )
    caller_name: str = (
        session.get("caller_name")
        or pending.get("caller_name")
        or "Unknown"
    )
    recording_url: str = artifact.get("recordingUrl", "") or ""
    transcript_url: str = artifact.get("transcriptUrl", "") or ""

    sentiment = classify_sentiment(transcript)
    outcome = derive_outcome(transcript)

    # Summary is best-effort — failure degrades to truncated transcript, never blocks logging.
    try:
        summary = generate_summary(transcript)
    except Exception as exc:
        log.warning("generate_summary failed, using truncated transcript: %s", exc)
        summary = transcript[:SUMMARY_FALLBACK_LENGTH].strip() + ("..." if len(transcript) > SUMMARY_FALLBACK_LENGTH else "")

    escalation_reason: str = session.get("escalation_reason", "")

    try:
        log_interaction(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "caller_phone": caller_phone,
                "caller_name": caller_name,
                "call_id": call_id,
                "summary": summary,
                "sentiment": sentiment,
                "outcome": outcome,
                "recording_url": recording_url,
                "transcript_url": transcript_url,
                "escalation_reason": escalation_reason,
            }
        )
    except Exception as exc:
        log.exception("log_interaction failed for call_id=%s: %s", call_id, exc)
        return JSONResponse({"error": "Failed to log interaction"}, status_code=500)

    return JSONResponse({"status": "ok"}, status_code=200)
