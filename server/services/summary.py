"""Post-call summary generation via OpenAI GPT-4o-mini with PII redaction."""
from __future__ import annotations

import logging
import re

from server.core.config import get_settings
from server.core.constants import SUMMARY_FALLBACK_LENGTH, SUMMARY_MAX_TOKENS, SUMMARY_MODEL

log = logging.getLogger(__name__)

_PHONE_RE = re.compile(r"\+?\d[\d\s\-(). ]{9,}\d")
_DOB_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")


def redact_pii(text: str) -> str:
    """Redact phone numbers and dates of birth before sending to OpenAI."""
    text = _PHONE_RE.sub("[PHONE]", text)
    text = _DOB_RE.sub("[DOB]", text)
    return text


def generate_summary(transcript: str) -> str:
    """Summarize transcript with GPT-4o-mini. Falls back to truncated transcript on any error."""
    if not transcript:
        return ""
    try:
        from openai import OpenAI  # lazy import — optional dependency path

        client = OpenAI(api_key=get_settings().openai_api_key)
        resp = client.chat.completions.create(
            model=SUMMARY_MODEL,
            max_tokens=SUMMARY_MAX_TOKENS,
            messages=[
                {
                    "role": "system",
                    "content": "Summarize insurance call transcripts in 1-2 sentences. Be concise.",
                },
                {"role": "user", "content": redact_pii(transcript)},
            ],
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as exc:
        log.warning("generate_summary failed, using truncated transcript: %s", exc)
        return transcript[:SUMMARY_FALLBACK_LENGTH].strip() + ("..." if len(transcript) > SUMMARY_FALLBACK_LENGTH else "")
