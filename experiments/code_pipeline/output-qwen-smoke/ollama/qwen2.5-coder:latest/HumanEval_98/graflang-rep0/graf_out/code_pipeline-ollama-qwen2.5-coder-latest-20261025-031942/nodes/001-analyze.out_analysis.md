[READY]

This spec is clear enough to proceed. The task is to implement a function `count_upper` that counts the number of uppercase vowels at even indices in a given string.

STRUCTURED SPEC:
1. Implement the function `count_upper(s)` where `s` is a string.
2. The function should return an integer count.
3. Uppercase vowels to consider are 'A', 'E', 'I', 'O', 'U'.
4. Only characters at even indices should be considered (0, 2, 4, ...).
5. The function should handle an empty string gracefully, returning 0.
6. The function should ignore non-alphabetic characters at even indices.
7. The function should ignore uppercase vowels at odd indices.