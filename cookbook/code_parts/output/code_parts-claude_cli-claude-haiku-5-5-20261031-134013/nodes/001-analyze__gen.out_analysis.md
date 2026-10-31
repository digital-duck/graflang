[READY]
A function `is_palindrome(s)` that returns whether a string reads the same forwards and backwards, ignoring letter case and punctuation.

STRUCTURED SPEC:
1. **Signature:** `is_palindrome(s: str) -> bool`; returns `True` or `False`.
2. **Normalization:** Keep only alphanumeric characters (letters and digits) from `s`, and convert them to a single case (e.g. lowercase) before comparing.
3. **Punctuation and whitespace:** All non-alphanumeric characters, including spaces, punctuation, and symbols, are discarded before comparison.
4. **Comparison:** After normalization, the result is `True` if the remaining string equals its reverse, otherwise `False`.
5. **Edge cases:** The empty string, and any string with no alphanumeric characters (e.g. `"!!!"`), return `True` since the normalized string is empty and equals its reverse.
6. **Non-ASCII:** Unicode letters and digits are treated as alphanumeric using Python's `str.isalnum()`; case folding uses `str.lower()`.
7. **Examples:** `"A man, a plan, a canal: Panama"` → `True`; `"race a car"` → `False`; `"No 'x' in Nixon"` → `True`.
8. **Input validation:** Non-string input is not specified; behaviour for it is left to the implementer (raising `TypeError` is a reasonable default).

Assumptions I filled in: "palindrome" means the normalized sequence equals its reverse; the output is a bool; and digits count as significant characters. The spec does not say whether the function should raise on non-string input, so I've flagged that as an implementer's choice rather than inventing a requirement.