# Prompt: refactor [call 001]

- model: `qwen2.5-coder-16k`
- max_tokens: 2048
- temperature: 0.7

---


You are an expert python developer improving code based on feedback.

Specification (the function name and signature must match it exactly):
Implement the following Python function. Return the complete function, including its signature and any imports it needs.


def digitSum(s):
    """Task
    Write a function that takes a string as input and returns the sum of the upper characters only'
    ASCII codes.

    Examples:
        digitSum("") => 0
        digitSum("abAB") => 131
        digitSum("abcCd") => 67
        digitSum("helloE") => 69
        digitSum("woArBld") => 131
        digitSum("aAaaaXa") => 153
    """

Original code:
def digitSum(s):
    return sum(ord(c) for c in s if c.isupper())

Review feedback:
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

Test failures (if any):


Rewrite the code addressing all feedback and fixing all test failures.
Return only the improved python code — no explanation, no markdown fences.
