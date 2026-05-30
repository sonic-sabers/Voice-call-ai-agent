"""In-process call state — keyed by VAPI call_id.

Single-worker only. For multi-worker / Render auto-scaling, replace with Redis
using SETEX TTLs (see TODO comments below).
"""
from __future__ import annotations

import json
import logging
import time

from server.core.constants import STATE_FILE

log = logging.getLogger(__name__)

# Entries older than this are evicted on save/load to prevent unbounded growth.
# VAPI calls are always < 1 hour; 4 h gives generous headroom.
_STATE_TTL_SECONDS = 4 * 3600

# call_id → {phone}
authenticated_calls: dict[str, dict[str, str]] = {}
# call_id → {phone, caller_name}  (pre-auth, from lookup_caller)
pending_callers: dict[str, dict[str, str]] = {}
# call_id → {phone, caller_name}  (post-auth only)
call_session: dict[str, dict[str, str]] = {}
# call_id → unix timestamp of last write (not persisted; reset on restart is fine)
_call_ts: dict[str, float] = {}

_STATE_FILE = STATE_FILE


def _touch(call_id: str) -> None:
    _call_ts[call_id] = time.time()


def _evict_expired() -> None:
    cutoff = time.time() - _STATE_TTL_SECONDS
    expired = [cid for cid, ts in _call_ts.items() if ts < cutoff]
    for cid in expired:
        authenticated_calls.pop(cid, None)
        pending_callers.pop(cid, None)
        call_session.pop(cid, None)
        _call_ts.pop(cid, None)
    if expired:
        log.debug("Evicted %d expired call state entries", len(expired))


def save_state() -> None:
    _evict_expired()
    try:
        with open(_STATE_FILE, "w") as f:
            json.dump(
                {
                    "authenticated": authenticated_calls,
                    "pending": pending_callers,
                    "session": call_session,
                    "ts": _call_ts,
                },
                f,
            )
    except Exception as exc:
        log.warning("save_state failed: %s", exc)


def _set_with_touch(store: dict, call_id: str, value: dict) -> None:
    store[call_id] = value
    _touch(call_id)


def load_state() -> None:
    try:
        with open(_STATE_FILE) as f:
            data = json.load(f)
        authenticated_calls.update(data.get("authenticated", {}))
        pending_callers.update(data.get("pending", {}))
        call_session.update(data.get("session", {}))
        _call_ts.update({k: float(v) for k, v in data.get("ts", {}).items()})
        _evict_expired()
    except FileNotFoundError:
        pass
    except Exception as exc:
        log.warning("load_state failed: %s", exc)


load_state()
