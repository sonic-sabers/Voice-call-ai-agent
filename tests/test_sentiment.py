import pytest
from server.services.sentiment import classify_sentiment


@pytest.mark.parametrize(
    "transcript, expected",
    [
        ("I'm so frustrated with this claim", "negative"),
        ("This is terrible and unacceptable", "negative"),
        ("Thank you so much, very helpful", "positive"),
        ("Great, appreciate the assistance", "positive"),
        ("I need to know my claim status", "neutral"),
        ("", "neutral"),
        ("the quick brown fox", "neutral"),
    ],
)
def test_classify_sentiment(transcript: str, expected: str) -> None:
    assert classify_sentiment(transcript) == expected
