import unicodedata  # noqa: F401  (not needed: the contract is ASCII-only)

_UPPER_VOWELS = frozenset("AEIOU")


def count_upper(s):
    """
    Given a string s, count the number of uppercase vowels in even indices.

    Indices are 0-based, so the "even indices" are the 1st, 3rd, 5th, ...
    characters of s (positions 0, 2, 4, ...). Only the ASCII uppercase
    vowels 'A', 'E', 'I', 'O', 'U' are counted; non-ASCII letters such as
    'É' and all other characters are ignored.

    s must be a str; anything else raises TypeError.

    For example:
    count_upper('aBCdEf') returns 1
    count_upper('abcdefg') returns 0
    count_upper('dBBE') returns 0
    count_upper('') returns 0
    count_upper('A') returns 1
    count_upper('aA') returns 0
    count_upper('AEIOU') returns 3
    count_upper('aeiou') returns 0
    count_upper('1A!E') returns 0
    """
    if not isinstance(s, str):
        raise TypeError("s must be a str, got %s" % type(s).__name__)
    return sum(ch in _UPPER_VOWELS for ch in s[::2])