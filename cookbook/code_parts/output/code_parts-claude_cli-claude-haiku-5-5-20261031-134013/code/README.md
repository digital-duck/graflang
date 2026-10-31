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
