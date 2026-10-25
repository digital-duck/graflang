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