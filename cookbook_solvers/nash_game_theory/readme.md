# Recipe 110 — Nash Equilibrium Game Theory

> **GraphLang port.** Lifted from SPL.py's `cookbook-solver/110_nash_game_theory` with `spl3 util spl2graph` (no model was involved). The Python tools travel inside the graph as `SOLVE` nodes (`backend: kernel`), so `graf run` needs the `kernel` extra (`pip install 'graflang[kernel]'`) and the libraries named below, not SPL.py. Commands use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`.
> Not ported: `tools.py` (the SPL original's tool registration, experiment and app scripts).
> Test run (2026-11-01, `claude_cli` `claude-sonnet-5-5`, solver on): the graph completed (1 model calls, 357 tokens in / 275 out in total). A run that completes does not show the answer is right: read the output before you rely on a recipe.

**The key story:** Two SaaS firms choose simultaneously between High ($100/mo) and Low ($70/mo) pricing. LLM says "both should hold High prices for mutual benefit." nashpy proves (Low, Low) is the unique Nash equilibrium — a Prisoner's Dilemma where each firm earns $25K/mo instead of the cooperative $40K/mo.

## What it demonstrates

| Axis | solver=ON | solver=OFF |
|---|---|---|
| Engine | nashpy support enumeration | LLM cooperative reasoning |
| Output | All Nash equilibria + Prisoner's Dilemma gap | "Both should price High for mutual benefit" |
| Guarantee | Mathematically verified (no profitable unilateral deviation) | Intuitive but ignores incentive structure |
| Verification | `ASSERT nash_found` (C1) | — |
| Solver class | C1 (categorical: equilibrium found / not found) | — |

## The payoff matrix (profits in $K/month)

|  | **B: High** | **B: Low** |
|---|---|---|
| **A: High** | (40, 40) ← joint optimum | (10, 55) |
| **A: Low** | (55, 10) | **(25, 25) ← Nash** |

**Why (Low, Low) is Nash**: If B plays High, A earns 55 by playing Low vs 40 by playing High → A defects. If B plays Low, A earns 25 by playing Low vs 10 by playing High → A still defects. Low is a dominant strategy for A (and by symmetry, for B). The Nash equilibrium is where both dominant strategies intersect.

**Prisoner's Dilemma gap**: Each firm earns $25K/mo at Nash vs $40K/mo at the joint optimum — $15K/mo per firm, $30K/mo combined, is destroyed by rational self-interest.

## Run commands

```bash
# solver=ON — nashpy Nash equilibrium
graf run cookbook_solvers/nash_game_theory/nash_game_theory.graph.yaml \
    --adapter claude_cli --param use_solver=true

# solver=OFF — LLM strategic reasoning
graf run cookbook_solvers/nash_game_theory/nash_game_theory.graph.yaml \
    --adapter ollama -m gemma3 --param use_solver=false
```

## Install

```bash
conda activate spl123
pip install nashpy
```

## TOOL_API reference

| Function | Purpose |
|---|---|
| `get_default_game()` | Returns SaaS pricing duopoly game JSON (payoff matrices) |
| `find_nash_equilibria(game_json)` | nashpy support enumeration → all equilibria + PD gap |
| `nash_found(result_json)` | ASSERT gate: at least 1 equilibrium found |
| `format_nash_report(result_json)` | Markdown tables: equilibria + joint optimum + gap |

## Game theory concepts

- **Normal-form game**: players choose strategies simultaneously (no time structure)
- **Nash equilibrium**: no player can improve payoff by changing their strategy unilaterally
- **Dominant strategy**: a strategy that is best regardless of what the opponent does
- **Prisoner's Dilemma**: dominant-strategy Nash is Pareto-inferior (everyone worse off than cooperation)
- **Support enumeration**: nashpy's algorithm finds all Nash equilibria by iterating over support pairs

## Related recipes

- r111: Stackelberg sequential game (extensive form — leader goes first)
- r102: Z3 eligibility rules (constraint satisfiability, not game equilibria)
- r107: workforce multi-objective (Pareto — tradeoffs without strategic interaction)
