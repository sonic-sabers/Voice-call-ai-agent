"""Single entry point for all environment variables.

Every module must import get_settings() from here — no direct os.environ reads anywhere else.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache

from dotenv import load_dotenv

from server.core.constants import DEFAULT_PORT

load_dotenv()


@dataclass(frozen=True)
class Settings:
    # ── Required ──────────────────────────────────────────────────────────────
    vapi_webhook_secret: str
    google_spreadsheet_id: str
    google_credentials_json: str
    # ── Optional (features degrade gracefully if absent) ─────────────────────
    airtable_api_key: str = field(default="")
    airtable_base_id: str = field(default="")
    openai_api_key: str = field(default="")
    vapi_public_key: str = field(default="")
    vapi_assistant_id: str = field(default="")
    # ── Server ────────────────────────────────────────────────────────────────
    port: int = field(default=DEFAULT_PORT)

    def __post_init__(self) -> None:
        required = [
            ("VAPI_WEBHOOK_SECRET", self.vapi_webhook_secret),
            ("GOOGLE_SPREADSHEET_ID", self.google_spreadsheet_id),
            ("GOOGLE_CREDENTIALS_JSON", self.google_credentials_json),
        ]
        missing = [name for name, val in required if not val]
        if missing:
            raise EnvironmentError(f"Missing required env vars: {', '.join(missing)}")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached Settings instance. Call once at startup; reuse everywhere."""
    return Settings(
        vapi_webhook_secret=os.environ.get("VAPI_WEBHOOK_SECRET", ""),
        google_spreadsheet_id=os.environ.get("GOOGLE_SPREADSHEET_ID", ""),
        google_credentials_json=os.environ.get("GOOGLE_CREDENTIALS_JSON", ""),
        airtable_api_key=os.environ.get("AIRTABLE_API_KEY", ""),
        airtable_base_id=os.environ.get("AIRTABLE_BASE_ID", ""),
        openai_api_key=os.environ.get("OPENAI_API_KEY", ""),
        vapi_public_key=os.environ.get("VAPI_PUBLIC_KEY", ""),
        vapi_assistant_id=os.environ.get("VAPI_ASSISTANT_ID", ""),
        port=int(os.environ.get("PORT", str(DEFAULT_PORT))),
    )
