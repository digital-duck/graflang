# Physics Conservation Check Report

**Problem:** A 2 kg ball moving at 5 m/s strikes a stationary 2 kg ball head-on in a perfectly elastic collision. What is the final velocity of the first ball, in m/s?

**Verifier status:** `OK`
**Final velocity (object 1):** `0.0 m/s`
**Momentum conserved:** `True` (10.0 -> 10.0)
**Energy conserved:** `True` (25.0 -> 25.0)
**Round-trip check:** `match`

## Interpretation

**Interpretation:** The problem asks for the first ball's velocity after a head-on, perfectly elastic collision between two equal 2 kg masses, where one starts at 5 m/s and the other is at rest.

Object 1's final velocity is **0.0 m/s**: it stops dead, while the second ball leaves at 5.0 m/s. The two equal masses effectively swap velocities.

Verification confirmed that momentum (10.0 before and after) and kinetic energy (25.0 before and after) are both conserved, consistent with an elastic collision.

Final answer: 0.0

## Solver Code (LLM-generated, NumPy)

```python
m1 = 2.0
m2 = 2.0
v1i = 5.0
v2i = 0.0
v1f = ((m1 - m2) * v1i + 2 * m2 * v2i) / (m1 + m2)
v2f = ((m2 - m1) * v2i + 2 * m1 * v1i) / (m1 + m2)
_result = {
    "m1": m1, "m2": m2,
    "v1i": v1i, "v2i": v2i,
    "v1f": float(v1f), "v2f": float(v2f),
    "elastic": True,
}
```