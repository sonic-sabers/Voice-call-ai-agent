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
from server.core.state import _set_with_touch, authenticated_calls, call_session, pending_callers, save_state
from server.services.cove import compose_claim_response
from server.services.kb import query_knowledge_base
from server.services.sheets import lookup_by_name_dob, lookup_by_name_zip, lookup_caller

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
    s = raw.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return s
    # MM-DD only (caller gives just month/day, e.g. "07-23") — return as partial marker
    if re.fullmatch(r"\d{1,2}-\d{2}", s):
        m, d = s.split("-")
        return f"MM-DD:{int(m):02d}-{int(d):02d}"
    try:
        from dateutil import parser as dateparser  # lazy import

        dt = dateparser.parse(s, dayfirst=False)
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
    _set_with_touch(pending_callers, call_id, {
        "phone": phone,
        "caller_name": f"{record.first_name} {record.last_name}",
    })
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
    pending = pending_callers.get(call_id)
    # Require lookup_caller to have run first and the phone to match what was looked up.
    if not pending:
        log.warning("confirm_identity: no pending record for call_id=%s — rejecting", call_id)
        return {
            "toolCallId": tc_id,
            "result": json.dumps({"confirmed": False, "error": "NO_PENDING_LOOKUP"}),
        }
    if pending.get("phone") != phone:
        log.warning(
            "confirm_identity: phone mismatch for call_id=%s pending=%s claimed=%s",
            call_id, pending.get("phone"), phone,
        )
        return {
            "toolCallId": tc_id,
            "result": json.dumps({"confirmed": False, "error": "PHONE_MISMATCH"}),
        }
    caller_name = pending.get("caller_name", "Unknown")
    _set_with_touch(authenticated_calls, call_id, {"phone": phone})
    _set_with_touch(call_session, call_id, {"phone": phone, "caller_name": caller_name})
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
    # Support partial MM-DD match (caller gave only month/day without year)
    if dob and dob.startswith("MM-DD:"):
        partial = dob[len("MM-DD:"):]  # "MM-DD"
        verified = record is not None and record.dob[5:] == partial  # compare MM-DD suffix of YYYY-MM-DD
    else:
        verified = record is not None and record.dob == dob
    if verified:
        pending = pending_callers.get(call_id, {})
        caller_name = pending.get("caller_name", "Unknown")
        _set_with_touch(authenticated_calls, call_id, {"phone": phone})
        _set_with_touch(call_session, call_id, {"phone": phone, "caller_name": caller_name})
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


def _handle_verify_by_name_dob(tc_id: str, args: dict[str, Any], call_id: str) -> dict[str, Any]:
    """Alternate verification when caller phones from unregistered number.

    Looks up by last_name + DOB (full YYYY-MM-DD or partial MM-DD).
    On match, authenticates the call using the registered phone from the record.
    """
    last_name = args.get("lastName", "").strip()
    dob_raw = args.get("dob", "")
    if not last_name:
        return {"toolCallId": tc_id, "result": json.dumps({"verified": False, "error": "MISSING_LAST_NAME"})}
    dob = _normalize_dob(dob_raw)
    if not dob:
        return {"toolCallId": tc_id, "result": json.dumps({"verified": False, "error": "INVALID_DOB"})}

    # Strip partial marker for lookup
    dob_for_lookup = dob[len("MM-DD:"):] if dob.startswith("MM-DD:") else dob
    is_partial = dob.startswith("MM-DD:")

    try:
        record = lookup_by_name_dob(last_name, dob_for_lookup)
    except Exception as exc:
        log.exception("verify_by_name_dob error: %s", exc)
        return {"toolCallId": tc_id, "result": _TOOL_ERROR_RESULT}

    if not record:
        return {"toolCallId": tc_id, "result": json.dumps({"verified": False})}

    caller_name = f"{record.first_name} {record.last_name}"
    _set_with_touch(authenticated_calls, call_id, {"phone": record.phone})
    _set_with_touch(call_session, call_id, {"phone": record.phone, "caller_name": caller_name})
    save_state()
    return {
        "toolCallId": tc_id,
        "result": json.dumps(
            {
                "verified": True,
                "firstName": record.first_name,
                "variableValues": {
                    "authenticated": "true",
                    "customer_name": _first_name(caller_name),
                },
            }
        ),
    }


def _handle_verify_by_name_zip(tc_id: str, args: dict[str, Any], call_id: str) -> dict[str, Any]:
    """First alternate verification step — last name + ZIP code.

    Softer than DOB; used before falling back to DOB when phone not on file.
    On match, authenticates using the registered phone from the record.
    """
    last_name = args.get("lastName", "").strip()
    zip_code = args.get("zipCode", "").strip()
    if not last_name:
        return {"toolCallId": tc_id, "result": json.dumps({"verified": False, "error": "MISSING_LAST_NAME"})}
    if not zip_code:
        return {"toolCallId": tc_id, "result": json.dumps({"verified": False, "error": "MISSING_ZIP"})}
    try:
        record = lookup_by_name_zip(last_name, zip_code)
    except Exception as exc:
        log.exception("verify_by_name_zip error: %s", exc)
        return {"toolCallId": tc_id, "result": _TOOL_ERROR_RESULT}
    if not record:
        return {"toolCallId": tc_id, "result": json.dumps({"verified": False})}
    caller_name = f"{record.first_name} {record.last_name}"
    _set_with_touch(authenticated_calls, call_id, {"phone": record.phone})
    _set_with_touch(call_session, call_id, {"phone": record.phone, "caller_name": caller_name})
    save_state()
    return {
        "toolCallId": tc_id,
        "result": json.dumps(
            {
                "verified": True,
                "firstName": record.first_name,
                "variableValues": {
                    "authenticated": "true",
                    "customer_name": _first_name(caller_name),
                },
            }
        ),
    }


def _handle_escalate(tc_id: str, args: dict[str, Any], call_id: str) -> dict[str, Any]:
    """Log an escalation event server-side and return a structured ack.

    Used for three trigger types:
      - 'representative_requested' — caller asked for a human
      - 'unsupported_question'     — question outside scope (payments, complaints, etc.)
      - 'emergency'               — caller used emergency keywords (911, harm, suicide)

    The actual call transfer is handled by transfer_to_agent (VAPI transferCall).
    This tool exists to tag the call in server state so the end-of-call log
    captures the escalation reason without relying on transcript parsing.
    """
    reason = args.get("reason", "unknown")
    valid_reasons = {"representative_requested", "unsupported_question", "emergency"}
    if reason not in valid_reasons:
        reason = "unknown"
    log.info("escalate: call_id=%s reason=%s", call_id, reason)
    session = call_session.get(call_id, {})
    session["escalation_reason"] = reason
    _set_with_touch(call_session, call_id, session)
    save_state()
    return {
        "toolCallId": tc_id,
        "result": json.dumps({"logged": True, "reason": reason}),
    }


def _handle_answer_faq(tc_id: str, args: dict[str, Any]) -> dict[str, Any]:
    question = args.get("question", "").strip()
    if not question:
        return {"toolCallId": tc_id, "result": _FAQ_FALLBACK}
    answer = query_knowledge_base(question)
    return {"toolCallId": tc_id, "result": answer or _FAQ_FALLBACK}


def _handle_compose_claim_response(tc_id: str, args: dict[str, Any], call_id: str) -> dict[str, Any]:
    phone = normalize_phone(args.get("phone", ""))
    cid = call_id  # always use server-side call_id — LLM-provided callId is unreliable (template vars)
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

# Tools that require the server-side call_id to read/write per-call state.
# Kept separate so stateless tools (answer_faq) never receive a call_id arg.
_CALL_ID_TOOLS = frozenset(
    {
        "lookup_caller", "confirm_identity", "verify_identity",
        "verify_by_name_zip", "verify_by_name_dob",
        "escalate", "compose_claim_response",
    }
)

_DISPATCH: dict[str, Any] = {
    "lookup_caller": _handle_lookup_caller,
    "confirm_identity": _handle_confirm_identity,
    "verify_identity": _handle_verify_identity,
    "verify_by_name_zip": _handle_verify_by_name_zip,
    "verify_by_name_dob": _handle_verify_by_name_dob,
    "escalate": _handle_escalate,
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
    if not isinstance(msg, dict):
        return JSONResponse({"error": "message must be an object"}, status_code=400)
    log.debug("tool webhook body: %s", json.dumps(body)[:500])

    # When VAPI is configured with a single serverUrl (instead of separate toolsUrl /
    # serverUrl), all message types arrive at /webhook/tool. Detect end-of-call
    # reports here and forward them rather than treating them as a tool call.
    if msg.get("type") == "end-of-call-report":
        from server.services.call_end import handle_call_end  # local import avoids circular
        return await handle_call_end(request, prefetched_body=body)

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
