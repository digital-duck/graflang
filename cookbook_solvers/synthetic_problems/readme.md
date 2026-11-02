# Recipe 109 — Synthetic Problem Generator

> **GraphLang port.** Lifted from SPL.py's `cookbook-solver/109_synthetic_problems` with `spl3 util spl2graph` (no model was involved). The Python tools travel inside the graph as `SOLVE` nodes (`backend: kernel`), so `graf run` needs the `kernel` extra (`pip install 'graflang[kernel]'`) and the libraries named below, not SPL.py. Commands use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`.
> Not ported: `tools.py` (the SPL original's tool registration, experiment and app scripts).
> Test run (2026-11-01, `claude_cli` `claude-sonnet-5-5`, solver on): the graph completed (2 model calls, 1079 tokens in / 1887 out in total). A run that completes does not show the answer is right: read the output before you rely on a recipe.

**Purpose:** Turn one verified (problem, optimal) pair into a labeled test suite of N variants — expanding the benchmark space for any solver recipe without writing problems by hand.

## Why this matters

LLM problem decomposition (NL → solver formulation) is the ceiling on solver=ON correctness (findings F11, F12 from r78 ablation). To measure that ceiling systematically you need labeled (problem_text, known_optimal) pairs across a range of difficulties. Writing them by hand is slow; this recipe generates them automatically and verifies each one with the same solver.

The output — a JSON test suite with verified optima — is directly usable as:
- **Benchmark input** for solver=ON vs solver=OFF ablation sweeps across models
- **Training data** for a problem-decomposition fine-tune or router
- **Regression suite** for a given .spl script (same workflow, N problems instead of 1)

## Architecture

```
LLM generates N variants        ← structured JSON (problem_text + formal spec)
    ↓
WHILE repair loop               ← fixes malformed JSON (≤ 3 attempts)
    ↓
ASSERT has_valid_variants       ← at least 1 valid before proceeding
    ↓
batch_solve (TOOL_API)          ← routes to domain solver, returns verified optima
    ↓
format_test_suite               ← markdown table: ID / domain / status / optimal
    ↓
save_test_suite                 ← output/{domain}_{timestamp}.json
    ↓
LLM analyzes difficulty spread  ← which variant stresses decomposition most?
```

## What the LLM generates

Each variant is a structured JSON object with **both** the natural-language description and the formal solver spec in one shot:

```json
{
  "id": "v003",
  "domain": "LP",
  "problem_text": "A bakery produces muffins ($4 profit, 1 labor-hour, 2 kg flour) ...",
  "variables": [{"name": "muffins", "type": "continuous", "lb": 0}, ...],
  "objective": {"sense": "maximize", "coefficients": {"muffins": 4, ...}},
  "constraints": [{"name": "labor", "lhs": {"muffins": 1}, "op": "<=", "rhs": 40}, ...]
}
```

This means `batch_solve` can construct the PuLP model directly from the JSON — no secondary NL parsing, no extra LLM call.

## Supported domains

| Domain | Solver | Verification |
|---|---|---|
| `LP` | PuLP + CBC (continuous vars) | `status == Optimal` (C1) |
| `ILP` | PuLP + CBC (integer vars) | `status == Optimal` (C1) |
| `supply-sourcing` | PuLP + CBC (B1 pattern) | `status == Optimal` (C1) |

Additional domains (production, workforce, job-shop) can be added by extending `batch_solve` in `tools.py`.

## Run commands

```bash
# n05: small LP problems (5 products) — mirrors r78 n05 baseline
graf run cookbook_solvers/synthetic_problems/synthetic_problem_gen.graph.yaml \
    --llm claude_cli \
    --param domain=LP \
    --param n_variants=5 --param n_size=5

# n10: medium scale — where gemma3 formulation starts to degrade (per r78 H2)
graf run cookbook_solvers/synthetic_problems/synthetic_problem_gen.graph.yaml \
    --llm claude_cli \
    --param domain=LP \
    --param n_variants=5 --param n_size=10

# n20: large scale — crossover point where solver=OFF collapses
graf run cookbook_solvers/synthetic_problems/synthetic_problem_gen.graph.yaml \
    --llm claude_cli \
    --param domain=LP \
    --param n_variants=5 --param n_size=20

# Supply-sourcing n10 (10 suppliers, B1 pattern)
graf run cookbook_solvers/synthetic_problems/synthetic_problem_gen.graph.yaml \
    --llm claude_cli \
    --param domain=supply-sourcing \
    --param n_variants=5 --param n_size=10

# Custom reference problem + ILP at n08
graf run cookbook_solvers/synthetic_problems/synthetic_problem_gen.graph.yaml \
    --llm claude_cli \
    --param domain=ILP \
    --param n_variants=5 --param n_size=8 \
    --param sample_problem="A knapsack has capacity 15 kg. Items: A (value=10, weight=5), B (value=6, weight=3), C (value=12, weight=7). Maximize total value. Variables are binary (0/1). Known optimal: select A and C, value=22."
```

## Output

Results saved to `output/{domain}_{timestamp}.json`:

```json
{
  "status": "OK",
  "n_total": 5,
  "n_optimal": 4,
  "n_failed": 1,
  "results": [
    {
      "id": "v001",
      "domain": "lp",
      "problem_text": "A bakery produces muffins...",
      "solver_status": "OPTIMAL",
      "optimal": 160.0,
      "variables": {"muffins": 20.0, "cakes": 10.0}
    },
    ...
  ]
}
```

## Parameters

| Parameter | Default | Description |
|---|---|---|
| `sample_problem` | B3 production problem | Reference problem with known optimal |
| `domain` | `LP` | `LP`, `ILP`, or `supply-sourcing` |
| `n_variants` | `5` | Number of variants to generate per batch |
| `n_size` | `5` | Decision variables per problem — mirrors r78 scale levels (n05/n10/n20) |

### `n_size` semantics by domain

| Domain | n_size means | n05 | n10 | n20 |
|---|---|---|---|---|
| LP / ILP | number of products / items | 5 products | 10 products | 20 products |
| supply-sourcing | number of suppliers | 5 suppliers | 10 suppliers | 20 suppliers |

Larger `n_size` stresses the LLM's constraint-mapping ability. Per r78 H2: gemma3 solver=ON degrades at n10/n20; solver=OFF collapses to 0/4 at n10. Use `n_size` to find the crossover point for any model.
| `scale` | `similar` | `similar` (same size) / `larger` (add variables) / `varied` (mix) |

## Actual run results (LP, claude-sonnet-4-6, 5 variants each)

Three runs executed with `--param domain=LP --param n_variants=5` at n_size=5, 10, 20.

| Run | Solve rate | Fractional optima | Latency | Repair loops |
|---|---|---|---|---|
| n=5  | 5/5 (100%) | 1/5 — v004: 202.91 | 360s | 0 |
| n=10 | 5/5 (100%) | 1/5 — v005: 1083.33 | 198s | 0 |
| n=20 | 5/5 (100%) | 1/5 — v001: 13333.33 | 497s | 0 |

### Are these results expected?

**Solver solve rate (100% all scales):** expected. PuLP/CBC solves well-posed LP in milliseconds regardless of n. These generated problems have bounded variables and feasible regions — no repair loops needed. The 100% rate tells us nothing about LLM accuracy; it only confirms the generator produces valid LP instances.

**Exactly 1 fractional optimum per suite:** consistent across all three runs and likely a structural artifact of the generator — one of the 5 problem templates consistently produces tighter constraint geometry where multiple constraints bind simultaneously at a non-integer vertex. Fractional optima are the hardest instances for solver=OFF (the LLM must reproduce the exact vertex coordinates, not just a plausible round number).

**Round optima dominate at n=20** (5000, 600, 5600, 4000, except v001 at 13333.33): confirms the LLM's own assessment that n=20 problems have loose constraints and a single dominant binding constraint class. For LP solver benchmarking these are too easy — a solver=OFF LLM can often guess the correct answer for round-optimum instances by inspection.

**Latency non-monotonic** (n=5: 360s > n=10: 198s < n=20: 497s): the bottleneck is LLM output length (difficulty analysis prose), not problem computation. n=10's analysis was more concise.

### LLM difficulty predictions (from the analysis sections)

| Run | Predicted solver=OFF accuracy | Key stress-test variant |
|---|---|---|
| n=5  | Artificially high — LLMs can inspect 5-variable systems | v004 (202.91 fractional — multiple constraints bind) |
| n=10 | 60–80% — coefficient mapping errors start accumulating | v005 (1083.33 fractional, scaled units — "100-lb bunches") |
| n=20 | 60–75% strong models; weaker models drop variables near end of list | v001 (13333.33 fractional, 20 products, mixed profit magnitudes) |

### Next steps recommended by the LLM

Scale to **n=50** with **constraint tightness ≤ 5% RHS slack** — the interesting solver=OFF failure cliff is predicted between n=30 and n=75. Tighter constraints simultaneously stress variable-count decomposition and near-degenerate vertex geometry. Also: run the generated JSONs through r78 with `solver=OFF` to measure actual LLM accuracy on these labeled benchmarks.

## Related recipes

- r78: constraint optimization — the primary target for LP test suites
- r100: supply sourcing — target for supply-sourcing test suites
- r101: production sustainability — target for LP + multi-objective suites
- r68: answer-first problem generator — SymPy-domain counterpart
