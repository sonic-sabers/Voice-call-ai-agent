from __future__ import annotations

import re


def normalize_phone(raw: str) -> str | None:
    """Normalize spoken/typed phone to E.164 (+1XXXXXXXXXX).

    Accepts: digits only, dashes, dots, spaces, parens.
    Returns None for unrecognizable input.
    """
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    return None
