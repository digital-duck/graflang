## Overview

`count_upper` counts the uppercase ASCII vowels (`A`, `E`, `I`, `O`, `U`) found at even, 0-based indices of a string (0, 2, 4, …). It slices the string with `s[::2]` and counts matches against a frozenset. It also validates its input type up front, so a non-string argument fails clearly instead of producing a misleading result.

## Function / Class Reference

### `count_upper(s: str) -> int`

Counts uppercase vowels at even indices of `s`.

**Parameters**
- `s` (`str`): The string to scan.

**Returns**
- `int`: The number of characters at positions 0, 2, 4, … that are one of `A`, `E`, `I`, `O`, `U`.

**Raises**
- `TypeError`: If `s` is not a `str`. The message names the actual type received.

**Examples**
```python
count_upper('aBCdEf')   # 1  (only 'E' at index 4)
count_upper('abcdefg')  # 0
count_upper('dBBE')     # 0  ('E' is at odd index 3)
```

### `count_uppercase_vowels_at_even_indices`

A module-level alias for `count_upper`, with the same behavior and signature.

### `_UPPER_VOWELS`

A private module constant, `frozenset("AEIOU")`. It is not part of the public API.

### `test_count_upper()`

A self-contained test function that uses plain `assert` statements. It covers empty input, single characters, the specification examples, non-ASCII letters and the `TypeError` case. It can be run directly or collected by pytest.

## Edge Cases & Assumptions

- **Indexing is 0-based.** The first character is at even index 0 and is counted if it is an uppercase vowel.
- **Only uppercase ASCII vowels count.** Lowercase vowels never match (`'aAeEiI'` → 0). `Y` is not treated as a vowel. Non-ASCII uppercase vowels such as `É` or `Ü` are not counted (`'AÉEÜ'` → 2, from `A` at 0 and `E` at 2).
- **Empty string** returns `0`.
- **Strict type check.** Any non-`str` input, including `None`, `bytes` and lists, raises `TypeError`. Subclasses of `str` are accepted.
- **Memory.** `s[::2]` creates a half-length copy of the string. This is negligible for typical inputs.

## Usage Example

```python
from your_module import count_upper

print(count_upper("EAEAEA"))  # 3 (E, E, E at indices 0, 2, 4)
print(count_upper("BAB"))     # 0 ('A' is at odd index 1)
print(count_upper(""))        # 0

try:
    count_upper(None)
except TypeError as e:
    print(e)  # s must be a str, got NoneType
```