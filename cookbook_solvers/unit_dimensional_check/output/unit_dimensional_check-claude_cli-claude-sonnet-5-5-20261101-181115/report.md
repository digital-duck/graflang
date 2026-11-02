# Unit / Dimensional Check Report

**Problem:** A car accelerates from rest at 2.5 m/s^2 for 12 seconds. What is its final speed, in km/h?

**pint status:** `OK`
**Ground-truth answer:** `108.0 km/h`
**Round-trip check:** `match`

## Interpretation

The problem asks for the final speed, in km/h, of a car that starts from rest and accelerates at 2.5 m/s² for 12 seconds.

The verified result gives an answer of **108.0 km/h**, which matches the intermediate value of 30.0 m/s.

The relationship used is the constant-acceleration kinematic equation v = v₀ + at, with v₀ = 0. This gives v = 2.5 × 12 = 30 m/s, and multiplying by 3.6 converts it to km/h.

Final answer: 108.0

## Solver Code (LLM-generated, pint)

```python
a = Q_(2.5, 'm/s^2')
t = Q_(12, 's')
v0 = Q_(0, 'm/s')
v_final = v0 + a * t
v_kmh = v_final.to('km/h')
_result = {
    "status": "OK",
    "answer": float(f"{v_kmh.magnitude:.3g}"),
    "unit": "km/h",
    "final_speed_m_per_s": float(v_final.to('m/s').magnitude),
}
```