# Specification: `car_race_collision`

## 1. Purpose

The function returns the number of head-on collisions in an idealized road-race scenario. A group of `n` cars travels left to right and a second group of `n` different cars travels right to left, on an infinitely long straight road at a common speed. Each left-to-right car meets each right-to-left car exactly once, and every such meeting is a collision. The function answers "how many collisions occur?" by a closed-form count. It does not simulate motion, positions, or times.

## 2. Inputs

- **`n`**: a single parameter.
  - **Type:** must be an `int`. A `bool` is rejected even though it is a subtype of `int`.
  - **Constraint:** must be non-negative (`n ≥ 0`).
  - **Meaning:** the number of cars in each direction. The two groups are disjoint, so the total number of cars is `2n`.

No other inputs, state, or external data are used.

## 3. Outputs

- **Type:** `int`.
- **Value:** `n²`, the number of (left-to-right, right-to-left) car pairs. This is the total number of collisions, given that each pair collides exactly once.
- **Special cases:** `n = 0` yields `0`. For `n = 1`, the result is `1`.
- The result is always non-negative and depends only on `n`.

## 4. Behaviour

**Validation (performed first, in this order):**
1. If `n` is not an `int`, or is a `bool`, the function raises `TypeError`. The message names the actual type of `n`.
2. If `n` is an `int` but is negative, the function raises `ValueError`. The message reports the value.

**Computation:** if validation passes, the function returns `n × n`. The justification is that every one of the `n` left-to-right cars meets every one of the `n` right-to-left cars exactly once, and the pairs are distinct.

**Edge cases:**
- `n = 0`: no cars in either direction, so no collisions, and the result is `0`.
- Large `n`: the result grows quadratically. No overflow handling is applied beyond what Python `int` provides.
- Floats such as `3.0`, strings, `None`, and other non-`int` values are rejected with `TypeError`. The function does not coerce them.

**Error conditions:** `TypeError` for non-int or bool input; `ValueError` for negative int input. No other exceptions are raised by the function.

**Physical model (as stated by the docstring, not computed by the code):**
- Cars never leave the road, are indestructible, and keep their trajectories after collision. A collision does not alter any later meeting.
- Because each pair meets once and the count is unaffected by collisions, the count is the same whatever the timing of the collisions.

## 5. Assumptions

1. **Geometry:** the road is infinite and straight, and the cars move in opposite directions along it.
2. **Equal speeds:** all cars travel at the same speed, so the two groups' relative motion is fixed.
3. **Initial placement:** the cars start far enough apart that every left-to-right car eventually meets every right-to-left car, and no two cars start at the same point.
4. **Exactly-once meeting:** each left-to-right/right-to-left pair meets exactly once. This relies on the cars being indestructible, never leaving the road, and keeping their paths after collisions.
5. **Distinctness:** the `n` cars in each group are distinct from each other and from the other group. Collisions are counted only between opposite-direction cars. Cars travelling in the same direction are assumed never to be counted as collisions.
6. **Non-simulation:** the function trusts the model rather than verifying it. Its correctness is a property of the model's assumptions, not something the code checks at runtime.
7. **Integer domain:** `n` is a finite non-negative integer. The result `n²` is exact in Python's arbitrary-precision integers.