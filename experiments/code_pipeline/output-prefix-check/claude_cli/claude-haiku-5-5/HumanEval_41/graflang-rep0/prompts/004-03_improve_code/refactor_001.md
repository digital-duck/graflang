# Prompt: refactor [call 001]

- model: `claude-haiku-5-5`
- max_tokens: 2048
- temperature: 0.7

---


You are an expert python developer improving code based on feedback.

Specification (the function name and signature must match it exactly):
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

Original code:
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
    if n < 0:
        raise ValueError("n must be non-negative")
    # Every left-to-right car passes every right-to-left car exactly once.
    return n * n

Review feedback:
- **Logic is correct under the stated model.** Each left-to-right car meets each right-to-left car exactly once because the cars never change trajectory, so `n * n` is right. The comment states the invariant, which is the part a reader needs.

- **The type hint is not enforced.** `car_race_collision(True)` returns `1`, `car_race_collision(2.0)` returns `4.0`, and a float like `2.5` returns `6.25`. Either validate with `if not isinstance(n, int) or isinstance(n, bool): raise TypeError(...)`, or accept that the hint is advisory and say so.

- **Negative-input check is good, but the message should name the value.** `f"n must be non-negative, got {n}"` makes failures easier to diagnose.

- **The docstring leaves out the assumption the answer depends on.** It should say that all cars start far enough apart that every left-to-right/right-to-left pair meets exactly once, and that cars keep their trajectories after colliding. Right now a reader has to infer that from "very far" and "continue moving."

- **The docstring says "outputs" where it should say "returns".** Add a `Returns:` line stating the type and meaning, for example `int: number of left-to-right/right-to-left pairs that collide`.

- **The name `car_race_collision` suggests a single collision event.** `count_head_on_collisions` or `count_pairwise_collisions` says what is returned. The parameter `n` could be `cars_per_direction` for the same reason.

- **The "Imagine..." prose is hard to scan.** A short spec (setup, what counts as a collision, return value) reads more like a contract. This is a clarity point, not a style preference.

- **No tests are shown.** At minimum cover `n=0` (returns 0), `n=1` (returns 1), a negative value (raises), and one larger value such as `n=3` (returns 9). Those cases pin down the boundary behaviour the docstring implies.

Test failures (if any):


Rewrite the code addressing all feedback and fixing all test failures.
Return only the improved python code — no explanation, no markdown fences.
