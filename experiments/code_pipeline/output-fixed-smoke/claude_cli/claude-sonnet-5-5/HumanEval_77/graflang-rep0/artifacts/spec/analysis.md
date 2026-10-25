[READY]
Build `iscube(a)`, which returns True if the integer `a` equals n³ for some integer n (negative, zero, or positive) and False otherwise.

Analysis: The purpose is a single, concrete goal. The input is an integer, and the output is a bool. The examples cover positive and negative cubes, zero, and non-cubes. The note that input is always valid removes the need for type checking. The only real pitfalls are floating-point error in cube roots and handling of negative numbers, and both can be handled with reasonable assumptions.

STRUCTURED SPEC:
1. Define `def iscube(a):` taking a single integer `a`. It may be negative, zero, or positive.
2. Return `True` if there is an integer `n` with `n**3 == a`, and `False` otherwise.
3. Handle negatives by symmetry: `iscube(-a)` equals `iscube(a)`, so `-1` and `-8` return True.
4. Return True for `0`, since 0 is 0³.
5. Use an exact result. Use integer arithmetic or round the float cube root and verify it with `round(abs(a) ** (1/3)) ** 3 == abs(a)`, so that large values don't suffer from float error.
6. Skip input validation, since the input is guaranteed valid.
7. Meet the examples: `iscube(1)` is True, `iscube(2)` is False, `iscube(-1)` is True, `iscube(64)` is True, `iscube(0)` is True, `iscube(180)` is False.
8. Return a bool. The full function includes its signature and any imports it needs, and none are required for the basic approach.