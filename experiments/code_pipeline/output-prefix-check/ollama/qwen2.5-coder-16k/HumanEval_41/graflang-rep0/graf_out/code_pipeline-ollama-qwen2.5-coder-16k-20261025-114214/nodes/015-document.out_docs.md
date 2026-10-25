## Overview
The `car_race_collision` function calculates the number of collisions between two sets of cars driving in opposite directions on a straight, infinitely long road. Given that each car in one set collides with each car in the opposite set, the function returns the total number of collisions.

## Function / Class Reference
### car_race_collision(n: int) -> int
Computes the number of collisions between two sets of `n` cars each, one set driving left to right and the other right to left.

**Parameters:**
- `n` (int): The number of cars in each set. Must be a non-negative integer.

**Returns:**
- int: The total number of collisions.

**Example Usage:**
```python
print(car_race_collision(3))  # Output: 9
```

## Edge Cases & Assumptions
- The function assumes that the input `n` is a non-negative integer.
- If `n` is less than 0, the function raises a `ValueError`.

## Usage Example
```python
# Calculate the number of collisions for 5 cars in each set
collisions = car_race_collision(5)
print(f"Number of collisions: {collisions}")  # Output: Number of collisions: 25

# Handle invalid input
try:
    car_race_collision(-2)
except ValueError as e:
    print(e)  # Output: Input must be a non-negative integer
```