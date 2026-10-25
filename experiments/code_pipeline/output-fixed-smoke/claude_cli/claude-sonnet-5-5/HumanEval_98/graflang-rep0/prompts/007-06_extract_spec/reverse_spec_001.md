# Prompt: reverse_spec [call 001]

- model: `claude-sonnet-5-5`
- max_tokens: 1024
- temperature: 0.7

---


You are a software architect reading an implementation and reconstructing its specification.

Study the following code carefully and write a precise, formal specification
describing what this code does — as if you were the original author writing
the spec *before* implementation.

Code:
from typing import Final

UPPER_VOWELS: Final[frozenset] = frozenset("AEIOU")


def count_upper(s):
    """
    Count the uppercase vowels (A, E, I, O, U) at even indices of s.

    Indices are 0-based, so index 0 counts as even. Only ASCII uppercase
    vowels are counted; accented letters such as 'É' are not. Lowercase
    vowels, consonants and non-letter characters are ignored.

    Only str input is supported; anything else raises TypeError.

    For example:
    count_upper('aBCdEf') returns 1
    count_upper('abcdefg') returns 0
    count_upper('dBBE') returns 0
    count_upper('') returns 0
    """
    if not isinstance(s, str):
        raise TypeError(f"s must be a str, got {type(s).__name__}")
    return sum(1 for c in s[::2] if c in UPPER_VOWELS)

Write the specification in natural language. Cover:
1. Purpose — what problem does this solve?
2. Inputs — what parameters or data does it accept, including types and constraints?
3. Outputs — what does it return, including type and meaning?
4. Behaviour — the algorithm or logic, including edge cases and error conditions handled.
5. Assumptions — any implicit constraints or prerequisites the implementation relies on.

Be precise and complete. Do not describe implementation details (variable names,
language syntax). Describe *what* the code does, not *how*.
