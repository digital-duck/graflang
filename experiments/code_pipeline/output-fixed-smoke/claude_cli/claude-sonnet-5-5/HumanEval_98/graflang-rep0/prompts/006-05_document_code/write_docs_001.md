# Prompt: write_docs [call 001]

- model: `claude-sonnet-5-5`
- max_tokens: 2048
- temperature: 0.7

---


You are a technical writer generating developer documentation for python code.

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

Implemented python code:
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
