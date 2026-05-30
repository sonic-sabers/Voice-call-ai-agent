from __future__ import annotations

from server.core.config import get_settings
from server.services.sheets import _get_client


async def check_sheets() -> bool:
    """Return True if we can open the spreadsheet."""
    try:
        sid = get_settings().google_spreadsheet_id
        if not sid:
            return False
        _get_client().open_by_key(sid)
        return True
    except Exception:
        return False
