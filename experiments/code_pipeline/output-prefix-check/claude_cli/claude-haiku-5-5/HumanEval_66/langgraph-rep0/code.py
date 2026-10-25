import unittest


def digitSum(s):
    """Return the sum of the ASCII codes of the uppercase letters in ``s``.

    Only the ASCII capitals 'A' through 'Z' are counted, each contributing its
    ``ord`` value. All other characters are ignored, including lowercase
    letters, digits, punctuation, whitespace and non-ASCII uppercase letters
    such as 'É'. A string with no capitals, including the empty string,
    returns 0.

    The name comes from the original specification. The function sums
    uppercase letters, not digits.

    Raises:
        TypeError: if ``s`` is not a str.

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
    >>> digitSum("É")
    0
    >>> digitSum(None)
    Traceback (most recent call last):
    ...
    TypeError: digitSum expects a str, got NoneType
    """
    if not isinstance(s, str):
        raise TypeError(f"digitSum expects a str, got {type(s).__name__}")
    # Deliberate explicit ASCII range, not str.isupper(). isupper() also accepts
    # non-ASCII capitals such as 'É' and 'Σ', which would change the result.
    return sum(ord(c) for c in s if 'A' <= c <= 'Z')


class DigitSumTests(unittest.TestCase):
    def test_spec_examples(self):
        cases = {
            "": 0,
            "abAB": 131,
            "abcCd": 67,
            "helloE": 69,
            "woArBld": 131,
            "aAaaaXa": 153,
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(digitSum(text), expected)

    def test_non_ascii_uppercase_is_ignored(self):
        self.assertEqual(digitSum("É"), 0)
        self.assertEqual(digitSum("ΣA"), 65)

    def test_non_string_input_raises(self):
        for value in (None, 0, 65, ["A"]):
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    digitSum(value)


if __name__ == "__main__":
    import doctest

    doctest.testmod()
    unittest.main()