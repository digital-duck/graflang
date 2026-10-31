"""Palindrome checking that ignores case, whitespace and punctuation."""

import unicodedata

_ASCII_ALNUM = frozenset(
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
)


def is_palindrome(text: str) -> bool:
    """Return True if ``text`` reads the same forwards and backwards.

    The text is normalized to Unicode NFC first, so composed and
    decomposed forms compare equal. Then only ASCII letters and digits
    are compared, case-insensitively; every other character (whitespace,
    punctuation, non-ASCII letters, numeric symbols such as "²", and
    combining marks) is skipped. An empty string, or one with no ASCII
    letters or digits, is a palindrome.

    Raises TypeError if ``text`` is not a string.
    """
    if not isinstance(text, str):
        raise TypeError(f"is_palindrome() expects str, not {type(text).__name__}")

    normalized = unicodedata.normalize("NFC", text)

    left, right = 0, len(normalized) - 1
    while left < right:
        if normalized[left] not in _ASCII_ALNUM:
            left += 1
            continue
        if normalized[right] not in _ASCII_ALNUM:
            right -= 1
            continue
        if normalized[left].lower() != normalized[right].lower():
            return False
        left += 1
        right -= 1
    return True
