# Developer Documentation

## Overview

This code provides a function `count_upper` that counts the number of uppercase vowels in even indices of a given string. It includes a set of uppercase vowels for quick lookup and a loop to iterate over the string at even indices, checking if each character is an uppercase vowel.

## Function / Class Reference

### Function: count_upper

**Signature**: `count_upper(s: str) -> int`

**Description**: This function takes a string `s` as input and returns the number of uppercase vowels at even indices.

**Parameters**:
- `s` (str): The input string to be processed.

**Return Value**:
- int: The count of uppercase vowels at even indices.

**Example Usage**:
```python
print(count_upper('aBCdEf'))  # Output: 1
print(count_upper('abcdefg'))  # Output: 0
print(count_upper('dBBE'))  # Output: 0
```

## Edge Cases & Assumptions

1. **Empty String**: If the input string is empty, the function will return 0 since there are no characters to check.
2. **Non-Alphabetic Characters**: Non-alphabetic characters at even indices are ignored, and the function only counts uppercase vowels.
3. **Case-Sensitive**: Only uppercase vowels ('A', 'E', 'I', 'O', 'U') are counted, not lowercase vowels.

## Usage Example

```python
# Example usage of the count_upper function
result = count_upper('aBCdEf')
print(result)  # Output: 1
```