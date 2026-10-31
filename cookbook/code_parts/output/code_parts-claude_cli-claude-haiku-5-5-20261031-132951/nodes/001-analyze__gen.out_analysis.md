[READY]
A single function that reports whether a string reads the same forwards and backwards, ignoring letter case and punctuation.

STRUCTURED SPEC:
1. **Signature:** `is_palindrome(s: str) -> bool`, returning `True` if `s` is a palindrome under the rules below, else `False`.
2. **Case:** Comparison is case-insensitive (`"A"` and `"a"` are equal).
3. **Ignored characters:** Punctuation, whitespace, and other non-alphanumeric characters are removed before comparison (`"A man, a plan, a canal: Panama"` → `True`).
4. **Alphanumerics kept:** Letters and digits are compared as-is after case folding; digits are not discarded.
5. **Edge cases:** The empty string and strings with no alphanumeric characters (e.g. `"!!!"`) return `True`.
6. **Input validation:** A non-string argument raises `TypeError`.
7. **Unicode:** Use `str.isalnum()` and `str.casefold()` so non-ASCII letters are handled consistently; no normalization beyond that is required.
8. **Out of scope:** Returning match positions, reporting which characters were ignored, or performing any I/O.