- **Unicode combining marks break the comparison.** `isalnum()` drops combining characters, so `"e\u0301e"` (visually "ée") normalizes to `"ee"` and is reported as a palindrome. Normalize the input first (e.g. `unicodedata.normalize("NFC", s)` or NFKD with combining marks filtered out) so that composed and decomposed forms behave the same and the result matches what a reader sees.

- **The docstrings over-promise.** `isalnum()` accepts characters such as `"²"`, `"½"`, and `"Ⅻ"`, which are numeric but not strictly "digits". `_normalize` and `is_palindrome` both say "letters and digits". Either restrict to ASCII (`ch.isascii() and ch.isalnum()`) and say so, or document that Unicode letters and numeric characters are compared.

- **Name mismatch in a test.** `test_punctuation_only_difference` uses `"Was it a car or a cat I saw?"`, which also differs in case and spacing. A name like `test_ignores_spaces_case_and_punctuation` describes it accurately. Consider also a separate test for a pair that differs only in punctuation.

- **Missing edge-case coverage:**
  - Even-length palindromes such as `"abba"` or `"noon"` (the code handles them, but nothing checks them).
  - Mixed letters and digits, e.g. `"1a1"` or `"a1 1a"`.
  - Non-ASCII input, including the combining-mark case above and a non-palindrome with non-ASCII letters.
  - A non-palindrome that differs only in case-folded characters.
  - Non-string input (`None`, `123`): the function raises `AttributeError` or `TypeError` by accident. Either test the intended behavior or document it.

- **Unnecessary allocation.** The function builds the normalized string and then a reversed copy, which is O(n) memory in addition to the input. A two-pointer scan over the original string that skips non-alphanumeric characters and stops at the first mismatch would avoid both copies and return early on non-palindromes.

- **Parameter name.** `s` is terse. `text` or `phrase` would make the public signature clearer to users reading `help(is_palindrome)`.