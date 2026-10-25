[READY]
Build a Python function `count_upper(s)` that returns the number of uppercase vowels (A, E, I, O, U) found at even indices (0, 2, 4, …) of the string `s`.

The examples and the docstring settle the two points that could look ambiguous:
- **Indexing** is 0-based. In `'aBCdEf'` the even indices hold `a`, `C`, `E`, so the count is 1 (`E`). In `'dBBE'` the even indices hold `d` and `B`, so the count is 0. The `E` is at index 3, which is odd.
- **Vowels** are the English letters A, E, I, O, U, in uppercase only. Lowercase vowels don't count (`'abcdefg'` gives 0).

STRUCTURED SPEC:
1. Define `def count_upper(s):` and return the complete function. It needs no imports.
2. The input `s` is a string. Behavior for non-string input is unspecified, so no validation is required.
3. Iterate over the characters of `s` at even, 0-based indices: 0, 2, 4, and so on.
4. Count a character only if it is one of `'AEIOU'`.
5. Return the count as an `int`.
6. An empty string returns `0`.
7. The function must satisfy the three docstring examples: `'aBCdEf'` → 1, `'abcdefg'` → 0, `'dBBE'` → 0.