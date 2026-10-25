# Specification: `count_upper`

## 1. Purpose
Count how many characters in a string are uppercase vowels (A, E, I, O, U) and sit at even positions. Positions are 0-based, so the first character is at position 0, which counts as even.

## 2. Inputs
- **`s`**: a value of type `str`. It can be any length, including empty. It can contain any characters.
- Any other type, including `None`, bytes, lists and numbers, is invalid.

## 3. Outputs
- A non-negative integer. It is the number of characters in `s` that satisfy both conditions below.
  1. The character's 0-based index is even (0, 2, 4, …).
  2. The character is exactly one of the ASCII uppercase letters `A`, `E`, `I`, `O`, `U`.
- The result is at most `ceil(len(s) / 2)`.

## 4. Behaviour
- If `s` is not a `str`, raise `TypeError`. The message states that `s` must be a `str` and names the actual type received. This check happens before any counting.
- Otherwise, examine only the characters at indices 0, 2, 4, … of `s` and count those that are one of the five uppercase vowels.
- Characters at odd indices are never counted, even if they are uppercase vowels.
- These characters are never counted:
  - lowercase vowels
  - consonants, whether uppercase or lowercase
  - digits, punctuation and whitespace
  - accented or other non-ASCII letters, such as `É`
  - the letter `Y`
- Matching is case-sensitive and exact. There is no Unicode normalisation or case folding.
- The empty string returns 0.
- The input is not modified.
- Examples:
  - `'aBCdEf'` → 1. The even-index characters are `a`, `C`, `E`, and only `E` counts.
  - `'abcdefg'` → 0.
  - `'dBBE'` → 0. `E` is at index 3, which is odd.
  - `''` → 0.

## 5. Assumptions
- Indexing is by Python string element (code point), not by byte or grapheme cluster. A combining sequence or surrogate-like composition therefore occupies several indices.
- Subclasses of `str` are accepted as `str`.
- Callers need no special handling for very long strings. The function is a pure, side-effect-free function of its input, and its running time is linear in the length of the string.
- There is no locale dependence.