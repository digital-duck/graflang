# Specification: `count_upper`

## 1. Purpose
Count how many uppercase vowels appear at even positions in a string. Positions are 0-based, so the positions checked are 0, 2, 4, and so on. The function is exposed under two names: `count_upper` and `count_uppercase_vowels_at_even_indices`. Both refer to the same function.

## 2. Inputs
- **`s`**: a string (`str`) of any length, including empty. It may contain any Unicode characters.
- Any other type, including `None`, `bytes`, lists and numbers, is invalid.

## 3. Outputs
- Returns a non-negative integer. It is the number of characters in `s` that meet both conditions:
  1. The character is at an even 0-based index.
  2. The character is one of the five ASCII uppercase vowels `A`, `E`, `I`, `O`, `U`.
- The result is at most `ceil(len(s) / 2)`.

## 4. Behaviour
- **Type check:** If `s` is not a `str`, the function raises `TypeError` before doing anything else. The message names the offending type, in the form "s must be a str, got <typename>".
- **Selection:** Examine only the characters at indices 0, 2, 4, … Characters at odd indices are ignored, whatever they are.
- **Matching:** A selected character counts only if it is exactly `A`, `E`, `I`, `O` or `U`. Matching is case-sensitive and exact:
  - Lowercase vowels (`a e i o u`) do not count.
  - `Y` does not count.
  - Non-ASCII uppercase vowels such as `É` and `Ü` do not count.
  - Consonants, digits, whitespace and punctuation do not count.
- **Edge cases:**
  - The empty string returns 0.
  - A single-character string checks only index 0.
  - A string with no matching characters at even indices returns 0.
- **Examples:**

| Input | Result | Reason |
|---|---|---|
| `""` | 0 | No characters |
| `"A"` | 1 | Index 0 is `A` |
| `"aBCdEf"` | 1 | Even indices hold `a`, `C`, `E`; only `E` counts |
| `"dBBE"` | 0 | Even indices hold `d`, `B`; the `E` is at index 3, which is odd |
| `"EAEAEA"` | 3 | Even indices hold `E`, `E`, `E` |
| `"aAeEiI"` | 0 | Even indices hold lowercase vowels only |
| `"AÉEÜ"` | 2 | `A` at 0 and `E` at 2 count; `É` and `Ü` are at odd indices and are not ASCII vowels |
| `"ÉBÜB"` | 0 | `É` and `Ü` are at even indices but are not ASCII vowels |
| `"YAY"` | 0 | `Y` does not count, and `A` is at an odd index |

## 5. Assumptions
- Indices are counted in Python `str` code points, not bytes or grapheme clusters. A combining sequence therefore occupies several positions.
- The function is pure. It has no side effects and keeps no state.
- The vowel set is fixed and has exactly five members. It is not configurable.
- The only error condition is a non-`str` argument. Subclasses of `str` are accepted. No other exceptions are expected for valid input.
- Callers rely on the exception type (`TypeError`), not on the exact message text.