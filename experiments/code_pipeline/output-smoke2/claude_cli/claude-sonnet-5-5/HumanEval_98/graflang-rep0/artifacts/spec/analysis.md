[READY]
Build a Python function `count_upper(s)` that returns how many characters at even indices (0, 2, 4, …) of `s` are uppercase vowels.

Analysis: The purpose is a single concrete function with a given signature. The input is a string and the output is an int. The three examples fix the semantics: 'aBCdEf' has E at index 4, so the result is 1. 'abcdefg' has no uppercase characters, so the result is 0. 'dBBE' has E at odd index 3, so the result is 0. Edge cases, such as the empty string, follow naturally and return 0. No error handling or non-string input behavior is specified, and none is needed.

STRUCTURED SPEC:
1. Define `count_upper(s)` taking one argument, a string `s`.
2. Return an `int` equal to the count of positions `i` in `s` where `i` is even (0-based) and `s[i]` is in the set `{'A', 'E', 'I', 'O', 'U'}`.
3. Only uppercase vowels count. Lowercase vowels, consonants, digits, and other characters do not.
4. Indices are 0-based, so the first character is at even index 0.
5. An empty string returns 0.
6. Required examples: `count_upper('aBCdEf') == 1`, `count_upper('abcdefg') == 0`, `count_upper('dBBE') == 0`.
7. Output the complete function with its signature and docstring. It needs no imports, since the standard library isn't required.
8. No input validation is required, and no I/O or side effects.