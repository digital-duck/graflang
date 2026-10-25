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