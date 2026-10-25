## Overview
This Python code defines a function `uppercaseAsciiSum` that calculates the sum of the ASCII values of all uppercase characters in a given string. This function is useful for scenarios where you need to analyze the ASCII values of uppercase letters in text data.

## Function / Class Reference
### Function Signature
```python
def uppercaseAsciiSum(s: str) -> int:
```

### Description
The `uppercaseAsciiSum` function takes a single string `s` as input and returns the sum of the ASCII values of all uppercase characters in the string.

### Parameters
- `s` (str): The input string from which the sum of ASCII values of uppercase characters will be calculated.

### Return Value
- `int`: The sum of the ASCII values of all uppercase characters in the input string.

### Example Usage
```python
result = uppercaseAsciiSum("helloE")
print(result)  # Output: 69
```

## Edge Cases & Assumptions
- The function assumes that the input is a string. If a non-string input is provided, it will raise a `TypeError`.
- The function considers only uppercase letters (A-Z). Characters that are not uppercase letters (including lowercase letters and non-alphabetic characters) are ignored.
- The function returns the sum of ASCII values as an integer. If the input string does not contain any uppercase letters, the function will return 0.

## Usage Example
```python
# Calculate the sum of ASCII values of uppercase characters in a string
result = uppercaseAsciiSum("helloE")
print(result)  # Output: 69

# Calculate the sum of ASCII values of uppercase characters in another string
result = uppercaseAsciiSum("woArBld")
print(result)  # Output: 131
```