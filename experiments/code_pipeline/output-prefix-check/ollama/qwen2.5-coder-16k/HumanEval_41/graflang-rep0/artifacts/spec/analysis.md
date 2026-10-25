[READY]
This function will implement a simulation of a car race where `n` cars are driving left to right on an infinitely long straight road, and another set of `n` cars are driving right to left. The function will return the total number of collisions between the cars.

STRUCTURED SPEC:
1. The function `car_race_collision` should accept a single parameter `n`, which represents the number of cars in each direction.
2. The function should simulate the scenario where each car from the left direction collides with each car from the right direction exactly once.
3. The function should return an integer representing the total number of collisions.
4. The cars are infinitely sturdy and strong, meaning they continue their original trajectory after a collision.
5. The function should not consider the position of the cars on the road, only their direction of travel.
6. The function should handle cases where `n` is zero, returning zero collisions in such scenarios.
7. The function should be implemented in Python.
8. The function should be self-contained and include any necessary imports.