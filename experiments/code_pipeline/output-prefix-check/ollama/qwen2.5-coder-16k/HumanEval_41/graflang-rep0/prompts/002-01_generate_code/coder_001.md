# Prompt: coder [call 001]

- model: `qwen2.5-coder-16k`
- max_tokens: 2048
- temperature: 0.7

---


You are an expert python developer.

Write clean, correct, well-structured python code for the following specification.
Return only the code — no explanation, no markdown fences.

Specification:
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

Previous attempt (empty on the first attempt):


Its test result (empty on the first attempt):


If there is a previous attempt, fix the failures its test result reports. Whatever you write, keep the function name and
the signature exactly as the specification gives them.
