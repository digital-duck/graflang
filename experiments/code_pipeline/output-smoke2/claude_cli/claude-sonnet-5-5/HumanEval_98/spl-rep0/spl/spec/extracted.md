# Specification: Count Uppercase Vowels at Even Indices

## 1. Purpose
Given a string, determine how many of the characters at even, 0-based positions (0, 2, 4, …) are uppercase English vowels. Lowercase vowels, consonants, other characters, and anything at odd positions do not contribute. The function is also exposed under the alias `count_uppercase_vowels_at_even_indices`, which behaves identically.

## 2. Inputs
- **s**: a single required argument, which must be a string (`str`). Any length is allowed, including empty. Any Unicode content is allowed.
- A `str` subclass is accepted. Any non-`str` value is rejected.

## 3. Outputs
- A non-negative integer.
- It equals the number of positions i in the string where i is even (0-based) and the character at i is one of `A`, `E`, `I`, `O`, `U`.
- The result is at most ⌈len(s)/2⌉. It is 0 for the empty string.

## 4. Behaviour
1. **Type check.** If `s` is not a `str`, raise `TypeError`. The message states that `s` must be a `str` and names the type actually received. No other validation occurs, and nothing is coerced.
2. **Selection.** Examine only the characters at indices 0, 2, 4, … Ignore characters at odd indices entirely.
3. **Matching.** A character counts only if it is exactly one of the five ASCII capital letters `A`, `E`, `I`, `O`, `U`.
   - Lowercase vowels (`a e i o u`) do not count.
   - `Y` is not treated as a vowel.
   - Accented or other non-ASCII uppercase vowels, such as `É`, do not count.
4. **Result.** Return the number of matching characters.

Examples:
- `""` → 0
- `"A"` → 1
- `"a"` → 0
- `"aBCdEf"` → 1 (only `E` at index 4 counts)
- `"AbEcIdOfU"` → 4 (`A`, `E`, `I`, `U`; the `O` is at index 6, which is even, so it also counts, and these five characters sit at indices 0, 2, 4, 6, 8. That makes the count 5, which contradicts the documented value of 4.) The documented example is the authority on intent, but see the note under Assumptions.
- `"aAeEiI"` → 0 (every uppercase vowel is at an odd index)
- `"bAdEfI"` → 0 (every uppercase vowel is at an odd index)

## 5. Assumptions
- Indexing is by Unicode code point (Python string indexing), not by byte or grapheme cluster. A combining sequence or surrogate-like sequence occupies several indices.
- The set of counted characters is fixed and case-sensitive. No locale or Unicode normalization is applied. Decomposed forms like `E` plus a combining accent count the `E` only if it falls on an even index.
- The input is not mutated. The function is pure, deterministic, and has no side effects.
- Strings are finite and small enough to scan in linear time and constant extra space.
- **Discrepancy in the docstring.** By the stated rule, `"AbEcIdOfU"` has uppercase vowels `A`, `E`, `I`, `O`, `U` at indices 0, 2, 4, 6, 8, so the result is 5, not 4. The implementation follows the rule, so it returns 5 for that input. The docstring example claiming 4 is wrong, and a doctest of it would fail.