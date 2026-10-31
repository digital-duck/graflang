import unicodedata

import pytest


def is_palindrome(s):
    """Return True if ``s`` reads the same forwards and backwards.

    Case, punctuation, whitespace and any other character that is not a
    letter or digit are ignored. "Letter or digit" follows ``str.isalnum()``,
    which is Unicode-aware: 'é' and '中' are kept, '_' is dropped.

    The text is NFKC-normalized, case-folded with ``str.casefold()`` and
    NFKC-normalized again before filtering, so composed and decomposed forms
    compare equal and 'ß' folds to 'ss'. Normalizing before filtering keeps
    combining marks that would otherwise be dropped.

    Empty strings and strings with no letters or digits (e.g. '' or '!!!')
    are treated as palindromes and return True.

    Raises:
        TypeError: if ``s`` is not a ``str``.
    """
    if not isinstance(s, str):
        raise TypeError(f"is_palindrome expects str, got {type(s).__name__}")

    text = unicodedata.normalize("NFKC", s)
    text = unicodedata.normalize("NFKC", text.casefold())
    cleaned = "".join(ch for ch in text if ch.isalnum())

    i, j = 0, len(cleaned) - 1
    while i < j:
        if cleaned[i] != cleaned[j]:
            return False
        i += 1
        j -= 1
    return True


# --- tests ---

def test_empty_string():
    assert is_palindrome("")


def test_whitespace_only():
    assert is_palindrome("   ")


def test_punctuation_only():
    assert is_palindrome("!!!")


def test_mixed_case():
    assert is_palindrome("Aa")
    assert not is_palindrome("Ab")


def test_digits():
    assert is_palindrome("12321")
    assert not is_palindrome("12345")


def test_odd_and_even_length():
    assert is_palindrome("abba")
    assert not is_palindrome("abca")
    assert is_palindrome("abcba")


def test_punctuation_and_spaces_ignored():
    assert is_palindrome("A man, a plan, a canal: Panama")
    assert not is_palindrome("Hello, world")


def test_unicode_letters():
    assert is_palindrome("été")
    assert is_palindrome("Été")
    assert not is_palindrome("Émile")


def test_unicode_composed_vs_decomposed():
    assert is_palindrome("e\u0301te\u0301")  # decomposed "été"


def test_casefold_german_sharp_s():
    assert is_palindrome("ßss")


def test_underscore_is_dropped():
    assert is_palindrome("a_a")


def test_rejects_non_str():
    with pytest.raises(TypeError):
        is_palindrome(None)
    with pytest.raises(TypeError):
        is_palindrome(["a", "b", "a"])