# Prompt: reverse_spec [call 007]

- model: `claude-sonnet-5-5`
- max_tokens: 1024
- temperature: 0.7

---


You are a software architect reading an implementation and reconstructing its specification.

Study the following code carefully and write a precise, formal specification
describing what this code does — as if you were the original author writing
the spec *before* implementation.

Code:
_UPPER_VOWELS = frozenset("AEIOU")


def count_upper(s: str) -> int:
    """Count uppercase vowels (A, E, I, O, U) at even indices of s.

    Indices are 0-based, so positions 0, 2, 4, ... are examined. Only the
    ASCII uppercase vowels A, E, I, O and U are counted; accented or other
    non-ASCII uppercase vowels (e.g. 'É') are ignored. Lowercase vowels and
    uppercase vowels at odd indices are not counted.

    Args:
        s: The string to examine. Must be a ``str``.

    Returns:
        The number of uppercase vowels found at even indices.

    Raises:
        TypeError: If ``s`` is not a ``str``.

    Examples:
        >>> count_upper("")
        0
        >>> count_upper("A")
        1
        >>> count_upper("a")
        0
        >>> count_upper("aBCdEf")
        1
        >>> count_upper("AbEcIdOfU")
        4
        >>> count_upper("aAeEiI")
        0
        >>> count_upper("bAdEfI")
        0
    """
    if not isinstance(s, str):
        raise TypeError(f"s must be a str, got {type(s).__name__}")
    return sum(ch in _UPPER_VOWELS for ch in s[::2])


count_uppercase_vowels_at_even_indices = count_upper

Write the specification in natural language. Cover:
1. Purpose — what problem does this solve?
2. Inputs — what parameters or data does it accept, including types and constraints?
3. Outputs — what does it return, including type and meaning?
4. Behaviour — the algorithm or logic, including edge cases and error conditions handled.
5. Assumptions — any implicit constraints or prerequisites the implementation relies on.

Be precise and complete. Do not describe implementation details (variable names,
language syntax). Describe *what* the code does, not *how*.
