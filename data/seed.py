"""Seed demo callers and interactions header to Google Sheets.

Usage:
    python data/seed.py
"""
from __future__ import annotations

import json
import sys

import gspread
from google.oauth2.service_account import Credentials

from server.core.config import get_settings
from server.core.constants import SHEET_TAB_CALLERS, SHEET_TAB_INTERACTIONS

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

CALLERS = [
    ["+1-408-555-0192", "Maya", "Patel", "1987-09-14", "CLM-2847", "approved", "", "POL-100192", "95110"],
    ["+1-312-555-0371", "Carlos", "Rivera", "1992-04-03", "CLM-3105", "requires_documentation", "radiology report and treating physician statement", "POL-100371", "60601"],
    ["+1-714-555-0884", "Amara", "Okonkwo", "1979-11-28", "CLM-4422", "pending", "", "POL-100884", "92801"],
]

CALLERS_HEADER = ["phone", "first_name", "last_name", "dob", "claim_id", "claim_status", "docs_required", "policy_number", "zip_code"]
INTERACTIONS_HEADER = ["timestamp", "caller_phone", "caller_name", "call_id", "summary", "sentiment", "outcome", "recording_url", "transcript_url"]


def main() -> None:
    try:
        cfg = get_settings()
    except EnvironmentError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    creds = Credentials.from_service_account_info(json.loads(cfg.google_credentials_json), scopes=SCOPES)
    gc = gspread.authorize(creds)
    ss = gc.open_by_key(cfg.google_spreadsheet_id)

    # ── callers sheet ──────────────────────────────────────────────────────
    try:
        callers_ws = ss.worksheet(SHEET_TAB_CALLERS)
    except gspread.exceptions.WorksheetNotFound:
        callers_ws = ss.add_worksheet(SHEET_TAB_CALLERS, rows=100, cols=10)

    callers_ws.clear()
    callers_ws.append_row(CALLERS_HEADER)
    for row in CALLERS:
        callers_ws.append_row(row)
    print(f"✓ {SHEET_TAB_CALLERS} sheet seeded with {len(CALLERS)} demo records")

    # ── interactions sheet ─────────────────────────────────────────────────
    try:
        interactions_ws = ss.worksheet(SHEET_TAB_INTERACTIONS)
    except gspread.exceptions.WorksheetNotFound:
        interactions_ws = ss.add_worksheet(SHEET_TAB_INTERACTIONS, rows=1000, cols=10)

    existing = interactions_ws.get_all_values()
    if not existing or existing[0] != INTERACTIONS_HEADER:
        interactions_ws.clear()
        interactions_ws.append_row(INTERACTIONS_HEADER)
        print(f"✓ {SHEET_TAB_INTERACTIONS} sheet header written")
    else:
        print(f"✓ {SHEET_TAB_INTERACTIONS} sheet header already present, skipping")

    print("\nDone. Spreadsheet:", f"https://docs.google.com/spreadsheets/d/{cfg.google_spreadsheet_id}")


if __name__ == "__main__":
    main()
