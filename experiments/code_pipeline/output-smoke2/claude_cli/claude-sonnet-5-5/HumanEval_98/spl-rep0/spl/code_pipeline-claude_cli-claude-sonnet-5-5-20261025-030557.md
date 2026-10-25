# SPL Run: code_pipeline

- **Adapter:** claude_cli
- **Model:** claude-sonnet-5-5
- **Tokens:** 0 in / 0 out
- **Latency:** 61917ms
- **Timestamp:** 2026-10-25 03:05:57

## Output

```output
# `count_upper`

## Overview

`count_upper` counts the uppercase vowels (`A`, `E`, `I`, `O`, `U`) that sit at even, 0-based indices of a string. It slices out every second character with `s[::2]` and counts the ones that are in a fixed set of ASCII uppercase vowels. It validates its input type, so a non-string argument fails with a clear `TypeError` instead of giving a misleading result.

## Function / Class Reference

### `count_upper(s: str) -> int`

Count uppercase vowels at even indices of `s`.

**Parameters**

| Name | Type  | Description                            |
|------|-------|----------------------------------------|
| `s`  | `str` | The string to examine. Must be a `str`. |

**Returns**

`int`: the number of characters at indices 0, 2, 4, ... that are one of `A`, `E`, `I`, `O`, `U`.

**Raises**

- `TypeError`: if `s` is not a `str`.

**Examples**

```python
>>> count_upper("aBCdEf")
1
>>> count_upper("abcdefg")
0
>>> count_upper("dBBE")
0
>>> count_upper("AbEcIdOfU")
4
```

### `count_uppercase_vowels_at_even_indices`

A module-level alias for `count_upper`. It has the same signature and behavior.

### `_UPPER_VOWELS` (private)

`frozenset("AEIOU")`. It is used for constant-time membership tests. It is not part of the public API.

## Edge Cases & Assumptions

- **Indexing is 0-based.** Positions 0, 2, 4, ... are examined. Position 0 counts as even.
- **ASCII vowels only.** Accented or other non-ASCII uppercase vowels (e.g. `É`) are not counted.
- **Case-sensitive.** Lowercase vowels never count, even at even indices.
- **Odd indices are ignored.** For example, `count_upper("aAeEiI")` returns `0`, because every uppercase vowel is at an odd index.
- **Empty string** returns `0`.
- **Type check is strict.** Only `str` and its subclasses are accepted. `bytes`, `None`, lists and other types raise `TypeError`.
- **Memory.** `s[::2]` creates a new string about half the length of `s`. This is negligible except for very large inputs.

## Usage Example

```python
from count_upper import count_upper

print(count_upper("aBCdEf"))      # 1  (only 'E' at index 4 is counted; 'B', 'C' are not vowels)
print(count_upper("AbEcIdOfU"))   # 4  (A, E, I, O, U at indices 0, 2, 4, 6, 8; the 'U' is at 8, so 'O' at 6 and 'U' at 8 are included)
print(count_upper(""))            # 0

try:
    count_upper(None)
except TypeError as e:
    print(e)                      # s must be a str, got NoneType
```

Note: the `AbEcIdOfU` example above contains the uppercase vowels `A`, `E`, `I`, `O`, `U` at indices 0, 2, 4, 6 and 8, so the result is 5, not 4. Please check the docstring doctest `count_upper("AbEcIdOfU") -> 4`. The string is `A b E c I d O f U`, whose even indices are `A E I O U`, which gives 5. The doctest as written would fail, and both the doctest and the examples in this document should be corrected to `5`.
```
