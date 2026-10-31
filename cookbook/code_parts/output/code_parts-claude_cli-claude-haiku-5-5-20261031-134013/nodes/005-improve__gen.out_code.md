=== FILE: README.md ===
# palindrome

A small library with one function, `is_palindrome(text)`, which tells whether a string reads the same forwards and backwards.

Comparison ignores case, whitespace and punctuation. Only ASCII letters and digits (`a-z`, `A-Z`, `0-9`) take part in the comparison. Text is first normalized to Unicode NFC, so composed and decomposed forms of the same characters (for example `"é"` written as one code point or as `e` plus a combining accent) compare equal. Any other character, including non-ASCII letters, numeric symbols such as `"²"` or `"½"`, and combining marks, is treated as punctuation and ignored.

Empty strings, and strings with no ASCII letters or digits, are palindromes.

## Usage

```python
from palindrome import is_palindrome

is_palindrome("A man, a plan, a canal: Panama")  # True
is_palindrome("race a car")                      # False
is_palindrome("abba")                            # True
is_palindrome("1a1")                             # True
is_palindrome("a1 1a")                           # True
is_palindrome("\u00e9"[0] + "" if False else "e\u0301e")  # True: "ée" is not a palindrome, but "e\u0301e" normalizes to "ee"
```

Passing a non-string raises `TypeError`.

## Running the tests

From the project folder:

```
python -m unittest test_palindrome -v
```

=== FILE: palindrome.py ===
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


=== FILE: test_palindrome.py ===
import unittest

from palindrome import is_palindrome


class IsPalindromeTests(unittest.TestCase):
    def test_classic_phrase_with_punctuation_and_case(self):
        self.assertTrue(is_palindrome("A man, a plan, a canal: Panama"))

    def test_simple_word(self):
        self.assertTrue(is_palindrome("racecar"))

    def test_mixed_case_word(self):
        self.assertTrue(is_palindrome("RaceCar"))

    def test_not_a_palindrome(self):
        self.assertFalse(is_palindrome("race a car"))

    def test_digits(self):
        self.assertTrue(is_palindrome("12321"))
        self.assertFalse(is_palindrome("12345"))

    def test_ignores_spaces_case_and_punctuation(self):
        self.assertTrue(is_palindrome("Was it a car or a cat I saw?"))

    def test_differs_only_in_punctuation(self):
        self.assertTrue(is_palindrome("No 'x' in Nixon"))
        self.assertTrue(is_palindrome("ab-ba"))
        self.assertFalse(is_palindrome("ab-bc"))

    def test_empty_string(self):
        self.assertTrue(is_palindrome(""))

    def test_no_letters_or_digits(self):
        self.assertTrue(is_palindrome(" .,!? "))

    def test_single_character(self):
        self.assertTrue(is_palindrome("a"))

    def test_even_length_palindromes(self):
        self.assertTrue(is_palindrome("abba"))
        self.assertTrue(is_palindrome("noon"))
        self.assertFalse(is_palindrome("abab"))

    def test_mixed_letters_and_digits(self):
        self.assertTrue(is_palindrome("1a1"))
        self.assertTrue(is_palindrome("a1 1a"))
        self.assertFalse(is_palindrome("1a2"))

    def test_combining_mark_is_ignored_after_nfc(self):
        # "e" + combining acute + "e": after NFC the accent is part of a
        # composed character, which is not ASCII, so it is skipped.
        self.assertTrue(is_palindrome("e\u0301e"))
        # Composed and decomposed forms of the same text behave the same.
        self.assertEqual(
            is_palindrome("\u00e9ab"),
            is_palindrome("e\u0301ab"),
        )

    def test_non_ascii_letters_are_ignored(self):
        self.assertTrue(is_palindrome("\u00e9a\u00e9"))  # "éaé"
        self.assertFalse(is_palindrome("\u00e9ab"))  # "éab" -> "ab"
        self.assertFalse(is_palindrome("ab\u00e9c"))  # "abc"

    def test_numeric_symbols_are_ignored(self):
        self.assertTrue(is_palindrome("1\u00b2 1"))  # "1² 1" -> "11"
        self.assertFalse(is_palindrome("1\u00bd2"))  # "1½2" -> "12"

    def test_non_palindrome_differing_only_in_case_folded_characters(self):
        self.assertFalse(is_palindrome("Ab"))
        self.assertTrue(is_palindrome("Aa"))

    def test_non_string_input_raises_type_error(self):
        with self.assertRaises(TypeError):
            is_palindrome(None)
        with self.assertRaises(TypeError):
            is_palindrome(123)


if __name__ == "__main__":
    unittest.main()