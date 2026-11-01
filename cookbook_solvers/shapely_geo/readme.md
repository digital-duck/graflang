# Recipe 106 — Shapely Geospatial Coverage Analyzer

> **GraphLang port.** Lifted from SPL.py's `cookbook-solver/106_shapely_geo` with `spl3 util spl2graph` (no model was involved). The Python tools travel inside the graph as `SOLVE` nodes (`backend: kernel`), so `graf run` needs the `kernel` extra (`pip install 'graflang[kernel]'`) and the libraries named below, not SPL.py. Commands use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`.
> Not ported: `tools.py` (the SPL original's tool registration, experiment and app scripts).
> Smoke test (2026-11-01, placeholder model, no real model call): runs end to end with the placeholder model. This is a run-through of the graph, not a check that the answers are right: run it with a real model before you rely on it.

**The key story:** Three delivery zones in Maplewood have a 2 km² routing conflict (Zone A ∩ Zone B) where Alice and Bob both claim the same neighborhood, and a 2 km² northeast gap where no driver is assigned. Shapely computes both exactly in <0.01s. LLM estimates the gap as "small" from the description.

## What it demonstrates

| Axis | solver=ON | solver=OFF |
|---|---|---|
| Engine | Shapely polygon geometry | LLM spatial estimation from description |
| Output | Exact overlap/gap areas, point-in-zone assignments | Rough estimate: "Zone A and B probably overlap a bit" |
| Guarantee | Mathematically exact (floating point) | Approximate, misses edge cases |
| Verification | `ASSERT coverage_is_valid` (C1) | — |
| Solver class | C1 (categorical: OK / ERROR) + C3 (independent geometric computation) | — |

## Default problem (Maplewood city, 10×8 km)

```
(0,8)──────────────────(10,8)
  │  Zone A (North)    │ GAP │
  │  [0,4]→[6,8]       │     │
(0,4)────────(6,4)    │     │
  │           │  OVERLAP    │
  │  Zone B   │  Zone A∩B   │ Zone C (East)
  │  (South-W)│  [0,4]→[6,5]│ [6,0]→[10,6]
  │  [0,0]→[7,5]       │     │
(0,0)────────────────(10,0)
```

Zone A: [0,4]→[6,8] = 30 km²  
Zone B: [0,0]→[7,5] = 35 km²  
Zone C: [6,0]→[10,6] = 24 km²  
City: 10×8 = 80 km²

## Key findings (solver=ON)

| Finding | Value |
|---|---|
| Zone A ∩ Zone B overlap | 6 km² (routing conflict for Alice + Bob) |
| Northeast gap (x>6, y>6) | 4 km² (no driver assigned) |
| Coverage ratio | 95% of city |
| C004 River View Deli (9,7) | UNASSIGNED — in the gap |
| C005 NE Corner Shop (8,7) | UNASSIGNED — in the gap |

## Run commands

```bash
# solver=ON — Shapely exact geometry
graf run ~/.graflang/solvers/shapely_geo/shapely_geo.graph.yaml \
    --adapter claude_cli --param use_solver=true

# solver=OFF — LLM spatial estimate
graf run ~/.graflang/solvers/shapely_geo/shapely_geo.graph.yaml \
    --adapter ollama -m gemma3 --param use_solver=false
```

## Install

```bash
conda activate spl123
pip install shapely
```

## TOOL_API reference

| Function | Purpose |
|---|---|
| `get_default_zones()` | Returns Maplewood zone JSON (3 zones, 5 customers) |
| `analyze_coverage(zones_json)` | Shapely: overlaps, gaps, point-in-zone assignments |
| `coverage_is_valid(result_json)` | ASSERT gate: `status == "OK"` |
| `format_coverage_report(result_json)` | Markdown tables: conflicts, gaps, customer assignments |

## Geometry operations used

- `Polygon.intersection(other)` — compute overlap area between two zones
- `unary_union(polygons)` — merge all zones into a single covered region
- `city.difference(covered)` — find the uncovered gap inside city boundary
- `Polygon.contains(Point)` — assign each customer to their zone

## Real-world applications

- **Delivery logistics**: detect routing conflicts between driver territories
- **Telecom coverage**: find dead zones and overlapping cell tower footprints
- **Zoning compliance**: verify that a new development falls within permitted zones
- **Emergency services**: ensure no address is outside every fire station's service radius

## Related recipes

- r102: Z3 SMT — logical constraints over eligibility rules (not geometric)
- r107: workforce optimization — 3-objective Pareto over shift assignments
- r100: supply sourcing — geographic supplier selection (non-spatial but location-aware)
