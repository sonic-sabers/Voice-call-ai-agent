"""Chain-of-Verification claim response (Dhuliawala et al. 2023).

Prevents hallucination of claim data by re-fetching from Sheets and validating
server-side auth before the LLM is allowed to speak any claim detail.
"""
from __future__ import annotations

from dataclasses import dataclass

from server.core.constants import CLAIM_PROCESSING_DAYS, PORTAL_URL, SUPPORT_EMAIL
from server.core.state import authenticated_calls
from server.services.sheets import lookup_caller

# Explicit allowlist — any unrecognised status (DB typo, future value) returns
# safe_to_speak=False rather than leaking raw data through an unhandled branch.
_VALID_STATUSES = frozenset({"approved", "pending", "requires_documentation"})


@dataclass
class ClaimResponseOutput:
    safe_to_speak: bool
    response: str


def compose_claim_response(phone: str, call_id: str) -> ClaimResponseOutput:
    """Return a pre-verified, safe-to-speak claim status sentence.

    Steps (CoVe adaptation):
    1. Guard: server-side auth check — phone must match authenticated session.
    2. Re-fetch: pull claim data fresh from Sheets (not from LLM memory).
    3. Validate: claim_status must be in allowlist.
    4. Compose: return exact wording the LLM must speak verbatim.
    """
    # Step 1 — auth guard
    # Use server-side registered phone — LLM may pass unregistered caller phone
    # in alternate-phone flows (verify_by_name_zip / verify_by_name_dob).
    auth_entry = authenticated_calls.get(call_id)
    if not auth_entry:
        return ClaimResponseOutput(
            safe_to_speak=False,
            response="I'm having trouble verifying the account. A representative will follow up shortly.",
        )
    registered_phone = auth_entry.get("phone") or phone

    # Step 2 — re-fetch using registered phone (not LLM-provided phone)
    record = lookup_caller(registered_phone)

    # Step 3 — validate
    if not record or record.claim_status not in _VALID_STATUSES:
        return ClaimResponseOutput(
            safe_to_speak=False,
            response="I'm having trouble retrieving your claim details. A representative will follow up shortly.",
        )

    # Step 4 — compose
    claim_id_spoken = record.claim_id.replace("-", " ")  # CLM-2847 → CLM 2847 (avoids TTS "minus")
    policy_spoken = record.policy_number.replace("-", " ") if record.policy_number else ""
    policy_suffix = f" under policy {policy_spoken}" if policy_spoken else ""

    if record.claim_status == "approved":
        return ClaimResponseOutput(
            safe_to_speak=True,
            response=f"Great news — your claim {claim_id_spoken}{policy_suffix} has been approved.",
        )
    if record.claim_status == "pending":
        return ClaimResponseOutput(
            safe_to_speak=True,
            response=(
                f"Your claim {claim_id_spoken}{policy_suffix} is currently pending. "
                f"Standard processing takes {CLAIM_PROCESSING_DAYS}."
            ),
        )
    # requires_documentation — verify docs_required populated
    if not record.docs_required:
        return ClaimResponseOutput(
            safe_to_speak=False,
            response="Your claim requires additional documentation. A specialist will contact you with details.",
        )
    return ClaimResponseOutput(
        safe_to_speak=True,
        response=(
            f"Your claim {claim_id_spoken}{policy_suffix} requires additional documentation — "
            f"specifically, {record.docs_required}. "
            f"You can upload it at {PORTAL_URL} or email {SUPPORT_EMAIL}."
        ),
    )
