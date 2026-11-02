# Crystal Structure Check Report

**Problem:** NaCl crystallizes in a cubic (rock-salt) structure with lattice parameter a = 5.640 Angstrom, all angles 90 degrees, Z = 4 formula units per unit cell, and molar mass 58.44 g/mol. What is its theoretical density, in g/cm^3?

**Verifier status:** `OK`
**Theoretical density:** `2.1636 g/cm^3`
**Crystal system:** `cubic` (symmetry_ok=True)
**Unit cell volume:** `179.406 Å³`
**Round-trip check:** `match`

## Interpretation

NaCl adopts a **cubic** (rock-salt) crystal system, with a unit-cell volume of **179.406 Å³** (from a = 5.640 Å, Z = 4).

Its theoretical density is **2.1636 g/cm³** (reported as 2.164 g/cm³), meaning the packed ions in the cell are a bit more than twice as dense as water.

This cross-check matters because verifying the symmetry constraints and independently recomputing density from the raw lattice parameters catches inconsistent or mistyped structural data before it spreads into databases and downstream calculations.

Final answer: 2.1636

## Solver Code (LLM-generated, Python)

```python
a = 5.640
b = 5.640
c = 5.640
alpha = 90.0
beta = 90.0
gamma = 90.0
Z = 4
molar_mass = 58.44
N_A = 6.02214076e23

ca = math.cos(math.radians(alpha))
cb = math.cos(math.radians(beta))
cg = math.cos(math.radians(gamma))

V_angstrom3 = a * b * c * math.sqrt(1 - ca**2 - cb**2 - cg**2 + 2 * ca * cb * cg)
V_cm3 = V_angstrom3 * 1e-24

density = Z * molar_mass / (N_A * V_cm3)
density = float(f"{density:.4g}")

_result = {
    "system": "cubic",
    "a": a, "b": b, "c": c,
    "alpha": alpha, "beta": beta, "gamma": gamma,
    "Z": Z, "molar_mass": molar_mass,
    "density": density
}
```