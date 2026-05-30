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


async def handle_call_end(request: Request) -> JSONResponse:
    # VAPI sends no custom headers on serverUrl calls — only reject if wrong secret is present.
    secret_header = request.headers.get("x-vapi-secret")
    if secret_header and not verify_vapi_secret(request):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    msg = body.get("message", {})
    artifact = msg.get("artifact", {})
    call = msg.get("call", {})

    if not isinstance(artifact, dict) or not isinstance(call, dict):
        return JSONResponse({"error": "Malformed payload"}, status_code=422)

    transcript: str = artifact.get("transcript", "") or ""
    call_id: str = call.get("id") or "unknown"
    caller_phone: str = call.get("customer", {}).get("number") or "unknown"
    session = call_session.get(call_id, {})
    caller_name: str = (
        session.get("caller_name")
        or pending_callers.get(call_id, {}).get("caller_name")
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
            }
        )
    except Exception as exc:
        log.exception("log_interaction failed for call_id=%s: %s", call_id, exc)
        return JSONResponse({"error": "Failed to log interaction"}, status_code=500)

    return JSONResponse({"status": "ok"}, status_code=200)
