from __future__ import annotations

from pyairtable import Api

from server.core.config import get_settings
from server.core.constants import AIRTABLE_TABLE_FAQ


async def check_airtable() -> bool:
    """Return True if we can reach the Airtable FAQ table."""
    try:
        cfg = get_settings()
        if not cfg.airtable_api_key or not cfg.airtable_base_id:
            return False
        Api(cfg.airtable_api_key).table(cfg.airtable_base_id, AIRTABLE_TABLE_FAQ).first()
        return True
    except Exception:
        return False
