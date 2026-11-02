# Recipe 118 — Z3 Trading Rule Checker

> **GraphLang port.** Lifted from SPL.py's `cookbook-solver/118_trading_rule_z3` with `spl3 util spl2graph` (no model was involved). The Python tools travel inside the graph as `SOLVE` nodes (`backend: kernel`), so `graf run` needs the `kernel` extra (`pip install 'graflang[kernel]'`) and the libraries named below, not SPL.py. Commands use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`.
> Not ported: `tools.py` (the SPL original's tool registration, experiment and app scripts).
> Test run (2026-11-01, `claude_cli` `claude-sonnet-5-5`, solver on): the graph completed (1 model calls, 293 tokens in / 398 out in total). A run that completes does not show the answer is right: read the output before you rely on a recipe.

**The key story:** A disciplined trader has rules. But rules interact. A strategy that looks consistent when traced rule-by-rule can be internally contradictory — no market state ever fires it. Z3 audits the entire rulebook formally, finds the exact boundary scenario where all rules first align, and surfaces hidden conflicts before the first dollar is risked. The LLM does the domain translation (NL → formal spec); Z3 does the proof.

## The IT-era analogy

| Era | Translation | Solver | Rigor |
|---|---|---|---|
| Pre-IT | human experts | pen + paper | ad-hoc |
| IT era | programmers | hand-crafted rule engines | deterministic but brittle, domain-locked |
| **Now** | **LLM** | **Z3 / LP / Prolog / Nash...** | **provable, composable, reusable** |

Every domain-specific rule system a programmer once wrote by hand was a custom solver — a compliance engine, a risk checker, an eligibility gate. Those are now replaced by: LLM (translates NL) + formal solver (proves correctness). As the solver collection grows, each becomes a composable building block for larger problems.

## What it demonstrates

| Mode | Input | Z3 Output |
|---|---|---|
| **AUDIT** (default) | trading rules (NL or default) | SAT → triggering market scenario; UNSAT → contradiction proof |
| **SNAPSHOT** | `--param snapshot_json=...` | BUY / NO_SIGNAL + which rules blocked |

## The hidden constraint story

Default strategy: Momentum Breakout with 6 entry/risk rules.

A trader manually traces: "RSI < 35 ✓, price above MA ✓, volume surge ✓ — strategy looks good." But:
- **E1** requires `28 ≤ RSI ≤ 35` (not just RSI < 35 — lower bound is intentional: avoid panic)
- **R1** blocks `earnings_week = True`
- **R2** requires `in_uptrend = True`

Z3 finds the **minimum boundary**: RSI=28 (not 31, not 35) — the floor of the valid window. A manual trace picks a comfortable middle, never discovers whether the floor is reachable, and never discovers if a future rule addition makes the floor unreachable.

If a trader adds a new rule "RSI ≥ 30 for liquidity" alongside E1's "RSI ≤ 35", valid window shrinks silently to `30 ≤ RSI ≤ 35`. Z3 immediately reports SAT with the new boundary. If they accidentally write "RSI ≥ 36", Z3 returns UNSAT — no market state satisfies both `RSI ≤ 35` and `RSI ≥ 36`. The strategy is dead. No manual trace catches this.

## Run commands

```bash
# AUDIT mode — default Momentum Breakout strategy
graf run cookbook_solvers/trading_rule_z3/trading_rule_z3.graph.yaml \
    --llm claude_cli

# AUDIT mode — custom NL trading rules
graf run cookbook_solvers/trading_rule_z3/trading_rule_z3.graph.yaml \
    --llm claude_cli \
    --param "rules_text=Enter long when RSI is between 30 and 40, price is above the 50-day moving average, and volume is at least twice the 20-day average. Never enter if a Fed announcement is scheduled today. Skip if ADR% is below 1.5."

# SNAPSHOT mode — check today's indicators against the default strategy
graf run cookbook_solvers/trading_rule_z3/trading_rule_z3.graph.yaml \
    --llm claude_cli \
    --param 'snapshot_json={"rsi":31,"price_vs_ma200":5,"volume_ratio":180,"adr_pct":25,"in_uptrend":true,"earnings_week":false}'

# SNAPSHOT with custom rules + today's data
graf run cookbook_solvers/trading_rule_z3/trading_rule_z3.graph.yaml \
    --llm claude_cli \
    --param "rules_text=Enter when RSI is between 30 and 45 and volume ratio exceeds 150. No earnings weeks." \
    --param 'snapshot_json={"rsi":38,"volume_ratio":160,"earnings_week":false}'
```

## Install

```bash
conda activate spl123
pip install z3-solver
```

## TOOL_API reference

| Function | Purpose |
|---|---|
| `get_default_policy()` | Returns hardcoded Momentum Breakout policy JSON — demo / fallback |
| `is_empty_policy(policy_text)` | Returns `"true"` if no custom rules supplied; structural branch, no LLM |
| `parse_policy_json(json_str)` | Strips fences, validates LLM-extracted policy JSON; falls back to default |
| `check_z3_strategy(policy_json)` | Z3 SAT/UNSAT on all entry + risk rules → triggering scenario or contradiction proof |
| `check_market_snapshot(policy_json, snapshot_json)` | Given today's indicator values, evaluate which rules pass/fail |
| `is_strategy_consistent(result_json)` | ASSERT gate: strategy is SAT (rules are not contradictory) |
| `format_strategy_report(result_json, policy_json)` | Markdown audit report |

## Two modes — one workflow

```
rules_text="" AND snapshot_json=""  →  AUDIT on default strategy
rules_text=NL AND snapshot_json=""  →  NL→Z3 extraction, then AUDIT
rules_text="" AND snapshot_json={}  →  SNAPSHOT on default strategy
rules_text=NL AND snapshot_json={}  →  NL→Z3 extraction, then SNAPSHOT
```

The branching is structural (empty-string check), not keyword-based — no hardcoding.

## Z3 as a trading risk engine

Beyond one-shot checks, Z3 can answer:

| Question | Z3 query |
|---|---|
| Can I ever trade this? | `find_triggering_scenario` (SAT/UNSAT) |
| Does today trigger a buy? | `check_market_snapshot` |
| Do my rules contradict each other? | UNSAT proof |
| What's the minimum RSI that fires my strategy? | Model extraction from SAT result |
| After I add a new rule, is the strategy still viable? | Re-run AUDIT — Z3 re-proves in milliseconds |

Each answer is a **formal proof**, not a heuristic. No backtesting required for consistency — Z3 checks all possible market states simultaneously.

## Related recipes

- r102: Z3 compliance checker — loan eligibility (the NL→Z3 pipeline this recipe extends)
- r105: Prolog inference — backward chaining for contract/compliance
- r110: Nash game theory — multi-agent strategic reasoning
- r78: PuLP constraint optimization — LP/MILP for portfolio allocation
