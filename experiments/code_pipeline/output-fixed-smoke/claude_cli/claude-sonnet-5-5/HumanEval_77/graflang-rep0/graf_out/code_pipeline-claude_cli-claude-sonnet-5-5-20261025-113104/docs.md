## Overview

`is_cube(n)` returns `True` if the integer `n` is the cube of some integer (positive, negative, or zero). It uses only integer arithmetic (a doubling search for an upper bound, then a binary search for the integer cube root), so it stays exact for arbitrarily large inputs. Floating-point cube roots lose precision above about 2**53 and overflow past about 1e308. `iscube` is an alias that matches the name in the original specification.

## Function / Class Reference

### `is_cube(n)`

Alias: `iscube = is_cube`

**Description:** Checks whether `n == k**3` for some integer `k`. It relies on `(-k)**3 == -(k**3)`, so it tests `abs(n)` and handles negative inputs the same way as positive ones.

**Parameters:**

| Name | Type  | Description                                            |
|------|-------|--------------------------------------------------------|
| `n`  | `int` | The value to test. `bool` is accepted because it is a subclass of `int`. |

**Returns:** `bool`. `True` if `n` is a perfect cube, otherwise `False`.

**Raises:** `TypeError` if `n` is not an `int` (floats, strings, `None`, `nan` and `inf` all raise).

**Algorithm:**
1. Double `high` from 1 until `high**3 >= abs(n)`.
2. Binary search `[0, high]` for the smallest integer whose cube is `>= abs(n)`.
3. Return whether that integer's cube equals `abs(n)`.

Complexity is O(log |n|) iterations, each with a big-integer multiplication.

**Examples:**

```python
is_cube(64)    # True  (4**3)
is_cube(-64)   # True  ((-4)**3)
is_cube(180)   # False
is_cube(0)     # True
is_cube(True)  # True  (True == 1)
```

### `_run_tests()`

Private self-test, run when the file is executed as a script. It uses plain `assert` statements and raises `AssertionError` on failure. It covers small values, negatives, `2**150`, cubes near `2**53`, cubes above 1e47, values beyond float range (`10**309`), and the `TypeError` cases.

## Edge Cases & Assumptions

- **Strict typing:** `8.0` and `0.125` raise `TypeError` rather than being coerced, even though `8.0` is mathematically a cube. This is stricter than the original spec, which says the input is always a valid integer.
- **`bool`:** `True` and `False` are treated as `1` and `0`.
- **Zero:** `0` is a cube (`0**3`). With `magnitude == 0`, `high` stays at 1 and the search returns `low == 0`.
- **Negative numbers:** Always evaluated through `abs(n)`.
- **Large integers:** There is no size limit besides memory and time. Tests cover values above `10**309`.
- **Name:** The primary name is `is_cube`. `iscube` is provided only as an alias.

## Usage Example

```python
from your_module import is_cube, iscube

for value in (1, 2, -1, 64, 0, 180, 10**309):
    print(value if value < 10**6 else "10**309", is_cube(value))

assert iscube(-27) is True

try:
    is_cube(8.0)
except TypeError as e:
    print("TypeError:", e)   # is_cube expects an int, got float
```