"""In-process call state — keyed by VAPI call_id.

Replace authenticated_calls / call_session with Redis for multi-worker production.
"""
from __future__ import annotations

import json
import logging

from server.core.constants import STATE_FILE

log = logging.getLogger(__name__)

# call_id → {phone}
authenticated_calls: dict[str, dict[str, str]] = {}
# call_id → {phone, caller_name}  (pre-auth, from lookup_caller)
pending_callers: dict[str, dict[str, str]] = {}
# call_id → {phone, caller_name}  (post-auth only)
call_session: dict[str, dict[str, str]] = {}

_STATE_FILE = STATE_FILE


def save_state() -> None:
    try:
        with open(_STATE_FILE, "w") as f:
            json.dump(
                {
                    "authenticated": authenticated_calls,
                    "pending": pending_callers,
                    "session": call_session,
                },
                f,
            )
    except Exception as exc:
        log.warning("save_state failed: %s", exc)


def load_state() -> None:
    try:
        with open(_STATE_FILE) as f:
            data = json.load(f)
        authenticated_calls.update(data.get("authenticated", {}))
        pending_callers.update(data.get("pending", {}))
        call_session.update(data.get("session", {}))
    except FileNotFoundError:
        pass
    except Exception as exc:
        log.warning("load_state failed: %s", exc)


load_state()
