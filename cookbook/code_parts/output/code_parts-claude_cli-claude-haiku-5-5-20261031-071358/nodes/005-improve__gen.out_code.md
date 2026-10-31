```python
import unicodedata


def is_palindrome(s):
    """Return True if `s` reads the same forwards and backwards.

    Comparison is case-insensitive (uses casefold), ignores any character
    that is not alphanumeric (punctuation, whitespace, symbols), and is
    Unicode-aware: text is NFKD-normalized and combining marks are dropped,
    so "Café" matches "cafe". Digits and non-ASCII letters are kept.

    Input with no alphanumeric characters (e.g. "", " ", "!!!") returns True.

    Raises TypeError if `s` is not a str.
    """
    if not isinstance(s, str):
        raise TypeError(f"is_palindrome expects str, got {type(s).__name__}")

    chars = []
    for ch in unicodedata.normalize("NFKD", s):
        if unicodedata.combining(ch):
            continue
        for c in ch.casefold():
            if c.isalnum():
                chars.append(c)

    left, right = 0, len(chars) - 1
    while left < right:
        if chars[left] != chars[right]:
            return False
        left += 1
        right -= 1
    return True
```