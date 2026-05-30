"""Airtable knowledge base — FAQ lookup by keyword tag matching."""
from __future__ import annotations

import logging
import random
import time

from pyairtable import Api
from pyairtable.exceptions import PyAirtableError as AirtableApiError

from server.core.config import get_settings
from server.core.constants import AIRTABLE_BASE_DELAY, AIRTABLE_MAX_RETRIES, AIRTABLE_TABLE_FAQ

log = logging.getLogger(__name__)

_MAX_RETRIES = AIRTABLE_MAX_RETRIES
_BASE_DELAY = AIRTABLE_BASE_DELAY


def _backoff(attempt: int) -> None:
    cap = _BASE_DELAY * (2**attempt)
    time.sleep(random.uniform(0, cap))


def query_knowledge_base(question: str) -> str | None:
    """Search Airtable FAQ table. Returns answer string or None if no match / error."""
    if not question or not question.strip():
        return None

    cfg = get_settings()
    api_key = cfg.airtable_api_key
    base_id = cfg.airtable_base_id
    if not api_key or not base_id:
        log.error("AIRTABLE_API_KEY / AIRTABLE_BASE_ID not set")
        return None

    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            table = Api(api_key).table(base_id, AIRTABLE_TABLE_FAQ)
            records = table.all(fields=["tag", "answer"])
            q = question.lower()
            for record in records:
                tag = record["fields"].get("tag", "").lower()
                if tag and tag in q:
                    return record["fields"].get("answer")  # type: ignore[return-value]
            return None
        except AirtableApiError as exc:
            last_exc = exc
            log.warning("query_knowledge_base attempt %d failed: %s", attempt + 1, exc)
            if attempt < _MAX_RETRIES - 1:
                _backoff(attempt)
    log.error("query_knowledge_base exhausted retries: %s", last_exc)
    return None
