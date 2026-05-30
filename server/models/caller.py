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
