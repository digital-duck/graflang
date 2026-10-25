def uppercaseAsciiSum(s):
    return sum(ord(c) for c in s if c.isupper())