[READY]
Build `car_race_collision(n: int) -> int`, which returns the number of collisions between n left-to-right cars and n right-to-left cars, which is n².

STRUCTURED SPEC:
1. **Signature:** `def car_race_collision(n: int) -> int:` with a docstring. No imports are needed.
2. **Input:** `n` is a non-negative integer, the count of cars in each direction. Negative input is outside the spec; the implementation may raise or return 0.
3. **Output:** An integer, the total number of collisions.
4. **Collision model:** Cars never stop or change course, and every car is eventually passed by every car going the opposite way. Each (left-to-right, right-to-left) pair collides exactly once.
5. **Formula:** The result is `n * n`. Counting pairs gives the same answer, so the spec does not need to justify it further.
6. **Edge case:** `car_race_collision(0)` returns `0`.
7. **Acceptance checks:** `car_race_collision(1) == 1`, `car_race_collision(2) == 4`, and `car_race_collision(10) == 100`.