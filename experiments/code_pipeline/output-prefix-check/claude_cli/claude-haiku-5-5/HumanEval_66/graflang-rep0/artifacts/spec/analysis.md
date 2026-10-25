[READY]
Build `digitSum(s)`, which returns the sum of the ASCII codes of the uppercase letters in `s` as an int, with 0 for an empty string.

**Analysis:** The purpose is clear and the signature is explicit. The examples are consistent with the rule: `"abAB"` gives 65 + 66 = 131, `"aAaaaXa"` gives 65 + 88 = 153, and `""` gives 0. The only open point is what "upper" means for non-ASCII characters. The spec says "ASCII codes", so I take the uppercase set to be A–Z. The stray `'` after the docstring's first sentence is a typo and doesn't affect the behaviour.

**STRUCTURED SPEC:**
1. Signature: `def digitSum(s):` returns an `int`. `s` is a `str`.
2. Only characters in `'A'`–`'Z'` (code points 65–90) are counted. All other characters, including lowercase letters, digits, punctuation, whitespace, and non-ASCII characters, are ignored.
3. The result is the sum of `ord(c)` over every qualifying character `c`. Repeated characters are each counted.
4. An empty string returns `0`.
5. A string with no uppercase letters returns `0`.
6. The output must include the function definition and any imports it needs. The function needs no imports if it is written with a plain loop or generator over `s`.
7. The docstring may be kept as given, with the stray `'` removed.