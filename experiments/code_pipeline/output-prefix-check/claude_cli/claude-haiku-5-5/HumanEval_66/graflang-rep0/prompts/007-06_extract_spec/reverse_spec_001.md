# Prompt: reverse_spec [call 001]

- model: `claude-haiku-5-5`
- max_tokens: 1024
- temperature: 0.7

---


You are a software architect reading an implementation and reconstructing its specification.

Study the following code carefully and write a precise, formal specification
describing what this code does — as if you were the original author writing
the spec *before* implementation.

Code:
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

Write the specification in natural language. Cover:
1. Purpose — what problem does this solve?
2. Inputs — what parameters or data does it accept, including types and constraints?
3. Outputs — what does it return, including type and meaning?
4. Behaviour — the algorithm or logic, including edge cases and error conditions handled.
5. Assumptions — any implicit constraints or prerequisites the implementation relies on.

Be precise and complete. Do not describe implementation details (variable names,
language syntax). Describe *what* the code does, not *how*.
