import operator


def car_race_collision(n: int) -> int:
    """
    Imagine a road that's a perfectly straight, infinitely long line.
    There are n cars driving left to right and a different set of n cars driving
    right to left, so n is the number of cars in each direction, not the total.
    The two sets start very far apart. All cars move at the same speed.
    Two cars collide when a left-to-right car hits a right-to-left car.
    The cars are infinitely sturdy, so after a collision each car keeps its
    trajectory as if the collision had not happened.

    Assumptions:
    - Cars moving in the same direction never collide with each other.
    - Each left-to-right car meets each right-to-left car exactly once.

    Returns the total number of collisions between the two groups of cars.

    >>> car_race_collision(0)
    0
    >>> car_race_collision(1)
    1
    >>> car_race_collision(3)
    9
    >>> car_race_collision(-1)
    Traceback (most recent call last):
    ...
    ValueError: n must be non-negative
    >>> car_race_collision(True)
    Traceback (most recent call last):
    ...
    TypeError: n must be an integer, not bool
    """
    if isinstance(n, bool):
        raise TypeError("n must be an integer, not bool")
    n = operator.index(n)
    if n < 0:
        raise ValueError("n must be non-negative")
    # Each of the n rightward cars meets each of the n leftward cars exactly once.
    return n * n