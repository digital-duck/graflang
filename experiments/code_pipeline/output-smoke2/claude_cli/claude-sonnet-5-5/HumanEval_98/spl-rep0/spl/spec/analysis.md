[READY]
Build a Python function `count_upper(s)` that returns the number of uppercase vowels (A, E, I, O, U) found at even (0-based) indices of string `s`.

The spec is clear enough to proceed. The docstring gives one goal and a signature, and the examples settle the main ambiguity: indexing is 0-based. Check `'aBCdEf'`. The even indices 0, 2, 4 hold 'a', 'C', 'E', so the count is 1. In `'dBBE'`, 'E' is at index 3 (odd), so the count is 0. The remaining gaps are minor and have obvious defaults: empty input, non-ASCII characters, and non-string input.

STRUCTURED SPEC:
1. Define `count_upper(s)`, which takes a string `s` and returns an `int`.
2. Indices are 0-based. Only even indices (0, 2, 4, ...) are examined.
3. A character counts only if it is one of the uppercase vowels `A`, `E`, `I`, `O`, `U`. Lowercase vowels and uppercase consonants do not count.
4. Return the total number of matching characters.
5. An empty string returns 0.
6. Expected results: `count_upper('aBCdEf') == 1`, `count_upper('abcdefg') == 0`, `count_upper('dBBE') == 0`.
7. Return the complete function with its signature, including any imports it needs. It needs none, since the function can use a plain string-membership check.
8. Out of scope: input validation, non-string inputs, and handling of non-ASCII vowels.