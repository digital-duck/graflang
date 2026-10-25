- The function `digitSum` is intended to calculate the sum of ASCII values of uppercase characters in a given string `s`. However, the name `digitSum` is misleading because it suggests the sum of digits, not ASCII values.
- The logic of the function is incorrect. It should sum the ASCII values of uppercase characters, not digits.

Here is the corrected version of the function:

```python
def uppercaseAsciiSum(s):
    return sum(ord(c) for c in s if c.isupper())
```

- The function now correctly sums the ASCII values of uppercase characters in the string `s`.
- The function name has been changed to `uppercaseAsciiSum` to better reflect its purpose.
- No additional edge cases were identified in the provided function, but consider adding a check for an empty string to return 0, which could be considered a valid edge case for this function.