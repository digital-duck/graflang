### Specification

#### Purpose
The purpose of this function is to calculate the square of a given non-negative integer, representing a simple mathematical operation.

#### Inputs
The function accepts a single parameter:
- `n` (integer): A non-negative integer. If `n` is not an integer or is negative, the function will raise a `ValueError`.

#### Outputs
The function returns a single value:
- The square of the input integer `n`. The output is an integer.

#### Behaviour
- The function takes an integer `n` and returns `n * n`, which is the square of `n`.
- If `n` is not a non-negative integer, the function raises a `ValueError` with the message "Input must be a non-negative integer".
- The function handles the edge case where `n` is 0, returning 0 as `0 * 0 = 0`.

#### Assumptions
- The input `n` is expected to be an integer type.
- The input `n` is expected to be non-negative (i.e., greater than or equal to 0).

This specification provides a clear, precise description of what the code is intended to do, its inputs, outputs, and behavior, including edge cases and error conditions.