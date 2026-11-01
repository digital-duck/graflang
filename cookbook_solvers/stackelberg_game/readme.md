# Recipe 111 — Stackelberg Sequential Game (Backward Induction)

> **GraphLang port.** Lifted from SPL.py's `cookbook-solver/111_stackelberg_game` with `spl3 util spl2graph` (no model was involved). The Python tools travel inside the graph as `SOLVE` nodes (`backend: kernel`), so `graf run` needs the `kernel` extra (`pip install 'graflang[kernel]'`) and the libraries named below, not SPL.py. Commands use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`.
> Not ported: `tools.py` (the SPL original's tool registration, experiment and app scripts).
> Smoke test (2026-11-01, placeholder model, no real model call): runs end to end with the placeholder model. This is a run-through of the graph, not a check that the answers are right: run it with a real model before you rely on it.

**The key story:** A market leader sets subscription price first; the follower observes and responds. LLM says "price High (\$100) to signal quality." Backward induction: if the leader prices High, the follower always undercuts to Low and earns \$52K while the leader earns \$12K. The leader anticipates this and prices Low instead — ending at (Low, Low) = (\$28K, \$22K). The first-mover advantage is in correctly anticipating the follower's response, not in premium pricing.

## What it demonstrates

| Axis | solver=ON | solver=OFF |
|---|---|---|
| Engine | Backward induction (pure Python) | LLM sequential reasoning |
| Structure | Extensive form: leader moves first, follower observes | Simultaneous-style reasoning applied to sequential game |
| Output | SPNE: action sequence + payoffs | "Leader should price High to signal quality" |
| Verification | `ASSERT spne_solved` (C1) | — |
| Solver class | C1 (categorical: SPNE found) | — |

## The game tree

```
Leader chooses:
├── High ($100)
│   └── Follower responds:
│       ├── High ($100) → Leader=$38K, Follower=$38K
│       └── Low  ($70)  → Leader=$12K, Follower=$52K  ← follower best-response
└── Low ($70)
    └── Follower responds:
        ├── High ($100) → Leader=$50K, Follower=$14K
        └── Low  ($70)  → Leader=$28K, Follower=$22K  ← follower best-response
```

**Backward induction**:
1. If leader plays High: follower chooses Low (\$52K > \$38K) → leader gets \$12K
2. If leader plays Low: follower chooses Low (\$22K > \$14K) → leader gets \$28K
3. Leader compares: \$28K (play Low) > \$12K (play High) → **leader plays Low**

**SPNE**: (Low, Low) → Leader=\$28K, Follower=\$22K

### Subgame-Perfect Nash Equilibrium (**SPNE**)

It refines Nash equilibrium for sequential (extensive-form) games: not only must no player want to deviate at the top level, but the strategy must also prescribe rational play in every subgame (every decision point reachable in the tree). Backward induction is the standard algorithm for finding it.

## Simultaneous vs Sequential (r110 vs r111)

| | r110 (Nash, simultaneous) | r111 (SPNE, sequential) |
|---|---|---|
| Game structure | Both choose at same time | Leader commits first |
| Solution concept | Nash equilibrium | Subgame-perfect Nash equilibrium |
| Outcome | (Low, Low) = (\$25K, \$25K) | (Low, Low) = (\$28K, \$22K) |
| Leader advantage | None (symmetric) | +\$3K from first-mover anticipation |

## Run commands

```bash
# solver=ON — backward induction
graf run ~/.graflang/solvers/stackelberg_game/stackelberg_game.graph.yaml \
    --llm claude_cli --param use_solver=true

# solver=OFF — LLM sequential reasoning
graf run ~/.graflang/solvers/stackelberg_game/stackelberg_game.graph.yaml \
    --llm claude_cli --param use_solver=false
```

## Install

```bash
conda activate spl123
# No additional install — pure Python backward induction
```

## TOOL_API reference

| Function | Purpose |
|---|---|
| `get_default_game()` | Returns Stackelberg game tree JSON |
| `solve_stackelberg(game_json)` | Backward induction → SPNE path + payoffs |
| `spne_solved(result_json)` | ASSERT gate: status OK |
| `format_stackelberg_report(result_json)` | Markdown: SPNE path table + LLM comparison |

## Related recipes

- r110: Nash equilibrium (simultaneous game — no time structure)
- r112: Optuna black-box (no strategic interaction, just parameter optimization)
- r102: Z3 SMT (logical constraint satisfiability, not game equilibria)
