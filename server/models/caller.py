"""Typed model for a caller row read from the 'callers' Google Sheet."""
from dataclasses import dataclass


@dataclass
class CallerRecord:
    phone: str
    first_name: str
    last_name: str
    dob: str          # YYYY-MM-DD — never returned to LLM
    claim_id: str
    claim_status: str
    docs_required: str
    policy_number: str = ""
    zip_code: str = ""  # 5-digit ZIP — used for alternate verification only
