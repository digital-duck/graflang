=== Z3 Trading Rule Checker (r118) | mode=AUDIT ===

## Z3 Trading Rule Audit — Momentum Breakout Strategy v1.0

**Status:** SAT  
**Verdict:** Strategy is consistent — a triggering market scenario exists
**Entry rules checked:** 4  
**Risk rules checked:** 2

### Triggering Market Scenario Found by Z3

| Indicator | Value |
|---|---|
| rsi | 28 |
| price_vs_ma200 | 0 |
| volume_ratio | 150 |
| adr_pct | 20 |
| in_uptrend | True |
| earnings_week | False |

> Z3 found the **minimum boundary** scenario — the exact threshold where all rules first become simultaneously satisfiable. A manual trace typically picks a 'typical' example and misses these edges.

── Analyst Explanation ─────────────────────────────────────
**1. What Z3 found:** The strategy is consistent (SAT). The four entry rules and two risk rules can all be true at once, so the strategy can actually fire a trade. No contradictions.

**2. The scenario:** RSI 28, price exactly at the 200-day MA (0% above it), volume 150% of average, ADR 20%, in an uptrend, no earnings that week. It's a valid but odd state. An RSI of 28 is oversold, which sits awkwardly with a "momentum breakout" label. A 20% average daily range is extreme, typical of highly volatile small caps or speculative names, not normal breakout candidates. Price sitting right on the 200 MA with an uptrend flag is possible but marginal.

**3. UNSAT:** Not applicable.

**4. What a manual check would miss:** Z3 reports the boundary point where the rules first become satisfiable. That shows the thresholds permit trades in states that don't match the strategy's intent (oversold RSI on a "breakout"). A manual trace using a typical example, like RSI 65 and price 5% above the MA, would pass without ever revealing this. It also hints that the RSI and ADR thresholds may be too loose or mis-specified.

**5. Risk of skipping formal checks:** Contradictory rules would silently never trigger, leaving you believing you're running a strategy you aren't. The opposite risk is subtler: rules that are consistent but admit unintended trades, as here. You would then take positions in market states you never meant to trade, with no warning until losses show up.

**Takeaway:** Consistent is not the same as correct. Review the RSI floor and the ADR cap against what you actually intend.