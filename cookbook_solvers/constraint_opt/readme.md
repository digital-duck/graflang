# Recipe 78 — Constraint Optimization

> **GraphLang port.** Lifted from SPL.py's `cookbook-solver/078_constraint_opt` with `spl3 util spl2graph` (no model was involved). The Python tools travel inside the graph as `SOLVE` nodes (`backend: kernel`), so `graf run` needs the `kernel` extra (`pip install 'graflang[kernel]'`) and the libraries named below, not SPL.py. Commands use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`.
> Not ported: `exp-claude_cli-n05.md`, `run_experiment.sh`, `run_experiment.py`, `experiment.db`, `experiment_H2_scale_sensitivity.md`, `experiment_results.db` (the SPL original's tool registration, experiment and app scripts).
> Test run (2026-11-01, `claude_cli` `claude-sonnet-5-5`, solver on): all 4 graphs completed (8 model calls, 3551 tokens in / 2319 out in total); the SPL token counters `_total_input_tokens`/`_total_output_tokens` were replaced by `globals().get(...)`. A run that completes does not show the answer is right: read the output before you rely on a recipe.

**Category:** reasoning · **Tier:** 2 · **Requires:** `pip install pulp`

## What this demonstrates

This recipe showcases the most distinctive feature of SPL: the **deterministic-probabilistic boundary** — the ability to assign each subtask to the computation mode best suited for it, and to enforce that boundary formally with `ASSERT`.

| Stage | Mode | Tool | Why |
|-------|------|------|-----|
| Parse natural-language problem | **Probabilistic** | LLM (`formulate_lp`) | LLMs read prose; solvers don't |
| Generate PuLP code | **Probabilistic** | LLM | Code synthesis from intent |
| Run LP solver | **Deterministic** | PuLP / CBC | Solver produces proof of optimality |
| Gate on Optimal status | **Deterministic** | `ASSERT is_optimal()` | Formal boundary: execution stops here if solver fails |
| Repair failed code | **Probabilistic** | LLM (`repair_lp`) | LLM sees actual error; rewrites code |
| Interpret result | **Probabilistic** | LLM (`interpret_solution`) | Business-language explanation of verified numbers |

**Key property**: The LLM never does arithmetic. Numbers in the output come exclusively from the solver. The ASSERT gate is the formal oracle — it is structurally impossible for a non-Optimal result to reach the interpretation step.

This boundary is **inexpressible in PDL (https://github.com/IBM/prompt-declaration-language), LangChain, or AutoGen** without external orchestration scaffolding. In SPL it is four tokens: `ASSERT is_optimal(@solution)`.

### Ablation mode: `use_solver=false`

The workflow accepts a `use_solver` flag (default `"true"`) that swaps in a pure-LLM baseline for direct comparison:

| `use_solver` | Stage 1 | Stage 2 | Gate | Metrics tracked |
|---|---|---|---|---|
| `true` | LLM formulates PuLP code → CBC solves (with repair loop) | LLM interprets verified JSON result | `ASSERT is_optimal()` — hard gate | LLM calls, stage-1 latency, stage-2 latency, total |
| `false` | LLM solves directly via corner enumeration (no solver) | — | None | LLM calls, stage-1 latency, total |

Both modes emit a `## Run Metrics` table at the bottom of the report. This makes it easy to compare solution quality, token cost, and latency with and without the deterministic solver rung.



## Setup

### Install PuLP

PuLP is not part of the SPL core install. Add it once to your environment:

```bash
conda activate spl123
pip install pulp        # installs PuLP + the bundled CBC solver binary
```

No additional configuration is needed. CBC (COIN-OR Branch and Cut) is bundled with the PuLP wheel and works offline.

### What is PuLP?

[PuLP](https://coin-or.github.io/pulp/) ([GitHub](https://github.com/coin-or/pulp)) is a Python library for **[Linear Programming (LP)](https://en.wikipedia.org/wiki/Linear_programming) and [Mixed-Integer Programming (MIP)](https://en.wikipedia.org/wiki/Integer_programming)**. You describe an optimization problem in Python — decision variables, an objective function, linear constraints — and PuLP dispatches it to a solver backend (CBC by default). The solver returns not just a solution but a **proof of optimality**: a certificate that no better solution exists within the feasible region.

PuLP sits at the mature, boring end of the operations research stack:
- Open-source, BSD-licensed, actively maintained (v2.x)
- Default backend is [CBC (COIN-OR Branch and Cut)](https://github.com/coin-or/Cbc), one of the best open-source MIP solvers
- Supports optional commercial backends ([Gurobi](https://www.gurobi.com/), [CPLEX](https://www.ibm.com/products/ilog-cplex-optimization-studio), [HiGHS](https://highs.dev/)) via the same API
- Widely used in [supply chain optimization](https://en.wikipedia.org/wiki/Supply_chain_optimization), [scheduling](https://en.wikipedia.org/wiki/Job-shop_scheduling), [resource allocation](https://en.wikipedia.org/wiki/Resource_allocation), [logistics / transportation](https://en.wikipedia.org/wiki/Transportation_theory_(mathematics))

#### Learning resources

| Resource | What you'll learn |
|---|---|
| [PuLP official docs](https://coin-or.github.io/pulp/) | API reference, solver configuration |
| [PuLP case studies](https://coin-or.github.io/pulp/CaseStudies/index.html) | Worked examples: beer distribution, whiskas cat food |
| [LP Wikipedia](https://en.wikipedia.org/wiki/Linear_programming) | Theory: feasible region, simplex, duality |
| [Transportation problem](https://en.wikipedia.org/wiki/Transportation_theory_(mathematics)) | Classic supply-chain LP — ships goods from warehouses to stores at minimum cost |
| [Vehicle routing problem (VRP)](https://en.wikipedia.org/wiki/Vehicle_routing_problem) | Logistics: route a fleet of trucks to serve customers |
| [Job-shop scheduling](https://en.wikipedia.org/wiki/Job-shop_scheduling) | Assign jobs to machines respecting precedence + capacity |
| [Nurse scheduling problem](https://en.wikipedia.org/wiki/Nurse_scheduling_problem) | Staff shift assignment with coverage and fairness constraints |
| [Knapsack / portfolio selection](https://en.wikipedia.org/wiki/Knapsack_problem) | Binary ILP: select best subset under budget/capacity limits |

### Why PuLP for this recipe?

Three reasons it is the right tool for demonstrating SPL's strengths:

**1. The solver verdict is categorical and machine-readable.**  
PuLP returns `{"status": "Optimal"}`, `{"status": "Infeasible"}`, or `{"status": "Error"}`. There is no ambiguity — unlike SQL results or LLM scoring, you cannot argue about whether the answer is correct. This makes it a clean `ASSERT` target.

**2. LP problems have known closed-form optima for verification.**  
The default bakery problem has a hand-verifiable optimum (bread=3, croissants=3, profit=$60). You can confirm the solver's answer with pencil and paper, which makes the demo self-contained and trustworthy as a tutorial.

**3. PuLP is one entry point into a wide class of deterministic solvers — the .spl workflow scales across domains by swapping the backend.**  
LLMs hallucinate LP solutions. Ask any model to maximize profit subject to three resource constraints and it will confabulate numbers that violate the constraints. A solver cannot hallucinate — it either proves global optimality or reports infeasibility. That contrast is the point of this recipe.

But PuLP is only the demo rung. The `GENERATE → CALL solver → ASSERT → WHILE repair` pattern in this workflow extends directly to other solver backends without touching the .spl logic:

| Domain | Replace `run_pulp()` with | What ASSERT checks |
|--------|--------------------------|-------------------|
| Structural engineering | FEniCS / OpenSees FEM solver | stress < yield strength, deflection < limit |
| Semiconductor process | TCAD simulator (Sentaurus, Silvaco) | threshold voltage, leakage within spec |
| Wafer metrology | on-tool measurement API | CD / overlay / film thickness within tolerance |
| Chemical process | Aspen HYSYS / DWSIM flowsheet solver | energy balance, purity ≥ target |
| Circuit design | SPICE / ngspice | gain, bandwidth, phase margin within bounds |
| Supply chain scheduling | OR-Tools CP-SAT solver | all jobs scheduled, no resource overrun |

In every case the .spl workflow is identical in structure. The LLM's job is always the same — read the natural-language specification and write the solver input. The solver's job is always the same — run the physics or mathematics and return a machine-readable verdict. `ASSERT` is always the formal boundary between them. Only the `TOOL_API` body changes, because only the solver changes. This is **DODA** (Design Once, Deploy Anywhere) applied to the deterministic layer: one workflow specification, many physical backends.

## Companion recipes in this directory

Three additional `.spl` files apply the same `GENERATE → CALL solver → ASSERT → WHILE repair → GENERATE interpret` pattern to different PuLP problem domains:

| File | Domain | PuLP type | Default problem |
|---|---|---|---|
| `constraint_opt.graph.yaml` | Production planning | LP | Bakery: bread + croissants, maximize profit |
| `supply_chain.graph.yaml` | Logistics / shipping | LP ([transportation problem](https://en.wikipedia.org/wiki/Transportation_theory_(mathematics))) | 2 warehouses → 3 stores, minimize shipping cost |
| `staff_scheduling.graph.yaml` | HR / operations | ILP ([nurse scheduling](https://en.wikipedia.org/wiki/Nurse_scheduling_problem)) | 4 nurses, 3 shifts, minimize wage cost |
| `resource_allocation.graph.yaml` | Portfolio / strategy | Binary ILP ([knapsack](https://en.wikipedia.org/wiki/Knapsack_problem)) | 6 IT projects, budget + headcount limits, maximize value |

Each recipe is self-contained. The SPL structure is identical — only the tool bodies and LLM prompts change because only the solver problem changes. This is **DODA** in action: the orchestration logic is invariant across domains.

## Run

```bash
# Default problem (bakery production planning) — solver ON
graf run cookbook_solvers/constraint_opt/constraint_opt.graph.yaml \
    --llm claude_cli


# Set problem once; reuse in all commands below
export PROBLEM="A factory makes chairs (2h labor, 4kg wood, \$20 profit) and tables (4h labor, 3kg wood, \$30 profit). Available: 20h labor, 24kg wood. Maximize profit."


# solver ON (default)
graf run cookbook_solvers/constraint_opt/constraint_opt.graph.yaml \
    --llm claude_cli \
    --param problem="$PROBLEM"

# solver OFF — LLM baseline for ablation comparison
graf run cookbook_solvers/constraint_opt/constraint_opt.graph.yaml \
    --llm claude_cli \
    --param use_solver=false \
    --param problem="$PROBLEM"

# More repair attempts (default 3)
graf run cookbook_solvers/constraint_opt/constraint_opt.graph.yaml \
    --llm claude_cli \
    --param max_tries=5 \
    --param problem="$PROBLEM"
```

## Default problem

> A bakery produces artisan bread and croissants. Each loaf of bread requires 3 hours of labor and 2 kg of flour, earning \$12 profit. Each batch of croissants requires 1 hour of labor and 3 kg of flour, earning \$8 profit. The bakery has 12 hours of labor and 15 kg of flour available each day. Maximize daily profit.

**Known optimal** (verifiable by hand): bread = 3, croissants = 3, profit = $60.  
Labor: 3×3 + 3×1 = 12 ✓ · Flour: 3×2 + 3×3 = 15 ✓ · Both constraints binding.

## Execution flow

### solver=ON (default)

```
GENERATE formulate_lp(@problem)     -- LLM writes PuLP code        [LLM call +1]
    │
CALL run_pulp(@lp_code)             -- CBC solver executes
    │
CALL result_status(@solution)       -- extract status string
    │
WHILE @tries < @max_tries
    ├── status = "Optimal" → exit loop
    ├── status = "init"    → first attempt (above)
    └── status = Error/Infeasible
            │
        CALL result_error()         -- get error message
        GENERATE repair_lp()        -- LLM rewrites with error      [LLM call +1]
        CALL run_pulp()             -- retry
            │
ASSERT is_optimal(@solution)        -- hard gate: ToolFailed if not Optimal
    │                                  ◄── stage 1 latency recorded here
GENERATE interpret_solution()       -- LLM explains verified result [LLM call +1]
    │                                  ◄── stage 2 latency recorded here
CALL make_metrics(...)              -- assemble metrics table
CALL format_report(...)             -- Markdown report with metrics
```

### solver=OFF (ablation baseline)

```
GENERATE solve_directly(@problem)   -- LLM enumerates corners,      [LLM call +1]
    │                                  evaluates objective, verifies
    │                                  ◄── stage 1 latency recorded here
CALL make_metrics(...)              -- assemble metrics table
CALL format_report(...)             -- Markdown report with metrics
```

## Output format

### solver=ON

```markdown
# Constraint Optimization Report

**Problem:** ...
**Solver status:** `Optimal`
**Optimal objective value:** 168

**Decision variables:**
  - chairs = 3.6
  - tables = 3.2

## Interpretation
...

## Solution Verification
- Labor: 2(3.6) + 4(3.2) = 7.2 + 12.8 = 20h ✓ (binding)
- Wood:  4(3.6) + 3(3.2) = 14.4 + 9.6 = 24kg ✓ (binding)
- Profit: 3.6 × $20 + 3.2 × $30 = $72 + $96 = $168 ✓

## Solver Code (LLM-generated, PuLP)
```python
...
```

## Run Metrics

| Metric | Value |
|---|---|
| Mode | solver=ON  (PuLP/CBC + ASSERT gate) |
| LLM calls | 2 |
| Stage 1 — formulation + solve (s) | 7.00 |
| Stage 2 — interpretation (s) | 14.90 |
| Total latency (s) | 22.60 |
| Input tokens | 541 |
| Output tokens | 441 |
| Total tokens | 982 |
```

### solver=OFF

```markdown
# Constraint Optimization Report

**Problem:** ...

## Solution
...

## Verification
...

## Run Metrics

| Metric | Value |
|---|---|
| Mode | solver=OFF (LLM reasoning only) |
| LLM calls | 1 |
| Stage 1 — direct LLM solve (s) | 44.70 |
| Stage 2 — interpretation (s) | — |
| Total latency (s) | 45.20 |
| Input tokens | 275 |
| Output tokens | 760 |
| Total tokens | 1,035 |
```

## Why deterministic workflow matters — observed results

The `use_solver` ablation on the chairs-and-tables factory problem (claude-sonnet-4-6, 2026-08-30) produced a striking result:

| Metric | solver=ON | solver=OFF | Δ |
|---|---|---|---|
| LLM calls | 2 | 1 | solver=OFF uses fewer calls… |
| Stage 1 latency | 7.0s | 44.7s | …but Stage 1 is **6.4× slower** |
| Stage 2 latency | 14.9s | — | |
| **Total latency** | **22.6s** | **45.2s** | **solver=ON is 2× faster end-to-end** |
| Input tokens | 541 | 275 | solver=ON sends more context (code + JSON) |
| Output tokens | **441** | **760** | solver=OFF generates **72% more output tokens** |
| **Total tokens** | **982** | **1,035** | similar volume, opposite composition |
| Optimality guarantee | ✅ CBC proof | ❌ none | |
| Answer correctness | ✅ verified by ASSERT | ⚠️ LLM arithmetic, may hallucinate | |

**What this tells us:**

1. **The token composition tells the real story.** Total token counts are nearly identical (982 vs 1,035 — a 5% difference), but the mix is opposite: solver=OFF generates **72% more output tokens** (760 vs 441) while consuming far fewer input tokens. Output tokens are what slow the LLM down and drive up cost on per-token APIs — solver=OFF's single call takes 44.7s because the model must generate a long reasoning chain. solver=ON splits the work: short code synthesis (Stage 1) + short interpretation of a pre-computed JSON result (Stage 2).

2. **Fewer LLM calls ≠ faster or cheaper.** solver=OFF uses one call, but that call is 6.4× slower than solver=ON's Stage 1 alone. The 72% output-token gap is exactly the reasoning work the solver would have done for free in microseconds.

3. **solver=ON adds a correctness guarantee at negative latency cost.** The ASSERT gate is not overhead — it is the mechanism that lets the LLM skip the arithmetic entirely. The solver proves optimality in milliseconds; the LLM never touches a number.

4. **This generalises beyond LP.** Wherever a deterministic oracle exists (physics simulator, symbolic solver, formal verifier, database query), plugging it in via `CALL solver → ASSERT` relieves the LLM of the hardest part of the task — and makes the output provably correct. This is the core value proposition of SPL's deterministic-probabilistic boundary.

> *"The token counts are nearly the same — but solver=ON spends them differently: less generation, more correctness."*

## Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `problem` | TEXT | bakery LP | Natural-language optimization problem |
| `use_solver` | TEXT | `"true"` | `"true"` = PuLP/CBC pipeline; `"false"` = LLM-only baseline |
| `max_tries` | INTEGER | `3` | Max LLM repair attempts before giving up (solver=ON only) |
| `lang` | TEXT | `"English"` | Output language for interpretation |
| `out_dir` | TEXT | `./cookbook/78_constraint_opt/output` | Directory for the generated report |

## Exception handling

If the solver cannot reach Optimal status within `max_tries`, `ASSERT is_optimal` raises `ToolFailed`, caught by `EXCEPTION WHEN ToolFailed THEN`. The workflow exits with `status = "infeasible"` and a diagnostic message. This means the report variable always carries either a verified solution or an explicit failure — never a hallucinated number.

The `use_solver=false` path has no ASSERT gate and therefore never raises `ToolFailed` — it always produces output, but that output carries no optimality guarantee.

## Connection to TMLR paper

This recipe is the reference implementation for **Appendix — Domain #1: Constraint Optimization** in the SPL TMLR submission. It demonstrates that `ASSERT` is a **ground-truth oracle**, not just execution-success tracking:

- Execution success (code ran without Python exception) ≠ Optimal solution
- `ASSERT is_optimal()` distinguishes these: `{"status": "Infeasible"}` is a successful execution that returns a wrong answer
- This is the rebuttal to ZXT2's claim that ASSERT only tracks "code ran"

The same `GENERATE → SOLVE → ASSERT → WHILE` pattern replicates directly to:
- **Recipe 75** (SymPy): symbolic algebra verifier rung
- **Recipe 76** (Lean): formal proof verifier rung
- **Recipe 78** (PuLP): combinatorial optimization verifier rung

## Experiment runner

`run_experiment.py` is the systematic harness for the solver=ON vs solver=OFF ablation study. It follows the same design as `cookbook/77_neurosymbolic/run_experiment.py` — SQLite persistence, multi-axis CLI, streaming output.

### Axes

| Flag | Values | What it controls |
|---|---|---|
| `-r` / `RECIPES=` | `r78a` `r78b` `r78c` `r78d` | Which recipe (LP / transport LP / ILP / Binary ILP) |
| `-m` / `MODELS=` | `m001` (sonnet-4-6) `m002` (gemma3) `m003` (gemma4:e2b) … | Which model/adapter |
| `-n` / `SIZES=` | `n05` `n10` `n20` | Problem scale (default / H2 scaled / large) |
| `-s` / `SOLVERS=` | `true` `false` | solver=ON (PuLP+ASSERT) vs solver=OFF (LLM only) |
| `-k` | integer | Repetitions per cell |

`n05` uses the default problem embedded in each `.spl` file (hand-verifiable, ≤ 6 variables). `n10` and `n20` are the H2 scale problems documented in `experiment_H2_scale_sensitivity.md`.

### Quick start

```bash
conda activate spl123
cd ~/projects/digital-duck/SPL.py

# List all available recipe and model IDs
python cookbook/78_constraint_opt/run_experiment.py --list

# H1: one recipe, one model, default scale, both arms
bash cookbook/78_constraint_opt/run_experiment.sh -r r78d -m m001 -n n05
# bash cookbook/78_constraint_opt/run_experiment.sh -r r78d -m m002 -n n05

# H2: run 4 recipes with claude/gemma3 for size=10,20
bash cookbook/78_constraint_opt/run_experiment.sh -m m001 -n n05,n10,n20 -s true
# Log: cookbook/78_constraint_opt/logs/recipe-78-log-20260830-175154.md


# solver=OFF tax heavily on LLM
LLM_TIMEOUT=1800 \
   bash cookbook/78_constraint_opt/run_experiment.sh -m m001 -n n05,n10,n20 -s false
# 4/12 done

# run in smaller batch to avoid session limit
# Batch 2 — r78b n10,n20 (2 cells)
LLM_TIMEOUT=1800 bash cookbook/78_constraint_opt/run_experiment.sh -r r78b -m m001 -n n10,n20 -s false
# Log: cookbook/78_constraint_opt/logs/recipe-78-log-20260830-202050.md

# Batch 3 — r78c all sizes (3 cells)
LLM_TIMEOUT=1800 bash cookbook/78_constraint_opt/run_experiment.sh -r r78c -m m001 -n n05,n10,n20 -s false
# Log: cookbook/78_constraint_opt/logs/recipe-78-log-20260830-203434.md

# Batch 4 — r78d all sizes (3 cells)
LLM_TIMEOUT=1800 bash cookbook/78_constraint_opt/run_experiment.sh -r r78d -m m001 -n n05,n10,n20 -s false
# Log: cookbook/78_constraint_opt/logs/recipe-78-log-20260830-204031.md


LLM_TIMEOUT=1800 \
   bash cookbook/78_constraint_opt/run_experiment.sh -m m001,m002 -n n05,n10,n20 -s false

# see /home/papagame/projects/digital-duck/SPL.py/cookbook/78_constraint_opt/logs/recipe-78-log-20260830-131237.md

# Full H2 scale-sensitivity study (all recipes, all scales)
bash cookbook/78_constraint_opt/run_experiment.sh \
    -r r78a,r78b,r78c,r78d -m m001 -n n05,n10,n20

# Swap to gemma3 for model comparison
MODELS="m001 m002" SIZES="n05 n10" \
    bash cookbook/78_constraint_opt/run_experiment.sh -r r78d

# solver=ON only (ground-truth pass to establish known optima)
bash cookbook/78_constraint_opt/run_experiment.sh -r r78d -m m001 -n n10,n20 -s true

# Dry run — shows commands without executing
python cookbook/78_constraint_opt/run_experiment.py \
    -r r78a,r78d -m m001,m002 -n n05,n10 --dry-run
```

### What gets logged to SQLite

Every cell (recipe × model × n_size × solver × run) writes one row to `experiment_results.db`:

| Column | Source | Notes |
|---|---|---|
| `recipe_id` / `recipe_name` | runner | e.g. `r78d` / `resource_allocation` |
| `model_id` / `model_label` | runner | e.g. `m001` / `sonnet-4-6` |
| `n_size` | runner | `n05` / `n10` / `n20` |
| `solver` | runner | `true` / `false` |
| `status` | spl3 RETURN | `complete` / `infeasible` |
| `objective_claimed` | `RETURN … objective=` | solver=ON: CBC result; solver=OFF: LLM's claimed value |
| `correct` | post-hoc backfill | 1 if solver=OFF objective matches solver=ON ground truth |
| `verify_status` | `RETURN … verify=` | solver=OFF only: `PASS` / `FAIL` / `UNPARSEABLE` |
| `llm_calls` | `LLM calls:` stdout line | |
| `latency_ms` | `Latency:` stdout line | |
| `input_tokens` / `output_tokens` | `tokens_in=` / `tokens_out=` LOGGING line | |

After each run `backfill_correct()` matches solver=OFF rows against solver=ON ground truth for the same (recipe, model, n_size) cell and sets `correct`.

### Verification for solver=OFF

When `use_solver=false`, the workflow adds two extra LLM calls after the direct solve:

1. `extract_solution_json_*` — asks the LLM to structure its own answer (variable values, constraint coefficients, selected projects, etc.) as JSON
2. `verify_off_*` (TOOL_API) — re-computes all constraint LHS values in Python from the extracted JSON, compares against problem RHS values, re-computes the objective independently

The `verify_status` field records the verdict: `PASS` (constraints satisfied, objective consistent), `FAIL` (violation or arithmetic mismatch), or `UNPARSEABLE` (LLM returned unstructured text). This catches hallucinations that look correct in prose but violate constraints arithmetically.

### Analysis queries

```sql
-- Correctness by recipe and scale
SELECT recipe_name, n_size,
       AVG(CASE WHEN solver='true'  THEN pass       END) AS on_pass_rate,
       AVG(CASE WHEN solver='false' THEN correct     END) AS off_correct_rate,
       AVG(CASE WHEN solver='false' THEN
               verify_status = 'PASS' END)               AS off_verify_pass_rate
FROM results
GROUP BY recipe_name, n_size;

-- Token cost comparison
SELECT recipe_name, n_size, solver,
       AVG(input_tokens)  AS avg_in,
       AVG(output_tokens) AS avg_out,
       AVG(latency_ms)    AS avg_ms
FROM results
WHERE status = 'complete'
GROUP BY recipe_name, n_size, solver;

-- solver=OFF failures: what did the LLM claim vs ground truth?
SELECT recipe_name, model_label, n_size,
       objective_claimed,
       verify_status, correct
FROM results
WHERE solver = 'false'
ORDER BY recipe_name, n_size, correct;
```

### Output files

| Path | Contents |
|---|---|
| `logs/recipe-78-log-<timestamp>.md` | Full streaming output for every cell in the run |
| `output/constraint_opt_<timestamp>.md` | Per-run formatted report (solver code, metrics table) |
| `experiment_results.db` | SQLite DB — single source of truth for analysis |
| `exp-claude_cli-n05.md` | Hand-annotated experiment results for model=claude_cli, n05 |
