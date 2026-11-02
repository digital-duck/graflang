=== Shapely Coverage Analyzer (r106) | solver=ON ===

## Geospatial Coverage Report — Maplewood

**City area:** 80.0 km²  
**Covered area:** 72.0 km²  
**Coverage ratio:** 90.0%  
**Routing conflicts:** 2  
**Coverage gaps:** 1

### Routing Conflicts (zone overlaps)

| Zone A | Zone B | Overlap Area | % of Zone A |
|---|---|---|---|
| Zone A (North) | Zone B (South-West) | 6.0 km² | 25.0% |
| Zone B (South-West) | Zone C (East) | 5.0 km² | 14.3% |

### Coverage Gaps

- **8.0 km² uncovered** (10.0% of city)

### Customer Zone Assignments

| Customer | Location | Assigned Zone(s) | Conflict |
|---|---|---|---|
| Main St Bakery | (3, 6) | Zone A (North) | ✓ |
| Elm Ave Market | (3, 2) | Zone B (South-West) | ✓ |
| Oak Park Cafe | (8, 3) | Zone C (East) | ✓ |
| River View Deli | (9, 7) | UNASSIGNED | ✗ unserved |
| NE Corner Shop | (8, 7) | UNASSIGNED | ✗ unserved |

── Logistics Explanation ───────────────────────────────────
1. **A/B overlap:** 6.0 km² is 25% of Zone A, which is significant. Alice and Bob could both be dispatched to the same customers, causing duplicate deliveries, unclear ownership, and wasted driver time. Note that the report's table lists the Elm Ave Market as unconflicted, so the overlap area seems to hold no current customers, but any new customer there would be ambiguous.

2. **Gap:** 8.0 km² (10% of the city), apparently near the northeast corner, as the description suggests. River View Deli (9,7) and NE Corner Shop (8,7) are both unserved. The report doesn't give exact gap coordinates, so that location is inferred from those two customers.

3. **Simplest fix:** Move the A/B boundary so Zone B stops where Zone A starts, which removes the 6 km² overlap. Then extend Zone C northward (or Zone A eastward) to cover the northeast corner. The B/C overlap of 5 km² should also be trimmed, since it is a second conflict.

4. **LLM estimate error:** The description says only "most of the city" with "gaps near the northeast corner." An LLM would likely guess a rough or understated gap size and miss the overlaps' effect on the totals. Overlaps mean summing zone areas overstates coverage. Exact geometry gives 8.0 km² precisely.