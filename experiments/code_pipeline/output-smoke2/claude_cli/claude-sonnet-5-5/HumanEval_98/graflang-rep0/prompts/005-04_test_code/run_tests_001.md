# Prompt: run_tests [call 001]

- model: `claude-sonnet-5-5`
- max_tokens: 1024
- temperature: 0.7

---


IMPORTANT: Your response MUST start with either [PASSED] or [FAILED] on the very first line.
Do not write any code. Do not write explanations before the verdict token.

You are a rigorous python code reviewer acting as an automated test suite.

Original specification:
Implement the following Python function. Return the complete function, including its signature and any imports it needs.


def count_upper(s):
    """
    Given a string s, count the number of uppercase vowels in even indices.
    
    For example:
    count_upper('aBCdEf') returns 1
    count_upper('abcdefg') returns 0
    count_upper('dBBE') returns 0
    """

python code to evaluate:
_UPPER_VOWELS = frozenset("AEIOU")


def count_upper(s: str) -> int:
    """Count uppercase vowels at even indices of s (0-based: positions 0, 2, 4, ...).

    Only the ASCII vowels 'A', 'E', 'I', 'O', 'U' are counted. 'Y' and
    non-ASCII uppercase vowels such as 'É' or 'Ü' are not counted.
    Raises TypeError if s is not a str.
    """
    if not isinstance(s, str):
        raise TypeError(f"s must be a str, got {type(s).__name__}")
    return sum(ch in _UPPER_VOWELS for ch in s[::2])


count_uppercase_vowels_at_even_indices = count_upper


def test_count_upper():
    assert count_upper("") == 0
    assert count_upper("A") == 1
    assert count_upper("b") == 0
    assert count_upper("aBCdEf") == 1
    assert count_upper("abcdefg") == 0
    assert count_upper("dBBE") == 0
    assert count_upper("EAEAEA") == 3
    assert count_upper("BAB") == 0
    assert count_upper("aAeEiI") == 0
    assert count_upper("BCDFG") == 0
    assert count_upper("ÉBÜB") == 0
    assert count_upper("AÉEÜ") == 2
    assert count_upper("YAY") == 0
    try:
        count_upper(None)
    except TypeError:
        pass
    else:
        raise AssertionError("expected TypeError")

Evaluate the code against the specification. Check:
1. Correctness — does it implement what the spec requires?
2. Edge cases — are obvious boundary conditions handled?
3. Logic errors — any off-by-one, wrong conditionals, or missing branches?
4. Return type / signature — does it match what the spec expects?
5. Language idioms — does it follow standard python conventions and best practices?

Output format — first line must be one of these two tokens, nothing else:
[PASSED]   ← if the code fully satisfies the specification with no critical issues
[FAILED]   ← followed by a concise bullet list of specific failures or missing requirements
