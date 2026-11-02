# Unit / Dimensional Check Report

**Problem:** A car accelerates from rest at 2.5 m/s^2 for 12 seconds. What is its final speed, in km/h?

**pint status:** `OK`
**Ground-truth answer:** `108.0 km/h`
**Round-trip check:** `match`

## Interpretation

**What's asked:** The final speed of a car that starts from rest and accelerates at 2.5 m/s² for 12 seconds, expressed in km/h.

**Answer:** The car reaches **108.0 km/h**, which is 30.0 m/s before conversion.

**Physics:** This uses the constant-acceleration relationship v = v₀ + a·t. With v₀ = 0, the speed is 2.5 m/s² × 12 s = 30 m/s, then multiplied by 3.6 to convert to km/h.

Final answer: 108.0

## Solver Code (LLM-generated, pint)

```python
a0 = Q_(2.5, 'm/s^2')
t = Q_(12, 's')
v0 = Q_(0, 'm/s')
v_final = v0 + a0 * t
v_kmh = v_final.to('km/h')
_result = {
    "status": "OK",
    "answer": round(v_kmh.magnitude, 3 - 1 - int(__import__('math').floor(__import__('math').log10(abs(v_kmh.magnitude))))),
    "unit": "km/h",
    "final_speed_m_per_s": v_final.to('m/s').magnitude,
    "acceleration": str(a0),
    "time": str(t),
}
```