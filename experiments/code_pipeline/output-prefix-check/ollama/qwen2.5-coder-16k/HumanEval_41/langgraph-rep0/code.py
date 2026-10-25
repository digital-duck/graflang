def count_car_collisions(n: int) -> int:
    """
    Calculate the total number of collisions between two sets of n cars each,
    one set driving left to right and the other set driving right to left on an infinitely long straight road.
    All cars move at the same speed and continue their path post-collision.
    """
    if not isinstance(n, int) or n < 0:
        raise ValueError("Input must be a non-negative integer")
    return n * n