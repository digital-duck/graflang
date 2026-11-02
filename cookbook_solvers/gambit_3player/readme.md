# Recipe 115 — Gambit 3-Player Game Theory

> **GraphLang port.** Lifted from SPL.py's `cookbook-solver/115_gambit_3player` with `spl3 util spl2graph` (no model was involved). The Python tools travel inside the graph as `SOLVE` nodes (`backend: kernel`), so `graf run` needs the `kernel` extra (`pip install 'graflang[kernel]'`) and the libraries named below, not SPL.py. Commands use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`.
> Not ported: `tools.py` (the SPL original's tool registration, experiment and app scripts).
> Test run (2026-11-01, `claude_cli` `claude-sonnet-5-5`, solver on): the graph completed (1 model calls, 506 tokens in / 435 out in total). A run that completes does not show the answer is right: read the output before you rely on a recipe.

**Category:** reasoning · **Tier:** 2 · **Requires:** `pip install pygambit` (C++ toolchain)
· **Solver class:** S024 (N-player normal-form Nash)

Find the Nash equilibria of a **3-player** normal-form game with
[pygambit](https://gambit.readthedocs.io/). Extends recipe 110 (2-player nashpy)
to the N-player case — the point where "just enumerate best responses in your
head" stops being reliable.

## About Gambit

[Gambit](http://www.gambit-project.org/) is a long-standing open-source toolkit
for **computation in game theory** (originated by McKelvey, McLennan & Turocy).
In brief:

- **Builds and solves games** — **N-player** normal-form *and* extensive-form
  (sequential) games, not just the 2-player matrices nashpy handles.
- **Many equilibrium methods** — pure-strategy enumeration (`enumpure`), mixed
  enumeration (`enummixed`), plus `lcp` / `liap` / `simpdiv` / `gnm` / `ipa`, and
  **quantal response equilibrium (QRE)** for bounded-rational play.
- **Two front-ends** — command-line tools and a Python API,
  [`pygambit`](https://gambit.readthedocs.io/), used here.

Where `nashpy` (r110) stops at 2-player normal-form, Gambit is the general-purpose
equilibrium engine for the rest — which is why this recipe uses it for the
3-firm case.

## What it demonstrates

| Axis | solver=ON | solver=OFF |
|---|---|---|
| Engine | pygambit `enumpure_solve` (pure-strategy Nash enumeration) | LLM reasons about 3-way competition |
| Guarantee | Every pure Nash found; no profitable unilateral deviation for **any** player | Plausible strategic narrative; may miss the equilibrium or the dominance |
| Verification | `ASSERT nash_3p_found` (status OK **and** ≥1 equilibrium) | — |
| LLM role | Interpret the equilibrium + the cooperation gap | Propose the likely outcome and reasoning |

The deterministic/probabilistic split: the **LLM** reads the game story; **pygambit**
proves which profiles are equilibria; the **LLM** explains what that means for the firms.

## The game (default: 3-firm SaaS pricing triopoly)

Three firms simultaneously price **Premium** or **Standard**. Per-firm payoffs
($K/period) for each joint profile:

| Profile (A,B,C) | Payoffs | Note |
|---|---|---|
| P, P, P | 200 / 200 / 200 | mutual premium — collectively best |
| S, P, P | 300 / 120 / 120 | solo defector wins big |
| S, S, P | 260 / 260 / 80 | lone holdout punished |
| S, S, S | 120 / 120 / 120 | race to the bottom |

(…and the symmetric permutations.) **Standard strictly dominates Premium for
every firm regardless of rivals' choices** — the textbook 3-player Prisoner's
Dilemma.

- **Nash equilibrium:** (Standard, Standard, Standard) → **$120K each**
- **Cooperative optimum:** (Premium, Premium, Premium) → **$200K each** — *not*
  a Nash equilibrium (any firm gains by defecting)
- **Cooperation gap:** **$80K/firm**

## Why gambit, not nashpy (r110)

`nashpy` handles 2-player normal-form games only. `pygambit` scales to **N
players** and extensive-form games, and supports more equilibrium concepts
(pure/mixed enumeration, correlated, QRE, SPNE). r110 → r115 is the jump from
2-player to the general case.

## Example output (solver=ON, pygambit)

```
## 3-Player Nash Equilibrium Report — 3-Firm SaaS Pricing Triopoly

**Solver:** pygambit   **Players:** Firm A, Firm B, Firm C   **Nash equilibria found:** 1

### Nash Equilibria
| # | Firm A | Firm B | Firm C | Payoff A | Payoff B | Payoff C |
|---|---|---|---|---|---|---|
| 1 | Standard | Standard | Standard | $120.0K | $120.0K | $120.0K |

### Cooperative Optimum (NOT a Nash equilibrium)
| Firm A | Firm B | Firm C | Payoff A | Payoff B | Payoff C |
|---|---|---|---|---|---|
| Premium | Premium | Premium | $200K | $200K | $200K |

### Prisoner's Dilemma Gap
Nash ['Standard','Standard','Standard'] → each earns $120.0K;
cooperative ['Premium','Premium','Premium'] → each earns $200K; gap = $80.0K/firm
```

`ASSERT nash_3p_found` passes (status OK, 1 equilibrium); the LLM then explains
why the collectively-best outcome is individually unstable.

## Run

```bash
# solver=ON — pygambit pure-Nash enumeration
graf run cookbook_solvers/gambit_3player/gambit_3player.graph.yaml \
    --llm claude_cli --param use_solver=true

# solver=OFF — LLM strategic reasoning baseline
graf run cookbook_solvers/gambit_3player/gambit_3player.graph.yaml \
    --llm claude_cli --param use_solver=false
```

## Install

```bash
pip install pygambit      # needs a C++ toolchain (build-essential / Xcode CLT)
```

Or via the bundled extra: `pip install "spl-llm[solver]"`.

## TOOL_API reference

| Function | Purpose |
|---|---|
| `get_default_game()` | Return the default 3-firm pricing game as JSON |
| `find_nash_equilibria_3p(game_json)` | pygambit pure-Nash enumeration → equilibria + cooperation gap |
| `nash_3p_found(result_json)` | ASSERT gate: status OK **and** ≥1 equilibrium |
| `format_gambit_report(result_json)` | Render equilibria + cooperative optimum as markdown |
| `format_report_solver_on / _off` | Assemble the final report |

## Implementation note (pygambit 16.7)

The solver uses the modern pygambit API:
- build with `gbt.Game.from_arrays(A, B, C, title=...)`
- solve with `gbt.nash.enumpure_solve(g).equilibria`
- **iterate** `for player in g.players` and read strategy probabilities with
  `eq[strategy]` — do **not** index `g.players[i]` by integer (in 16.7 that is a
  label lookup and raises `TypeError: Argument 'label' ... expected str, got int`)

The human-readable profile comes from the recipe's own `players`/`strategies`
lists, so gambit's internal integer labels are never touched.

## Related recipes

- **r110** — Nash equilibria, 2-player (nashpy)
- **r111** — Stackelberg sequential game (backward induction)
- **r116** — OpenSpiel CFR: imperfect-information games (the next step beyond pure Nash)
