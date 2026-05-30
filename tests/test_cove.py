"""CoVe auth + claim response tests — mocks Sheets and state."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from server.models.caller import CallerRecord
from server.services.cove import compose_claim_response


def _make_record(status: str, docs: str = "") -> CallerRecord:
    return CallerRecord(
        phone="+14085550192",
        first_name="Maya",
        last_name="Patel",
        dob="1987-09-14",
        claim_id="CLM-2847",
        claim_status=status,
        docs_required=docs,
    )


class TestComposeClaimResponse:
    def test_unauthenticated_returns_safe_false(self) -> None:
        with patch("server.services.cove.authenticated_calls", {}):
            out = compose_claim_response("+14085550192", "call-abc")
        assert out.safe_to_speak is False
        assert "verify" in out.response.lower() or "trouble" in out.response.lower()

    def test_wrong_phone_in_auth_returns_safe_false(self) -> None:
        auth = {"call-abc": {"phone": "+10000000000"}}
        with patch("server.services.cove.authenticated_calls", auth):
            out = compose_claim_response("+14085550192", "call-abc")
        assert out.safe_to_speak is False

    def test_approved_claim(self) -> None:
        auth = {"call-abc": {"phone": "+14085550192"}}
        record = _make_record("approved")
        with (
            patch("server.services.cove.authenticated_calls", auth),
            patch("server.services.cove.lookup_caller", return_value=record),
        ):
            out = compose_claim_response("+14085550192", "call-abc")
        assert out.safe_to_speak is True
        assert "approved" in out.response
        assert "CLM-2847" in out.response

    def test_pending_claim(self) -> None:
        auth = {"call-abc": {"phone": "+14085550192"}}
        record = _make_record("pending")
        with (
            patch("server.services.cove.authenticated_calls", auth),
            patch("server.services.cove.lookup_caller", return_value=record),
        ):
            out = compose_claim_response("+14085550192", "call-abc")
        assert out.safe_to_speak is True
        assert "pending" in out.response
        assert "5 to 7" in out.response

    def test_requires_documentation_with_docs(self) -> None:
        auth = {"call-abc": {"phone": "+14085550192"}}
        record = _make_record("requires_documentation", "radiology report")
        with (
            patch("server.services.cove.authenticated_calls", auth),
            patch("server.services.cove.lookup_caller", return_value=record),
        ):
            out = compose_claim_response("+14085550192", "call-abc")
        assert out.safe_to_speak is True
        assert "radiology report" in out.response

    def test_requires_documentation_no_docs_returns_safe_false(self) -> None:
        auth = {"call-abc": {"phone": "+14085550192"}}
        record = _make_record("requires_documentation", "")
        with (
            patch("server.services.cove.authenticated_calls", auth),
            patch("server.services.cove.lookup_caller", return_value=record),
        ):
            out = compose_claim_response("+14085550192", "call-abc")
        assert out.safe_to_speak is False

    def test_unknown_caller_returns_safe_false(self) -> None:
        auth = {"call-abc": {"phone": "+14085550192"}}
        with (
            patch("server.services.cove.authenticated_calls", auth),
            patch("server.services.cove.lookup_caller", return_value=None),
        ):
            out = compose_claim_response("+14085550192", "call-abc")
        assert out.safe_to_speak is False

    def test_invalid_status_returns_safe_false(self) -> None:
        auth = {"call-abc": {"phone": "+14085550192"}}
        record = _make_record("unknown_status")
        with (
            patch("server.services.cove.authenticated_calls", auth),
            patch("server.services.cove.lookup_caller", return_value=record),
        ):
            out = compose_claim_response("+14085550192", "call-abc")
        assert out.safe_to_speak is False
