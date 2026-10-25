# Prompt: run_tests [call 001]

- model: `claude-haiku-5-5`
- max_tokens: 1024
- temperature: 0.7

---


IMPORTANT: Your response MUST start with either [PASSED] or [FAILED] on the very first line.
Do not write any code. Do not write explanations before the verdict token.

You are a rigorous python code reviewer acting as an automated test suite.

Original specification:
Implement the following Python function. Return the complete function, including its signature and any imports it needs.



def car_race_collision(n: int):
    """
    Imagine a road that's a perfectly straight infinitely long line.
    n cars are driving left to right;  simultaneously, a different set of n cars
    are driving right to left.   The two sets of cars start out being very far from
    each other.  All cars move in the same speed.  Two cars are said to collide
    when a car that's moving left to right hits a car that's moving right to left.
    However, the cars are infinitely sturdy and strong; as a result, they continue moving
    in their trajectory as if they did not collide.

    This function outputs the number of such collisions.
    """

python code to evaluate:
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

Evaluate the code against the specification. Check:
1. Correctness — does it implement what the spec requires?
2. Edge cases — are obvious boundary conditions handled?
3. Logic errors — any off-by-one, wrong conditionals, or missing branches?
4. Return type / signature — does it match what the spec expects?
5. Language idioms — does it follow standard python conventions and best practices?

Output format — first line must be one of these two tokens, nothing else:
[PASSED]   ← if the code fully satisfies the specification with no critical issues
[FAILED]   ← followed by a concise bullet list of specific failures or missing requirements
