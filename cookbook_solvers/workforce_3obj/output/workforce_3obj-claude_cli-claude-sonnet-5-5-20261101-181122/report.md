=== Workforce 3-Objective Scheduling (solver=ON / NSGA-II) ===

Problem:
A service center runs 3 shift types. Day shift: $100/employee, 0.90 service quality, 0.10 fatigue risk, min 10 max 20 staff. Evening shift: $130/employee, 1.00 quality, 0.25 risk, min 10 max 20. Night shift: $160/employee, 0.70 quality, 0.40 risk, min 10 max 20. Total minimum: 30 staff. Find staffing plans that minimize cost, maximize quality, and minimize fatigue risk simultaneously.

Utopia Anchors (per-objective best):
{"min_cost": {"cost": 3900.0, "quality": 0.866667, "risk": 0.25, "xD": 10.0, "xE": 10.0, "xN": 10.0}, "max_quality": {"cost": 7800.0, "quality": 0.866667, "risk": 0.25, "xD": 20.0, "xE": 20.0, "xN": 20.0}, "min_risk": {"cost": 3900.0, "quality": 0.866667, "risk": 0.25, "xD": 10.0, "xE": 10.0, "xN": 10.0}}

Pareto Surface (82 non-dominated points):
| xD | xE | xN | Cost ($) | Quality | Risk |
|---|---|---|---|---|---|
| 10 | 10 | 10 | 3,900 | 0.8667 | 0.2500 |
| 11 | 10 | 10 | 4,000 | 0.8677 | 0.2452 |
| 10 | 11 | 10 | 4,030 | 0.8710 | 0.2500 |
| 12 | 10 | 10 | 4,100 | 0.8688 | 0.2406 |
| 11 | 11 | 10 | 4,130 | 0.8719 | 0.2453 |
| 13 | 10 | 10 | 4,200 | 0.8697 | 0.2364 |
| 12 | 11 | 10 | 4,230 | 0.8727 | 0.2409 |
| 11 | 12 | 10 | 4,260 | 0.8758 | 0.2455 |
| 10 | 13 | 10 | 4,290 | 0.8788 | 0.2500 |
| 14 | 10 | 10 | 4,300 | 0.8706 | 0.2324 |
| 13 | 11 | 10 | 4,330 | 0.8735 | 0.2368 |
| 12 | 12 | 10 | 4,360 | 0.8765 | 0.2412 |
| 15 | 10 | 10 | 4,400 | 0.8714 | 0.2286 |
| 14 | 11 | 10 | 4,430 | 0.8743 | 0.2329 |
| 13 | 12 | 10 | 4,460 | 0.8771 | 0.2371 |
| 12 | 13 | 10 | 4,490 | 0.8800 | 0.2414 |
| 16 | 10 | 10 | 4,500 | 0.8722 | 0.2250 |
| 15 | 11 | 10 | 4,530 | 0.8750 | 0.2292 |
| 14 | 12 | 10 | 4,560 | 0.8778 | 0.2333 |
| 13 | 13 | 10 | 4,590 | 0.8806 | 0.2375 |
| 12 | 14 | 10 | 4,620 | 0.8833 | 0.2417 |
| 16 | 11 | 10 | 4,630 | 0.8757 | 0.2257 |
| 11 | 15 | 10 | 4,650 | 0.8861 | 0.2458 |
| 15 | 12 | 10 | 4,660 | 0.8784 | 0.2297 |
| 14 | 13 | 10 | 4,690 | 0.8811 | 0.2338 |
| 18 | 10 | 10 | 4,700 | 0.8737 | 0.2184 |
| 16 | 12 | 10 | 4,760 | 0.8789 | 0.2263 |
| 15 | 13 | 10 | 4,790 | 0.8816 | 0.2303 |
| 19 | 10 | 10 | 4,800 | 0.8744 | 0.2154 |
| 14 | 14 | 10 | 4,820 | 0.8842 | 0.2342 |
| 17 | 12 | 10 | 4,860 | 0.8795 | 0.2231 |
| 16 | 13 | 10 | 4,890 | 0.8821 | 0.2269 |
| 20 | 10 | 10 | 4,900 | 0.8750 | 0.2125 |
| 15 | 14 | 10 | 4,920 | 0.8846 | 0.2308 |
| 10 | 18 | 10 | 4,940 | 0.8947 | 0.2500 |
| 14 | 15 | 10 | 4,950 | 0.8872 | 0.2346 |
| 18 | 12 | 10 | 4,960 | 0.8800 | 0.2200 |
| 13 | 16 | 10 | 4,980 | 0.8897 | 0.2385 |
| 17 | 13 | 10 | 4,990 | 0.8825 | 0.2238 |
| 12 | 17 | 10 | 5,010 | 0.8923 | 0.2423 |
| 16 | 14 | 10 | 5,020 | 0.8850 | 0.2275 |
| 20 | 11 | 10 | 5,030 | 0.8780 | 0.2134 |
| 15 | 15 | 10 | 5,050 | 0.8875 | 0.2313 |
| 19 | 12 | 10 | 5,060 | 0.8805 | 0.2171 |
| 10 | 19 | 10 | 5,070 | 0.8974 | 0.2500 |
| 18 | 13 | 10 | 5,090 | 0.8829 | 0.2207 |
| 17 | 14 | 10 | 5,120 | 0.8854 | 0.2244 |
| 12 | 18 | 10 | 5,140 | 0.8950 | 0.2425 |
| 20 | 12 | 10 | 5,160 | 0.8810 | 0.2143 |
| 15 | 16 | 10 | 5,180 | 0.8902 | 0.2317 |
| 19 | 13 | 10 | 5,190 | 0.8833 | 0.2179 |
| 14 | 17 | 10 | 5,210 | 0.8927 | 0.2354 |
| 13 | 18 | 10 | 5,240 | 0.8951 | 0.2390 |
| 17 | 15 | 10 | 5,250 | 0.8881 | 0.2250 |
| 16 | 16 | 10 | 5,280 | 0.8905 | 0.2286 |
| 11 | 20 | 10 | 5,300 | 0.9000 | 0.2463 |
| 19 | 14 | 10 | 5,320 | 0.8860 | 0.2186 |
| 13 | 19 | 10 | 5,370 | 0.8976 | 0.2393 |
| 17 | 16 | 10 | 5,380 | 0.8907 | 0.2256 |
| 12 | 20 | 10 | 5,400 | 0.9000 | 0.2429 |
| 16 | 17 | 10 | 5,410 | 0.8930 | 0.2291 |
| 20 | 14 | 10 | 5,420 | 0.8864 | 0.2159 |
| 19 | 15 | 10 | 5,450 | 0.8886 | 0.2193 |
| 13 | 20 | 10 | 5,500 | 0.9000 | 0.2395 |
| 17 | 17 | 10 | 5,510 | 0.8932 | 0.2261 |
| 20 | 15 | 10 | 5,550 | 0.8889 | 0.2167 |
| 18 | 17 | 10 | 5,610 | 0.8933 | 0.2233 |
| 17 | 18 | 10 | 5,640 | 0.8956 | 0.2267 |
| 16 | 19 | 10 | 5,670 | 0.8978 | 0.2300 |
| 20 | 16 | 10 | 5,680 | 0.8913 | 0.2174 |
| 19 | 17 | 10 | 5,710 | 0.8935 | 0.2207 |
| 18 | 18 | 10 | 5,740 | 0.8957 | 0.2239 |
| 20 | 17 | 10 | 5,810 | 0.8936 | 0.2181 |
| 19 | 18 | 10 | 5,840 | 0.8957 | 0.2213 |
| 18 | 19 | 10 | 5,870 | 0.8979 | 0.2245 |
| 17 | 20 | 10 | 5,900 | 0.9000 | 0.2277 |
| 20 | 18 | 10 | 5,940 | 0.8958 | 0.2188 |
| 19 | 19 | 10 | 5,970 | 0.8979 | 0.2219 |
| 18 | 20 | 10 | 6,000 | 0.9000 | 0.2250 |
| 20 | 19 | 10 | 6,070 | 0.8980 | 0.2194 |
| 19 | 20 | 10 | 6,100 | 0.9000 | 0.2224 |
| 20 | 20 | 10 | 6,200 | 0.9000 | 0.2200 |

**Cost:** $3,900 – $6,200  |  **Quality:** 0.8667 – 0.9000  |  **Risk:** 0.2125 – 0.2500

Interpretation:
**1. The tradeoff.** Quality and risk are staff-weighted averages, and the 10 Night staff (risk 0.40) are the main risk driver. Adding Day staff dilutes that risk, so risk falls as Day grows. Adding Evening staff raises quality (1.00) but barely moves risk. One caveat on the premise: cost and risk do not align in this table. The cheapest plan (10/10/10) has the *highest* risk (0.25), and cutting risk means paying for more Day staff. The real conflict is cost against both quality and risk.

**2. Operating points**
- **Budget:** 10/10/10 at $3,900 (quality 0.867, risk 0.250). It is the cheapest plan but the riskiest.
- **Peak/customer-facing:** 11/20/10 at $5,300 (quality 0.900, risk 0.246). It is the cheapest plan to reach the quality ceiling.
- **Balanced:** 16/10/10 at $4,500 (quality 0.872, risk 0.225). It costs 15% more than the minimum and cuts risk by 10%.

**3. Distance from utopia.** The supplied anchors disagree with the table (the max-quality anchor shows 0.867, not 0.900), so I used the table's own bests: cost $3,900, quality 0.900, risk 0.2125. No plan achieves all three. The cheapest plan is 0.033 below best quality and has the worst risk. The quality-max plan costs 36% more than the minimum. The lowest-risk plan (20/10/10, $4,900) has quality 0.875.

**4. Recommendation.** Staff roughly 16 Day, 10 Evening and 10 Night by default, and add Evening staff only for peak periods.

LLM calls: 2