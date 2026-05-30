"""VAPI tool call dispatcher.

VAPI sends tool calls as message.toolCallList.
Response shape: { "results": [{"toolCallId": "...", "result": "..."}, ...] }

All handlers return a result dict, never raise — exceptions degrade to a safe
VAPI-speakable error string so the call never dies silently.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from server.core.auth import verify_vapi_secret
from server.core.constants import FAQ_FALLBACK, TOOL_ERROR_MESSAGE
from server.core.phone import normalize_phone
from server.core.state import authenticated_calls, call_session, pending_callers, save_state
from server.services.cove import compose_claim_response
from server.services.kb import query_knowledge_base
from server.services.sheets import lookup_caller

log = logging.getLogger(__name__)

_TOOL_ERROR_RESULT = json.dumps(
    {
        "error": "TEMPORARY_ERROR",
        "message": TOOL_ERROR_MESSAGE,
    }
)

_FAQ_FALLBACK = FAQ_FALLBACK

# ── helpers ───────────────────────────────────────────────────────────────────


def _normalize_dob(raw: str) -> str | None:
    """Spoken DOB → YYYY-MM-DD. Returns None if unparseable."""
    if not raw:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw.strip()):
        return raw.strip()
    try:
        from dateutil import parser as dateparser  # lazy import

        dt = dateparser.parse(raw, dayfirst=False)
        return dt.strftime("%Y-%m-%d") if dt else None
    except Exception:
        return None


def _parse_args(tc: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Normalise both VAPI tool-call shapes → (name, args)."""
    name: str = tc.get("name") or tc.get("function", {}).get("name", "")
    args: dict[str, Any] = tc.get("parameters") or {}
    if not args and "function" in tc:
        raw = tc["function"].get("arguments", "{}")
        if isinstance(raw, dict):
            args = raw
        else:
            try:
                args = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                args = {}
    return name, args


def _first_name(full: str) -> str:
    parts = full.strip().split()
    return parts[0] if parts else ""


# ── tool handlers ─────────────────────────────────────────────────────────────


def _handle_lookup_caller(tc_id: str, args: dict[str, Any], call_id: str) -> dict[str, Any]:
    phone = normalize_phone(args.get("phone", ""))
    if not phone:
        return {"toolCallId": tc_id, "result": json.dumps({"found": False, "error": "INVALID_PHONE"})}
    try:
        record = lookup_caller(phone)
    except Exception as exc:
        log.exception("lookup_caller error for %s: %s", phone, exc)
        return {"toolCallId": tc_id, "result": _TOOL_ERROR_RESULT}
    if not record:
        return {"toolCallId": tc_id, "result": json.dumps({"found": False})}
    # Store server-side — never trust LLM-provided name.
    # Return ONLY identity fields — claim data never exposed to LLM pre-auth.
    pending_callers[call_id] = {
        "phone": phone,
        "caller_name": f"{record.first_name} {record.last_name}",
    }
    return {
        "toolCallId": tc_id,
        "result": json.dumps(
            {
                "found": True,
                "firstName": record.first_name,
                "lastName": record.last_name,
                # claimId, claimStatus, docsRequired, dob — intentionally omitted pre-auth
            }
        ),
    }


def _handle_confirm_identity(tc_id: str, args: dict[str, Any], call_id: str) -> dict[str, Any]:
    phone = normalize_phone(args.get("phone", ""))
    if not phone:
        return {
            "toolCallId": tc_id,
            "result": json.dumps({"confirmed": False, "error": "INVALID_PHONE"}),
        }
    pending = pending_callers.get(call_id, {})
    if not pending:
        log.warning("confirm_identity: no pending record for call_id=%s", call_id)
    caller_name = pending.get("caller_name", "Unknown")
    authenticated_calls[call_id] = {"phone": phone}
    call_session[call_id] = {"phone": phone, "caller_name": caller_name}
    save_state()
    return {
        "toolCallId": tc_id,
        "result": json.dumps(
            {
                "confirmed": True,
                "variableValues": {
                    "authenticated": "true",
                    "customer_name": _first_name(caller_name),
                },
            }
        ),
    }


def _handle_verify_identity(tc_id: str, args: dict[str, Any], call_id: str) -> dict[str, Any]:
    phone = normalize_phone(args.get("phone", ""))
    if not phone:
        return {
            "toolCallId": tc_id,
            "result": json.dumps({"verified": False, "error": "INVALID_PHONE"}),
        }
    dob = _normalize_dob(args.get("dob", ""))
    if not dob:
        return {
            "toolCallId": tc_id,
            "result": json.dumps({"verified": False, "error": "INVALID_DOB"}),
        }
    try:
        record = lookup_caller(phone)
    except Exception as exc:
        log.exception("verify_identity lookup error: %s", exc)
        return {"toolCallId": tc_id, "result": _TOOL_ERROR_RESULT}
    verified = record is not None and record.dob == dob
    if verified:
        pending = pending_callers.get(call_id, {})
        caller_name = pending.get("caller_name", "Unknown")
        authenticated_calls[call_id] = {"phone": phone}
        call_session[call_id] = {"phone": phone, "caller_name": caller_name}
        save_state()
        return {
            "toolCallId": tc_id,
            "result": json.dumps(
                {
                    "verified": True,
                    "variableValues": {
                        "authenticated": "true",
                        "customer_name": _first_name(caller_name),
                    },
                }
            ),
        }
    return {"toolCallId": tc_id, "result": json.dumps({"verified": False})}


def _handle_answer_faq(tc_id: str, args: dict[str, Any]) -> dict[str, Any]:
    question = args.get("question", "").strip()
    if not question:
        return {"toolCallId": tc_id, "result": _FAQ_FALLBACK}
    answer = query_knowledge_base(question)
    return {"toolCallId": tc_id, "result": answer or _FAQ_FALLBACK}


def _handle_compose_claim_response(tc_id: str, args: dict[str, Any], call_id: str) -> dict[str, Any]:
    phone = normalize_phone(args.get("phone", ""))
    cid = args.get("callId") or call_id
    if not phone:
        return {
            "toolCallId": tc_id,
            "result": json.dumps(
                {
                    "safeToSpeak": False,
                    "response": "I'm unable to verify the account. A representative will follow up shortly.",
                }
            ),
        }
    try:
        out = compose_claim_response(phone, cid)
    except Exception as exc:
        log.exception("compose_claim_response error: %s", exc)
        return {"toolCallId": tc_id, "result": _TOOL_ERROR_RESULT}
    return {
        "toolCallId": tc_id,
        "result": json.dumps({"safeToSpeak": out.safe_to_speak, "response": out.response}),
    }


# ── dispatcher ────────────────────────────────────────────────────────────────

_CALL_ID_TOOLS = frozenset(
    {"lookup_caller", "confirm_identity", "verify_identity", "compose_claim_response"}
)

_DISPATCH: dict[str, Any] = {
    "lookup_caller": _handle_lookup_caller,
    "confirm_identity": _handle_confirm_identity,
    "verify_identity": _handle_verify_identity,
    "answer_faq": _handle_answer_faq,
    "compose_claim_response": _handle_compose_claim_response,
}


async def handle_tool_call(request: Request) -> JSONResponse:
    if not verify_vapi_secret(request):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    msg = body.get("message", {})
    log.debug("tool webhook body: %s", json.dumps(body)[:500])
    raw_calls: list[dict[str, Any]] = msg.get("toolCallList", [])
    call_id: str = msg.get("call", {}).get("id", "")

    if not isinstance(raw_calls, list):
        return JSONResponse({"error": "toolCallList must be an array"}, status_code=400)

    results: list[dict[str, Any]] = []
    for tc in raw_calls:
        tc_id: str = tc.get("id", "")
        if not tc_id:
            log.warning("Skipping tool call with no id: %s", tc)
            continue
        name, args = _parse_args(tc)
        handler = _DISPATCH.get(name)
        if handler is None:
            log.warning("Unknown tool: %s", name)
            results.append(
                {"toolCallId": tc_id, "result": json.dumps({"error": "UNKNOWN_TOOL", "tool": name})}
            )
            continue
        try:
            if name in _CALL_ID_TOOLS:
                result = handler(tc_id, args, call_id)
            else:
                result = handler(tc_id, args)
        except Exception as exc:
            log.exception("Unhandled exception in tool %s: %s", name, exc)
            result = {"toolCallId": tc_id, "result": _TOOL_ERROR_RESULT}
        results.append(result)

    return JSONResponse({"results": results})
