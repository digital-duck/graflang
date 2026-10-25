def is_cube(n: int) -> bool:
    """Return True if n is the cube of some integer.

    Negative values are allowed, since the cube of a negative integer is
    negative (e.g. -8 == (-2) ** 3). Zero is a cube (0 == 0 ** 3).

    Uses an exact integer binary search, so it is correct for ints of any
    size and never converts to float.

    Raises TypeError if n is not an int (bool is rejected as well).
    """
    if not isinstance(n, int) or isinstance(n, bool):
        raise TypeError("n must be an integer, got %s" % type(n).__name__)

    # The cube of a negative integer is negative, so test |n|.
    target = abs(n)

    # Find an upper bound for the cube root by doubling.
    low, high = 0, 1
    while high ** 3 < target:
        high *= 2

    # Binary search for the smallest candidate whose cube is >= target.
    while low < high:
        mid = (low + high) // 2
        if mid ** 3 < target:
            low = mid + 1
        else:
            high = mid

    return low ** 3 == target


def iscube(a):
    """Alias kept for the original specification's function name."""
    return is_cube(a)