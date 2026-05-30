"""Keyword-based sentiment classifier for call transcripts."""
from __future__ import annotations

_NEGATIVE = frozenset(
    ["frustrated", "angry", "terrible", "unacceptable", "ridiculous", "awful", "worst"]
)
_POSITIVE = frozenset(
    ["thank", "great", "helpful", "perfect", "wonderful", "appreciate"]
)


def classify_sentiment(transcript: str) -> str:
    """Return 'positive', 'negative', or 'neutral'."""
    t = transcript.lower()
    if any(w in t for w in _NEGATIVE):
        return "negative"
    if any(w in t for w in _POSITIVE):
        return "positive"
    return "neutral"
