def iscube(a):
    a = abs(a)
    r = round(a ** (1 / 3))
    for c in (r - 1, r, r + 1):
        if c >= 0 and c ** 3 == a:
            return True
    return False