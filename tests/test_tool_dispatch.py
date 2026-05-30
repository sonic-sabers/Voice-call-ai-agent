"""Webhook tool dispatch integration tests using httpx TestClient."""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from server.main import app
from server.models.caller import CallerRecord

client = TestClient(app)

HEADERS = {"x-vapi-secret": "test-secret-123"}
MAYA = CallerRecord("+14085550192", "Maya", "Patel", "1987-09-14", "CLM-2847", "approved", "")


def _tool_body(name: str, params: dict, call_id: str = "call-test") -> dict:
    return {
        "message": {
            "toolCallList": [{"id": "tc-1", "name": name, "parameters": params}],
            "call": {"id": call_id},
        }
    }


@pytest.fixture(autouse=True)
def patch_env(monkeypatch):
    monkeypatch.setenv("VAPI_WEBHOOK_SECRET", "test-secret-123")
    monkeypatch.setenv("GOOGLE_SPREADSHEET_ID", "test-sheet-id")
    monkeypatch.setenv("GOOGLE_CREDENTIALS_JSON", '{"type":"service_account"}')
    # Reset lru_cache so each test picks up monkeypatched env
    from server.core.config import get_settings
    get_settings.cache_clear()


class TestWebhookAuth:
    def test_missing_secret_returns_401(self) -> None:
        resp = client.post("/webhook/tool", json=_tool_body("lookup_caller", {"phone": "+14085550192"}))
        assert resp.status_code == 401

    def test_wrong_secret_returns_401(self) -> None:
        resp = client.post(
            "/webhook/tool",
            json=_tool_body("lookup_caller", {"phone": "+14085550192"}),
            headers={"x-vapi-secret": "wrong"},
        )
        assert resp.status_code == 401


class TestLookupCaller:
    def test_found(self) -> None:
        with patch("server.services.tool_dispatch.lookup_caller", return_value=MAYA):
            resp = client.post(
                "/webhook/tool",
                json=_tool_body("lookup_caller", {"phone": "+14085550192"}),
                headers=HEADERS,
            )
        assert resp.status_code == 200
        result = json.loads(resp.json()["results"][0]["result"])
        assert result["found"] is True
        assert result["firstName"] == "Maya"
        # claim data must NOT be present pre-auth
        assert "claimId" not in result
        assert "claimStatus" not in result

    def test_not_found(self) -> None:
        with patch("server.services.tool_dispatch.lookup_caller", return_value=None):
            resp = client.post(
                "/webhook/tool",
                json=_tool_body("lookup_caller", {"phone": "+19995550000"}),
                headers=HEADERS,
            )
        result = json.loads(resp.json()["results"][0]["result"])
        assert result["found"] is False

    def test_invalid_phone(self) -> None:
        resp = client.post(
            "/webhook/tool",
            json=_tool_body("lookup_caller", {"phone": "not-a-phone"}),
            headers=HEADERS,
        )
        result = json.loads(resp.json()["results"][0]["result"])
        assert result["found"] is False
        assert result["error"] == "INVALID_PHONE"


class TestConfirmIdentity:
    def test_confirm_sets_auth(self) -> None:
        call_id = "call-confirm"
        # First seed pending_callers via lookup
        with patch("server.services.tool_dispatch.lookup_caller", return_value=MAYA):
            client.post(
                "/webhook/tool",
                json=_tool_body("lookup_caller", {"phone": "+14085550192"}, call_id),
                headers=HEADERS,
            )
        resp = client.post(
            "/webhook/tool",
            json=_tool_body("confirm_identity", {"phone": "+14085550192"}, call_id),
            headers=HEADERS,
        )
        result = json.loads(resp.json()["results"][0]["result"])
        assert result["confirmed"] is True
        assert result["variableValues"]["authenticated"] == "true"
        assert result["variableValues"]["customer_name"] == "Maya"


class TestAnswerFaq:
    def test_returns_answer(self) -> None:
        with patch("server.services.tool_dispatch.query_knowledge_base", return_value="We are open Mon-Fri 8am-6pm ET."):
            resp = client.post(
                "/webhook/tool",
                json=_tool_body("answer_faq", {"question": "what are your hours?"}),
                headers=HEADERS,
            )
        result = resp.json()["results"][0]["result"]
        assert "Mon-Fri" in result

    def test_fallback_on_no_match(self) -> None:
        with patch("server.services.tool_dispatch.query_knowledge_base", return_value=None):
            resp = client.post(
                "/webhook/tool",
                json=_tool_body("answer_faq", {"question": "some unknown question"}),
                headers=HEADERS,
            )
        result = resp.json()["results"][0]["result"]
        assert "claim status" in result.lower()
