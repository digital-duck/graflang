# car_race_collision

## Overview

`car_race_collision` returns the number of head-on collisions in an idealized road scenario. Two groups of `n` cars each travel along an infinitely long straight road, one group left to right and the other right to left, all at the same speed. Cars are indestructible, so they keep their trajectories after a collision. Each left-to-right car therefore meets each right-to-left car exactly once, and the total is `n * n`. The function computes this closed form directly rather than simulating motion.

## Function Reference

### `car_race_collision(n: int) -> int`

Counts the collisions between `n` left-to-right cars and `n` right-to-left cars.

**Parameters**

| Name | Type | Description |
|------|------|-------------|
| `n` | `int` | Number of cars in each direction. Must be a non-negative `int`. |

**Returns**

`int`: the number of left-to-right/right-to-left pairs that collide, equal to `n * n`.

**Raises**

- `TypeError`: if `n` is not an `int`. `bool` values are rejected even though `bool` subclasses `int`.
- `ValueError`: if `n` is negative.

**Example**

```python
car_race_collision(0)   # 0
car_race_collision(3)   # 9
car_race_collision(10)  # 100
```

## Edge Cases & Assumptions

- **Model, not simulation.** The result is the closed form `n * n`. Positions, speeds, and timing are not modelled. The function relies on the premise that every pair crosses exactly once.
- **Equal speeds and a straight, infinite road.** The problem statement guarantees these. If speeds differed or the road were bounded, the count would no longer be `n * n`.
- **Each pair counts once.** Because cars are indestructible, a car is never removed after a collision, so no pair is counted twice and none is skipped.
- **`n = 0`** returns `0`.
- **Type strictness.** `bool` is rejected. Other `int` subclasses are accepted. Integer-like types that are not `int` subclasses, such as `numpy.int64`, are rejected with `TypeError`.
- **No upper bound.** Very large `n` returns a large Python integer without overflow, but the result grows quadratically.

## Usage Example

```python
from collections import Counter  # not needed; shown only for a self-contained check

def car_race_collision(n: int) -> int:
    if not isinstance(n, int) or isinstance(n, bool):
        raise TypeError(f"n must be an int, got {type(n).__name__}")
    if n < 0:
        raise ValueError(f"n must be non-negative, got {n}")
    return n * n


if __name__ == "__main__":
    for n in (0, 1, 3, 10):
        print(f"{n} cars per direction -> {car_race_collision(n)} collisions")

    try:
        car_race_collision(-1)
    except ValueError as exc:
        print(f"Rejected: {exc}")
```

Expected output:

```
0 cars per direction -> 0 collisions
1 cars per direction -> 1 collisions
3 cars per direction -> 9 collisions
10 cars per direction -> 100 collisions
Rejected: n must be non-negative, got -1
```