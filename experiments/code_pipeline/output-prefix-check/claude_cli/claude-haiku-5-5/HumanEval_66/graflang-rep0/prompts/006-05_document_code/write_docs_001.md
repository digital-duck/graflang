# Prompt: write_docs [call 001]

- model: `claude-haiku-5-5`
- max_tokens: 2048
- temperature: 0.7

---


You are a technical writer generating developer documentation for python code.

Original specification:
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

Implemented python code:
def digitSum(s):
    """Return the sum of the ASCII codes of the uppercase ASCII letters in s.

    Only 'A' through 'Z' are counted. Every other character, including
    non-ASCII uppercase letters, is ignored. Raises TypeError if s is not a str.

    >>> digitSum("")
    0
    >>> digitSum("abAB")
    131
    >>> digitSum("abcCd")
    67
    >>> digitSum("helloE")
    69
    >>> digitSum("woArBld")
    131
    >>> digitSum("aAaaaXa")
    153
    >>> digitSum("\u00c9")
    0
    >>> digitSum(["a", "B"])
    Traceback (most recent call last):
        ...
    TypeError: digitSum expects a str, got list
    """
    # Name kept as digitSum because the specification requires it. The function
    # sums the codes of uppercase ASCII letters, not digits.
    if not isinstance(s, str):
        raise TypeError(f"digitSum expects a str, got {type(s).__name__}")
    return sum(ord(c) for c in s if 'A' <= c <= 'Z')

Write clear, complete documentation in Markdown. Include:

## Overview
One paragraph describing what this code does and why.

## Function / Class Reference
For each public function or class: signature, description, parameters, return value, example usage.

## Edge Cases & Assumptions
Any notable constraints, limitations, or assumptions the implementation makes.

## Usage Example
A short, runnable python example demonstrating typical use.

Be concise and accurate. Do not pad with filler.
