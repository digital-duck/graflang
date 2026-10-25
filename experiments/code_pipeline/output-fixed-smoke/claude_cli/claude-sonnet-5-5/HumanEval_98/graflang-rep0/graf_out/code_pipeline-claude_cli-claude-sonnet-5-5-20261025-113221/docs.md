## Overview

`count_upper(s)` counts the uppercase vowels (`A`, `E`, `I`, `O`, `U`) that sit at even, 0-based indices of a string. It takes every second character starting at index 0 and checks each against a fixed set of uppercase vowels. The vowel set is a module-level constant, `UPPER_VOWELS`, so it is built once and not on each call.

## Function / Class Reference

### `count_upper(s)`

```python
def count_upper(s) -> int
```

Counts the uppercase ASCII vowels at even indices of `s`.

**Parameters**

| Name | Type  | Description                  |
|------|-------|------------------------------|
| `s`  | `str` | The string to scan. Required. |

**Returns**: `int`. The number of characters at indices 0, 2, 4, … that are in `AEIOU`. Returns `0` for an empty string.

**Raises**: `TypeError` if `s` is not a `str`. The message is `s must be a str, got <typename>`.

**Examples**

```python
count_upper('aBCdEf')    # 1  (only 'E' at index 4 qualifies; 'B' and 'C' are consonants)
count_upper('abcdefg')   # 0
count_upper('dBBE')      # 0  ('E' is at odd index 3)
count_upper('')          # 0
```

### `UPPER_VOWELS`

`Final[frozenset]` containing `"A"`, `"E"`, `"I"`, `"O"`, `"U"`. It is a module-level constant and shouldn't be modified.

## Edge Cases & Assumptions

- **Indexing is 0-based.** Index 0 counts as even.
- **ASCII uppercase vowels only.** Accented capitals such as `'É'` are not counted. Lowercase vowels, consonants, digits, whitespace and punctuation are ignored.
- **`'Y'` is not a vowel** for this function.
- **Strict type check.** Any non-`str` input (`None`, `bytes`, lists, ints) raises `TypeError`. Subclasses of `str` are accepted.
- **Cost.** It runs in O(n) time, and the `s[::2]` slice makes a copy of about n/2 characters.

## Usage Example

```python
from typing import Final

UPPER_VOWELS: Final[frozenset] = frozenset("AEIOU")


def count_upper(s):
    if not isinstance(s, str):
        raise TypeError(f"s must be a str, got {type(s).__name__}")
    return sum(1 for c in s[::2] if c in UPPER_VOWELS)


print(count_upper("AbEdIf"))   # 3 -> 'A' (0), 'E' (2), 'I' (4)
print(count_upper("bAcEd"))    # 0 -> vowels are at odd indices 1 and 3

try:
    count_upper(None)
except TypeError as exc:
    print(exc)                 # s must be a str, got NoneType
```