=== FILE: README.md ===
# palindrome

A small library with one function, `is_palindrome(s)`, which tells whether a string reads the same forwards and backwards. Case and punctuation are ignored, and so is whitespace, since only letters and digits are compared.

## Usage

```python
from palindrome import is_palindrome

is_palindrome("A man, a plan, a canal: Panama")  # True
is_palindrome("race a car")                      # False
```

## Running the tests

From the project folder:

```
python -m unittest test_palindrome -v
```

=== FILE: palindrome.py ===
"""Palindrome checking that ignores case and punctuation."""


def _normalize(s: str) -> str:
    """Return the lowercase letters and digits of ``s``, in order."""
    return "".join(ch.lower() for ch in s if ch.isalnum())


def is_palindrome(s: str) -> bool:
    """Return True if ``s`` reads the same forwards and backwards.

    Case, punctuation and whitespace are ignored; only letters and
    digits are compared. An empty string, or one with no letters or
    digits, is a palindrome.
    """
    normalized = _normalize(s)
    return normalized == normalized[::-1]


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

    def test_punctuation_only_difference(self):
        self.assertTrue(is_palindrome("Was it a car or a cat I saw?"))

    def test_empty_string(self):
        self.assertTrue(is_palindrome(""))

    def test_no_letters_or_digits(self):
        self.assertTrue(is_palindrome(" .,!? "))

    def test_single_character(self):
        self.assertTrue(is_palindrome("a"))


if __name__ == "__main__":
    unittest.main()