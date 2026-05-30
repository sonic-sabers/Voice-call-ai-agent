import pytest
from server.core.phone import normalize_phone


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("4085550192", "+14085550192"),
        ("408-555-0192", "+14085550192"),
        ("(408) 555-0192", "+14085550192"),
        ("408.555.0192", "+14085550192"),
        ("+14085550192", "+14085550192"),
        ("14085550192", "+14085550192"),
        ("1 408 555 0192", "+14085550192"),
        ("", None),
        ("123", None),
        ("not a phone", None),
    ],
)
def test_normalize_phone(raw: str, expected: str | None) -> None:
    assert normalize_phone(raw) == expected
