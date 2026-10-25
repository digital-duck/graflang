# Prompt: reverse_spec [call 001]

- model: `claude-sonnet-5-5`
- max_tokens: 1024
- temperature: 0.7

---


You are a software architect reading an implementation and reconstructing its specification.

Study the following code carefully and write a precise, formal specification
describing what this code does — as if you were the original author writing
the spec *before* implementation.

Code:
def is_cube(n):
    """Return True if the integer ``n`` is the cube of some integer.

    Only ``int`` values are accepted (``bool`` counts as an int). Any other
    type, including floats, raises ``TypeError``. Uses exact integer
    arithmetic, so it is correct for arbitrarily large integers.
    """
    if not isinstance(n, int):
        raise TypeError("is_cube expects an int, got %s" % type(n).__name__)

    # (-k)**3 == -(k**3), so n is a cube exactly when |n| is.
    magnitude = abs(n)

    # Find an upper bound for the cube root by doubling.
    low, high = 0, 1
    while high ** 3 < magnitude:
        high *= 2

    # Binary search for the smallest integer whose cube is >= magnitude.
    while low < high:
        mid = (low + high) // 2
        if mid ** 3 < magnitude:
            low = mid + 1
        else:
            high = mid

    return low ** 3 == magnitude


iscube = is_cube


def _run_tests():
    assert is_cube(0)
    assert is_cube(1)
    assert is_cube(-1)
    assert is_cube(64)
    assert is_cube(-64)
    assert not is_cube(2)
    assert not is_cube(63)
    assert not is_cube(65)
    assert not is_cube(180)
    assert is_cube(True)
    assert is_cube(2 ** 150)  # 2**150 == (2**50)**3
    # Largest cube below 2**53, exactly representable as a float.
    root = int((2 ** 53) ** (1 / 3))
    while (root + 1) ** 3 < 2 ** 53:
        root += 1
    assert is_cube(root ** 3)
    assert not is_cube(root ** 3 + 1)
    # Cubes well above 1e47, where the float estimate fails.
    assert is_cube((10 ** 17 + 1) ** 3)
    assert is_cube(-((10 ** 17 + 1) ** 3))
    assert not is_cube((10 ** 17 + 1) ** 3 + 1)
    # Beyond float range (> 1e308).
    assert is_cube(10 ** 309)  # (10**103)**3
    assert not is_cube(10 ** 309 + 1)
    for bad in (0.125, 8.0, float("nan"), float("inf"), "8", None):
        try:
            is_cube(bad)
        except TypeError:
            pass
        else:
            raise AssertionError("expected TypeError for %r" % (bad,))


if __name__ == "__main__":
    _run_tests()

Write the specification in natural language. Cover:
1. Purpose — what problem does this solve?
2. Inputs — what parameters or data does it accept, including types and constraints?
3. Outputs — what does it return, including type and meaning?
4. Behaviour — the algorithm or logic, including edge cases and error conditions handled.
5. Assumptions — any implicit constraints or prerequisites the implementation relies on.

Be precise and complete. Do not describe implementation details (variable names,
language syntax). Describe *what* the code does, not *how*.
