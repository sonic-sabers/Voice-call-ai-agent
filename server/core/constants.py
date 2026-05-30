"""Single source of truth for all server-side constants.

Brand URLs, sheet/table names, retry config, rate limits, model names.
"""
from __future__ import annotations

# ── Brand / copy ──────────────────────────────────────────────────────────────
BRAND_NAME = "Observe Insurance"
AGENT_NAME = "Aria"
PORTAL_URL = "observeinsurance.com/portal"
SUPPORT_EMAIL = "support@observeinsurance.com"
CLAIM_PROCESSING_DAYS = "5 to 7 business days"
CALLBACK_SLA = "one business day"

# ── Google Sheets tab names ───────────────────────────────────────────────────
SHEET_TAB_CALLERS = "callers"
SHEET_TAB_INTERACTIONS = "interactions"

# ── Airtable table name ───────────────────────────────────────────────────────
AIRTABLE_TABLE_FAQ = "tblOJTpVWsZCBmmli"

# ── Retry / backoff ───────────────────────────────────────────────────────────
SHEETS_MAX_RETRIES = 3
SHEETS_BASE_DELAY = 1.0   # seconds

AIRTABLE_MAX_RETRIES = 3
AIRTABLE_BASE_DELAY = 0.5  # seconds

# ── LRU cache sizes ───────────────────────────────────────────────────────────
CALLER_CACHE_MAXSIZE = 64

# ── Interactions cache ────────────────────────────────────────────────────────
INTERACTIONS_CACHE_TTL = 20   # seconds; dashboard polls every 30s

# ── State persistence ─────────────────────────────────────────────────────────
STATE_FILE = "/tmp/call_state.json"

# ── Rate limits (slowapi format) ──────────────────────────────────────────────
RATE_LIMIT_TOOL_WEBHOOK = "60/minute"
RATE_LIMIT_CALL_END_WEBHOOK = "30/minute"

# ── LLM models ────────────────────────────────────────────────────────────────
SUMMARY_MODEL = "gpt-4o-mini"
SUMMARY_MAX_TOKENS = 100
SUMMARY_FALLBACK_LENGTH = 200

# ── Default server port ───────────────────────────────────────────────────────
DEFAULT_PORT = 3000

# ── FAQ fallback response (when Airtable returns no match) ────────────────────
FAQ_FALLBACK = (
    "I can help with claim status, office hours, document submission, and starting new claims."
)

# ── Tool error message (VAPI-speakable) ───────────────────────────────────────
TOOL_ERROR_MESSAGE = (
    "I'm experiencing a temporary issue. A representative will follow up shortly."
)
