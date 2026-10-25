# Prompt: reverse_spec [call 001]

- model: `claude-haiku-5-5`
- max_tokens: 1024
- temperature: 0.7

---


You are a software architect reading an implementation and reconstructing its specification.

Study the following code carefully and write a precise, formal specification
describing what this code does — as if you were the original author writing
the spec *before* implementation.

Code:
def car_race_collision(n: int) -> int:
    """
    Count head-on collisions between two groups of cars on an infinitely long straight road.

    Setup: n cars drive left to right and n different cars drive right to left.
    All cars travel at the same speed. Every car starts far enough from the others
    that each left-to-right car meets each right-to-left car exactly once.

    Collision: a left-to-right car meets a right-to-left car. Cars are indestructible
    and keep their trajectories after a collision, so each pair collides exactly once.

    Args:
        n: number of cars in each direction. Must be a non-negative int.

    Returns:
        int: number of left-to-right/right-to-left pairs that collide, which is n * n.

    Raises:
        TypeError: if n is not an int (bool is rejected).
        ValueError: if n is negative.
    """
    if not isinstance(n, int) or isinstance(n, bool):
        raise TypeError(f"n must be an int, got {type(n).__name__}")
    if n < 0:
        raise ValueError(f"n must be non-negative, got {n}")
    # Every left-to-right car passes every right-to-left car exactly once.
    return n * n

Write the specification in natural language. Cover:
1. Purpose — what problem does this solve?
2. Inputs — what parameters or data does it accept, including types and constraints?
3. Outputs — what does it return, including type and meaning?
4. Behaviour — the algorithm or logic, including edge cases and error conditions handled.
5. Assumptions — any implicit constraints or prerequisites the implementation relies on.

Be precise and complete. Do not describe implementation details (variable names,
language syntax). Describe *what* the code does, not *how*.
