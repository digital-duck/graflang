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