"""Google Sheets integration — caller lookup (read) + interaction log (write)."""
from __future__ import annotations

import json
import logging
import random
import re
import threading
import time
from functools import lru_cache
from typing import Any

import gspread
from google.oauth2.service_account import Credentials

from server.core.config import get_settings
from server.core.constants import (
    CALLER_CACHE_MAXSIZE,
    INTERACTIONS_CACHE_TTL,
    SHEETS_BASE_DELAY,
    SHEETS_MAX_RETRIES,
    SHEET_TAB_CALLERS,
    SHEET_TAB_INTERACTIONS,
)
from server.models.caller import CallerRecord

log = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
_MAX_RETRIES = SHEETS_MAX_RETRIES
_BASE_DELAY = SHEETS_BASE_DELAY

# ── Persistent client singleton ───────────────────────────────────────────────
_client_lock = threading.Lock()
_client: gspread.Client | None = None


def _normalize_phone(phone: str) -> str:
    """Normalize phone to +<digits> for robust matching."""
    digits = "".join(ch for ch in str(phone or "") if ch.isdigit())
    if not digits:
        return ""
    if len(digits) == 10:
        digits = f"1{digits}"
    return f"+{digits}"


def _get_client() -> gspread.Client:
    global _client
    with _client_lock:
        if _client is not None:
            return _client
        raw = get_settings().google_credentials_json
        if not raw:
            raise EnvironmentError("GOOGLE_CREDENTIALS_JSON not set")
        try:
            creds_dict = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise EnvironmentError("GOOGLE_CREDENTIALS_JSON is not valid JSON") from exc
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        _client = gspread.authorize(creds)
        return _client


def _open_sheet(client: gspread.Client, tab: str) -> gspread.Worksheet:
    sid = get_settings().google_spreadsheet_id
    if not sid:
        raise EnvironmentError("GOOGLE_SPREADSHEET_ID not set")
    return client.open_by_key(sid).worksheet(tab)


def _backoff(attempt: int) -> None:
    cap = _BASE_DELAY * (2**attempt)
    time.sleep(random.uniform(0, cap))


def _with_retry(fn, label: str):
    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            return fn()
        except (gspread.exceptions.APIError, gspread.exceptions.GSpreadException) as exc:
            last_exc = exc
            log.warning("%s attempt %d failed: %s", label, attempt + 1, exc)
            # Service-account tokens can expire mid-process; dropping _client forces
            # _get_client() to re-authorize on the next attempt rather than reusing
            # a stale credential object.
            if hasattr(exc, "response") and getattr(exc.response, "status_code", 0) in (401, 403):
                global _client
                with _client_lock:
                    _client = None
            if attempt < _MAX_RETRIES - 1:
                _backoff(attempt)
    raise RuntimeError(f"{label} failed after {_MAX_RETRIES} attempts") from last_exc


# ── Caller lookup (LRU-cached per process) ────────────────────────────────────

@lru_cache(maxsize=CALLER_CACHE_MAXSIZE)
def lookup_caller(phone: str) -> CallerRecord | None:
    """Look up caller by E.164 phone from 'callers' sheet. LRU-cached per process."""
    normalized_phone = _normalize_phone(phone)
    if not normalized_phone:
        return None

    def _fetch():
        rows: list[list[Any]] = _open_sheet(_get_client(), SHEET_TAB_CALLERS).get_all_values()
        for row in rows[1:]:
            if len(row) < 7:
                continue
            if _normalize_phone(row[0]) == normalized_phone:
                return CallerRecord(
                    phone=row[0],
                    first_name=row[1],
                    last_name=row[2],
                    dob=row[3],
                    claim_id=row[4],
                    claim_status=row[5],
                    docs_required=row[6],
                    policy_number=row[7] if len(row) > 7 else "",
                    zip_code=row[8] if len(row) > 8 else "",
                )
        return None

    return _with_retry(_fetch, "lookup_caller")


def lookup_by_name_dob(last_name: str, dob_partial: str) -> CallerRecord | None:
    """Look up caller by last_name + DOB (YYYY-MM-DD or MM-DD suffix).

    Used when caller phones from an unregistered number. Never LRU-cached —
    name+DOB combos are not unique enough to cache safely.
    """
    last_name_norm = last_name.strip().lower()
    # Accept full YYYY-MM-DD or partial MM-DD
    is_partial = not re.fullmatch(r"\d{4}-\d{2}-\d{2}", dob_partial)
    mm_dd = dob_partial[-5:] if is_partial else dob_partial[5:]  # MM-DD portion

    def _fetch():
        rows: list[list[Any]] = _open_sheet(_get_client(), SHEET_TAB_CALLERS).get_all_values()
        for row in rows[1:]:
            if len(row) < 7:
                continue
            if row[2].strip().lower() != last_name_norm:
                continue
            stored_dob: str = row[3]  # YYYY-MM-DD
            if is_partial:
                match = stored_dob[5:] == mm_dd
            else:
                match = stored_dob == dob_partial
            if match:
                return CallerRecord(
                    phone=_normalize_phone(row[0]),
                    first_name=row[1],
                    last_name=row[2],
                    dob=row[3],
                    claim_id=row[4],
                    claim_status=row[5],
                    docs_required=row[6],
                    policy_number=row[7] if len(row) > 7 else "",
                    zip_code=row[8] if len(row) > 8 else "",
                )
        return None

    return _with_retry(_fetch, "lookup_by_name_dob")


def lookup_by_name_zip(last_name: str, zip_code: str) -> CallerRecord | None:
    """Look up caller by last_name + ZIP code.

    First fallback when caller phones from unregistered number (softer check
    than DOB — caller may not recall exact DOB but usually knows their ZIP).
    Not LRU-cached.
    """
    last_name_norm = last_name.strip().lower()
    zip_norm = re.sub(r"\D", "", zip_code)[:5]
    if not zip_norm:
        return None

    def _fetch():
        rows: list[list[Any]] = _open_sheet(_get_client(), SHEET_TAB_CALLERS).get_all_values()
        for row in rows[1:]:
            if len(row) < 9:
                continue
            if row[2].strip().lower() != last_name_norm:
                continue
            if re.sub(r"\D", "", row[8])[:5] == zip_norm:
                return CallerRecord(
                    phone=_normalize_phone(row[0]),
                    first_name=row[1],
                    last_name=row[2],
                    dob=row[3],
                    claim_id=row[4],
                    claim_status=row[5],
                    docs_required=row[6],
                    policy_number=row[7] if len(row) > 7 else "",
                    zip_code=row[8],
                )
        return None

    return _with_retry(_fetch, "lookup_by_name_zip")


# ── Interaction log (write) ───────────────────────────────────────────────────

def log_interaction(entry: dict[str, str]) -> None:
    """Append one row to the 'interactions' sheet and invalidate cache."""
    required = {"timestamp", "caller_phone", "caller_name", "call_id", "summary", "sentiment", "outcome"}
    missing = required - entry.keys()
    if missing:
        raise ValueError(f"log_interaction missing fields: {missing}")

    row = [
        entry["timestamp"],
        entry["caller_phone"],
        entry["caller_name"],
        entry["call_id"],
        entry["summary"],
        entry["sentiment"],
        entry["outcome"],
        entry.get("recording_url", ""),
        entry.get("transcript_url", ""),
        entry.get("escalation_reason", ""),
    ]

    def _write():
        _open_sheet(_get_client(), SHEET_TAB_INTERACTIONS).append_row(row)

    _with_retry(_write, "log_interaction")
    _invalidate_interactions_cache()


# ── Interactions read cache (TTL) ─────────────────────────────────────────────

_interactions_lock = threading.Lock()
_interactions_cache: list[dict[str, Any]] = []
_interactions_ts: float = 0.0


def _invalidate_interactions_cache() -> None:
    global _interactions_ts
    with _interactions_lock:
        _interactions_ts = 0.0


def get_interactions() -> list[dict[str, Any]]:
    """Return all rows from 'interactions' sheet, cached for INTERACTIONS_CACHE_TTL seconds."""
    global _interactions_cache, _interactions_ts

    # First lock: check staleness only — release before the network call so
    # other threads aren't blocked while we wait for Sheets.
    with _interactions_lock:
        if time.monotonic() - _interactions_ts < INTERACTIONS_CACHE_TTL:
            return list(_interactions_cache)

    def _fetch():
        return _open_sheet(_get_client(), SHEET_TAB_INTERACTIONS).get_all_records()

    fresh = _with_retry(_fetch, "get_interactions")

    # Second lock: write fresh data back; concurrent fetchers may have also
    # fetched by now — last writer wins, which is fine for a read-only cache.
    with _interactions_lock:
        _interactions_cache = fresh
        _interactions_ts = time.monotonic()

    return list(fresh)
