# Specification: `is_cube`

## 1. Purpose
Decide whether an integer is a perfect cube, meaning it equals k·k·k for some integer k, positive, negative or zero. The decision must be exact for integers of any size. It must not rely on floating-point approximation, which breaks down for large magnitudes (above roughly 1e47) and for values beyond floating-point range (above about 1e308).

An alias, `iscube`, refers to the same operation.

## 2. Inputs
- One argument, `n`, which must be an integer.
- Boolean values are accepted and treated as the integers 1 (true) and 0 (false).
- Integers can be negative, zero or positive, with no upper or lower bound.
- Any other type is rejected. This covers floats, even integral-valued ones such as 8.0, and also NaN, infinity, strings and None.

## 3. Outputs
- Returns a boolean.
  - True if some integer k exists with k³ = n.
  - False otherwise.
- Raises `TypeError` for a non-integer input. The message names the offending type and has the form "is_cube expects an int, got <typename>".
- The function has no side effects and is deterministic.

## 4. Behaviour
1. **Type check.** If the input is not an integer (booleans count as integers), raise `TypeError`. No result is produced.
2. **Sign symmetry.** Since (−k)³ = −(k³), n is a cube exactly when its absolute value is a cube. The remaining steps work on the absolute value m.
3. **Find the integer cube root.** Find the smallest non-negative integer r with r³ ≥ m. This is done in two phases, using only exact integer arithmetic.
   - First, find an upper bound by starting at 1 and repeatedly doubling until its cube reaches or exceeds m.
   - Then binary search the range from 0 to that bound for the smallest r whose cube is at least m.
4. **Verdict.** Return True if and only if r³ equals m exactly.

**Expected results**
- 0, 1, −1, 64, −64, True (as 1) and 2¹⁵⁰ are cubes.
- 2, 63, 65 and 180 are not cubes.
- (10¹⁷+1)³ and its negative are cubes, but (10¹⁷+1)³+1 is not.
- 10³⁰⁹ is a cube, as (10¹⁰³)³. 10³⁰⁹+1 is not.
- The largest cube below 2⁵³ is a cube, and that value plus 1 is not.

**Complexity.** The number of iterations grows with the bit length of m, roughly logarithmically in its magnitude, and each step costs one big-integer cube and comparison.

## 5. Assumptions
- The runtime provides arbitrary-precision integers with exact multiplication, comparison and floor division, so no overflow or rounding occurs.
- Cubing is monotonically increasing on non-negative integers. Both the doubling phase and the binary search depend on this.
- Zero is a valid cube (0³), and the search handles it without special-casing. The smallest r with r³ ≥ 0 is 0.
- Callers wanting to test floats must convert them to integers themselves. The function does not coerce, round or accept integral floats.
- The built-in self-test is run only when the file is executed directly. It is not part of the public interface.