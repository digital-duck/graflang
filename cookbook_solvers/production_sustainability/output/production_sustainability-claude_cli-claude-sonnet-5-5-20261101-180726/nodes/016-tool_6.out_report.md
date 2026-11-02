=== Production Sustainability (solver=ON / PuLP Pareto Sweep) ===

Problem:
A factory produces standard product A and green product B. A: $10 profit, 3 kg CO₂, uses 2 hr labor and 3 kg material. B: $6 profit, 1 kg CO₂, uses 1 hr labor and 2 kg material. Available: 20 labor-hours, 30 kg material. Find production plans that maximize profit and minimize carbon footprint.

Extracted Problem Data (JSON):
{"products":[{"name":"A","profit":10.0,"carbon":3.0,"labor":2.0,"material":3.0},{"name":"B","profit":6.0,"carbon":1.0,"labor":1.0,"material":2.0}],"resources":{"labor":20.0,"material":30.0}}

Pareto Front (3 non-dominated points):
| Profit ($) | Carbon (kg) | Product A (units) | Product B (units) |
|---|---|---|---|
| 100.0 | 30.0 | 10.00 | 0.00 |
| 90.0 | 15.0 | 0.00 | 15.00 |
| 0.0 | 0.0 | 0.00 | 0.00 |

Interpretation:
# Profit vs. carbon: what the numbers say

## Why profit and emissions rise together

Material (30 kg) is the limit that binds. Per kilogram of material, product A earns about $3.33 and product B earns $3.00. A earns slightly more, but it emits **1.0 kg CO₂ per kg of material**, while B emits only **0.5 kg**. Putting the scarce material into A buys a little extra profit and doubles the emissions. That is the tradeoff.

## Operating points

| Plan | Mix | Profit | Carbon | Notes |
|---|---|---|---|---|
| **Profit-leaning** | 10 A, 0 B | $100 | 30 kg | Uses all labor and all material |
| **Green-leaning** | 0 A, 15 B | $90 | 15 kg | Uses all material, 5 labor-hours spare |
| **Balanced** (my interpolation, not in your table) | 5 A, 7.5 B | $95 | 22.5 kg | Uses all material, 12.5 of 20 labor-hours |
| Shutdown | none | $0 | 0 kg | Not a real option |

The balanced row is a straight-line blend of the two real plans. It is feasible, but you would need to check that making half-units of B is practical (for example, 5 A and 8 B gives $98 and 23 kg).

## What a carbon cut costs

Going from the profit-leaning plan to the green-leaning plan:

- Profit falls by **$10, or 10%**.
- Carbon falls by **15 kg, or 50%**.

That works out to about **$0.67 of profit per kg of CO₂ avoided**, which is a cheap trade. The 5 spare labor-hours in the green plan also give you some room to absorb disruptions.

Going lower than the green plan is expensive. Cutting further means making less B, and each kg of CO₂ removed then costs about **$6** in lost profit. So the green plan is the natural stopping point.

## Recommendation

**Choose 0 A and 15 B ($90, 15 kg).**

- You keep 90% of the maximum profit and halve your emissions.
- The next step down in carbon is nine times more expensive per kg.
- You can claim a large, verifiable reduction without a meaningful hit to the business.

If the owners won't accept any profit sacrifice, the balanced plan (about $95, 22.5 kg) cuts emissions by 25% for a 5% profit cost. That is a reasonable first step toward the green plan.

**Caveat:** this assumes demand and price for B hold at volumes of 15 units. If B's market is thinner than A's, check that before committing.

LLM calls: 2