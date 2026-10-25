# digitSum

## Overview

`digitSum` returns the sum of the ASCII codes of the uppercase letters (`A` through `Z`) in a string. All other characters are ignored, including lowercase letters, digits, punctuation, and non-ASCII uppercase letters such as `É`. The function is useful for checksum-style string scoring and as a small exercise in filtering and aggregating characters. Despite its name, it does not sum digits. The name is kept because the original specification requires it.

## Function Reference

### `digitSum(s)`

```python
def digitSum(s: str) -> int
```

Returns the sum of `ord(c)` for each character `c` in `s` where `'A' <= c <= 'Z'`.

**Parameters**

| Name | Type | Description |
|------|------|-------------|
| `s` | `str` | The input string. Any length, including empty. |

**Returns**

| Type | Description |
|------|-------------|
| `int` | The sum of ASCII codes of uppercase `A`–`Z` characters in `s`. Returns `0` if there are none. |

**Raises**

| Exception | Condition |
|-----------|-----------|
| `TypeError` | `s` is not an instance of `str`. The message is `digitSum expects a str, got <type name>`. |

**Examples**

```python
>>> digitSum("")
0
>>> digitSum("abAB")      # 'A' (65) + 'B' (66)
131
>>> digitSum("abcCd")     # 'C' (67)
67
>>> digitSum("helloE")    # 'E' (69)
69
>>> digitSum("aAaaaXa")   # 'A' (65) + 'X' (88)
153
>>> digitSum("\u00c9")    # non-ASCII uppercase is ignored
0
```

## Edge Cases & Assumptions

- **Empty string** returns `0`.
- **ASCII only.** Only code points 65–90 count. Non-ASCII uppercase letters (e.g. `É`, `Ω`) contribute nothing.
- **Single-character comparison.** Iterating over a `str` yields one-character strings, so the range check `'A' <= c <= 'Z'` is a valid character test.
- **Type strictness.** Only `str` is accepted. Other iterables, such as a list of characters, raise `TypeError` rather than being coerced. `bytes` is also rejected, since iterating over `bytes` would yield integers.
- **No digit handling.** Digits (`0`–`9`) are not summed. The name `digitSum` is misleading and is retained only for compatibility with the specification.
- **Return size.** Python integers are unbounded, so long inputs do not overflow. The maximum contribution per character is 90 (`Z`).
- **Performance.** The function is O(n) in the length of `s` and uses constant extra memory apart from the generator.

## Usage Example

```python
def digitSum(s):
    if not isinstance(s, str):
        raise TypeError(f"digitSum expects a str, got {type(s).__name__}")
    return sum(ord(c) for c in s if 'A' <= c <= 'Z')


if __name__ == "__main__":
    samples = ["", "abAB", "helloE", "woArBld"]
    for text in samples:
        print(f"{text!r:12} -> {digitSum(text)}")

    try:
        digitSum(["a", "B"])
    except TypeError as exc:
        print(f"Error: {exc}")
```

Output:

```
''           -> 0
'abAB'       -> 131
'helloE'     -> 69
'woArBld'    -> 131
Error: digitSum expects a str, got list
```