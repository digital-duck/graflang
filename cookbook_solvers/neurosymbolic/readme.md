# Recipe 77 — Neurosymbolic: One Workflow, the Whole Verifier Ladder

> **GraphLang port.** Lifted from SPL.py's `cookbook-solver/077_neurosymbolic` with `spl3 util spl2graph` (no model was involved). The Python tools travel inside the graph as `SOLVE` nodes (`backend: kernel`), so `graf run` needs the `kernel` extra (`pip install 'graflang[kernel]'`) and the libraries named below, not SPL.py. Commands use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`.
> `symbolic_math.spl` are SPL workflows that graphs here call (`procedure_ref`); running those graphs also needs SPL.py importable (`pip install 'graflang[spl]'`).
> The lift skipped statements GraphLang has no node for: symbolic_math.spl: COMMIT inside a WHILE body was skipped (a LOOP body cannot reach wf_exit).
> `sympolic_tools.spl` define tools only (no workflow) and are not ported.
> Dropped from the commands, as `graf run` has no such option: `--kernel`. `--kernel-name NAME` is there and means what it does in `spl3 run`.
> Not ported: `hackernews-v0.1.md`, `experiment_failure_modes.csv`, `experiment_results_by_model.csv`, `HackerNews-v1.1.md`, `expected_answers_DRAFT.md`, `HackerNews-v1.2.md`, `roundtrip_verification_report.md`, `run_extra_backend_split.sh`, `run_experiment.sh`, `experiment_results_backup_2026-07-17_pre-go-run.db`, `run_experiment_momagrid.py`, `experiment_results_by_run.csv`, `hackernews-v0.2.md`, `Show-HN-v1.0.md`, `app_experiment.py`, `run_experiment.py`, `experiment_aggregation_summary.md`, `hackernews-v0.3.md`, `analyze_experiment.py`, `verify_roundtrip.py`, `roundtrip_checks.py`, `compute_expected_DRAFT.py`, `latex_tables_for_paper.tex`, `HackerNews-v1.0-outline.md`, `experiment_results_by_tier_backend.csv`, `HackerNews-v1.0.md`, `roundtrip_verification_results.csv`, `experiment_results.db`, `SPL-workflow.png`, `ollama_pull_models.sh` (the SPL original's tool registration, experiment and app scripts).
> Test run (2026-11-01, `claude_cli` `claude-sonnet-5-5`, solver on): all three rungs were tried. `backend=sympy` and the default `backend=sage` (run with `--kernel-name sagemath`, see below) complete with the right answer for "differentiate 3*x**3-x, then factor if needed, finally solve for x" (x = ±1/3). `backend=lean` completes but reports `unverified` for a claim about real numbers, because the Lean installation here has no Mathlib (`ℝ` is unknown); claims over `Nat` are proved (see `lean_proof`). It needs SPL.py importable (`procedure_ref`); `sympolic_tools.spl` and `roundtrip_checks.py` were copied next to the graph. A run that completes does not show the answer is right: read the output before you rely on a recipe.
> The Sage rung needs the SageMath kernel: `pip install 'spl-llm[sage]'`, `python -m sage.repl.ipython_kernel.install --user`, then `graf run ... --kernel-name sagemath` (the SPL original's `--kernel-name`).

**Pattern:** ONE declarative workflow (`symbolic_math.graph.yaml`) where the
probabilistic regime (`GENERATE` — plan, formalize, judge, narrate) and the
deterministic regime (SymPy / SageMath / Lean 4 + mathlib — compute, typecheck,
kernel-check) compose seamlessly, and the deterministic backend is selected by
a single `--param backend=` flip.

This is the capstone of the verifier-ladder track
([`docs/DEV/sage_lean_integration_plan.md`](../../docs/DEV/sage_lean_integration_plan.md)):
recipe 67 proved the SymPy rung, recipe 75 the Sage rung, recipe 76 the Lean
rung — recipe 77 puts all three behind the *same* problem text, the *same*
models, and the *same* experiment harness.

## What this demonstrates

```
Probabilistic  (LLM)      — decompose the problem into a chain   (sympy/sage)
Deterministic  (SymPy)    — exact instances: diff, integrate, solve, ...
Deterministic  (Sage)     — instances SymPy can't reach: Galois groups (PARI),
                            rational points on conics over ℚ, elliptic-curve
                            rank, exact algebraic eigenvalues
Probabilistic  (LLM)      — explain the verified chain
       — or, for claims —
Probabilistic  (LLM)      — formalize the claim as a mathlib proposition
Deterministic  (Lean)     — statement_ok typecheck, capped repair loop
Probabilistic  (LLM)      — faithfulness judge (§B.4) — UNFAITHFUL gates the proof
Deterministic  (Lean)     — find_citation: exact? locally, Loogle fallback,
                            EVERY candidate kernel-checked (B-5)
Deterministic  (Lean)     — LLM tactic proof, kernel-checked repair loop (B-3)
```

The epistemic difference between the rungs is the point
(plan §1): SymPy/Sage verify **instances** (*this* Galois group, *this*
eigenvalue), Lean verifies **statements** (`∀ a : ℝ, 0 ≤ a ^ 2` — the theorem
itself). The lean arm returns its badge as the run status —
`machine_proved` / `statement_checked` / `unfaithful` / `unverified` — so the
harness scores proof-grade outcomes honestly.

## Files

| File | Role |
|---|---|
| `sympolic_tools.spl` | Shared TOOL_API + FUNCTION library — both chain kernels (`solve_step_with_sympy`, `solve_step_with_sage`, same `<bare>\|<readable>` protocol and `solver_error` sentinel), Lean helpers (`strip_fences`, `make_theorem`, `lean_report`), and all LLM prompt templates (decompose/explain/solve-directly + the mathlib formalize/judge/tactics set) |
| `symbolic_math.graph.yaml` | The workflow: `neurosymbolic_solver` routes on `@backend` (sympy \| sage \| lean) and `@enable_solver` (verified arm vs LLM-only baseline); `solve_chain_step` dispatches one chain step to the chosen engine |
| `run_experiment.py` | CLI harness: problems × models × solver × runs, sequential; m001–m010 including claude_cli reference; results in SQLite |
| `run_experiment_momagrid.py` | Distributed variant: routes LLM calls through Momagrid Hub, parallel cell dispatch via `--workers N`; auto-skips non-ollama models (m001); same SQLite DB |
| `run_experiment.sh` | Thin driver: activates `spl123`, forwards to `run_experiment.py` (env-var presets `MODELS` / `PROBLEMS` / `SOLVER_MODES` / `BACKEND` / `N_RUNS` still work, recipe-67 style) |

## The problem battery

`p001`–`p020` are recipe 67's battery, kept verbatim (Tier 0–5, diff → ODEs)
— **with the compute engine swapped from SymPy to SageMath** as the
per-problem default. Sage subsumes the SymPy operations (every shared op is
exact — eigenvalues come back as `5/2 ± √33/2`, not floats), so the swap is
one dispatch branch, not a rewrite; `--backend sympy` re-runs the identical
battery on the old rung for comparison.

New problems extend the ladder:

| IDs | Tier | Backend | What they add |
|---|---|---|---|
| `p021`–`p024` | T6 | sage | Operations SymPy cannot do: Galois group of `x⁵−x−1` (PARI), rational point on `x²+y²=3z²`, Mordell–Weil rank of an elliptic curve, factorization over ℚ |
| `p025`–`p029` | P1–P2 | lean | Prose **claims** proved against mathlib: commutativity of ℕ-addition, `0 ≤ a²` over ℝ, the triangle inequality, infinitude of primes, evenness closure |

## Provisioning

```bash
# SymPy — already in the spl123 env
pip install 'spl-llm[sage]'                            # Sage (passagemath wheels, same interpreter)
bash cookbook/tools/lean/setup_lean.sh --with-mathlib  # Lean + mathlib (~5 GB olean cache, one-time)
```

## Run

Single problems, three rungs, one flag apart:

```bash
# Sage rung (default backend): Galois group — SymPy cannot do this
graf run cookbook_solvers/neurosymbolic/symbolic_math.graph.yaml --llm claude_cli \
    --param problem="find the Galois group of x**5 - x - 1 over the rationals"

# SymPy rung: same chain machinery, classic battery
graf run cookbook_solvers/neurosymbolic/symbolic_math.graph.yaml --llm claude_cli \
    --param backend=sympy --param problem="differentiate 3*x**3-x, then factor if needed, finally solve for x"

# Lean rung: a CLAIM, kernel-checked against mathlib (citation-first)
graf run cookbook_solvers/neurosymbolic/symbolic_math.graph.yaml --llm claude_cli \
    --param backend=lean --param problem="the square of any real number is nonnegative"

# Baseline arm: same problem, NO verifier — the A/B contrast
graf run cookbook_solvers/neurosymbolic/symbolic_math.graph.yaml --llm claude_cli \
    --param backend=lean --param enable_solver=false \
    --param problem="the square of any real number is nonnegative"
```

The experiment harness (axes: problems × models × solver on/off × repetitions,
plus the backend override):

```bash
python cookbook/77_neurosymbolic/run_experiment.py --list          # see all IDs
python cookbook/77_neurosymbolic/run_experiment.py -m m001 -p p021  # smoke: Galois
python cookbook/77_neurosymbolic/run_experiment.py -m m001 -p p025  # smoke: Lean citation
python cookbook/77_neurosymbolic/run_experiment.py -m m001 -p "p001,p003" --backend sympy
python cookbook/77_neurosymbolic/run_experiment.py -m "m001,m010"   # full battery, 2 models

# or via the driver (recipe-67 style env presets)
MODELS=m001 PROBLEMS=p025 bash cookbook/77_neurosymbolic/run_experiment.sh
```

## Running on Mac Mini over Momagrid (distributed grid)

`run_experiment_momagrid.py` is the distributed variant of the harness.
It routes all LLM inference through a [Momagrid Hub](https://github.com/digital-duck/momagrid)
and dispatches cells concurrently across GPU worker nodes, reducing wall-clock
time from ~60 min (sequential) to ~20 min with 3 workers.

### Setup

**On the Mac Mini (requester / orchestrator):**
```bash
conda activate spl123
export MOMAGRID_HUB_URL=http://192.168.0.170:9000/   # persist in ~/.zshrc
```
The Mac Mini orchestrates all workflow logic — SPL executor, IPython kernel
(SymPy / Sage / Lean), SQLite writes. It never runs model inference.

**On each GPU worker node** (only Ollama + model weights required):
```bash
# worker nodes do NOT need sympy, sage, or lean installed
ollama serve
# register with the Hub so it can dispatch to this node
```

### Architecture

```
Mac Mini (requester)
  ├── SPL executor    — WHILE / EVALUATE / CALL orchestration
  ├── IPython kernel  — SymPy / Sage / Lean solver logic
  ├── SQLite writer   — experiment_results.db
  └── spl3 subproc ──► Momagrid Hub ──► GPU node A (gemma3, qwen2.5, ...)
                                    ──► GPU node B (phi4, llama3.2, ...)
                                    ──► GPU node C (rnj-1, deepseek-v2, ...)
```

Each `spl3 run` subprocess runs its workflow locally; only `GENERATE` nodes
(the LLM calls) are routed through the Hub to a worker that has the requested
model loaded.

### Model roster

`m001` (claude_cli / sonnet-4-6) is **excluded automatically** — momagrid
workers only serve Ollama inference. `m001` runs in `run_experiment.py`
(sequential) as the reference ceiling. The momagrid run covers the 9
open-source models (`m002`–`m010`), which is the actual subject of measurement.

| Run script | Models | Purpose |
|---|---|---|
| `run_experiment.py` | m001–m010 (10) | Sequential baseline; sonnet sets the reference ceiling |
| `run_experiment_momagrid.py` | m002–m010 (9) | Grid run; open-source models, parallelised across GPUs |

### Commands

```bash
conda activate spl123
export MOMAGRID_HUB_URL=http://192.168.0.170:9000/

# Smoke test — 1 model, 1 problem, dry run
python cookbook/77_neurosymbolic/run_experiment_momagrid.py \
    -m m002 -p p003 -s true -r 1 --workers 3 --dry-run

python cookbook/77_neurosymbolic/run_experiment_momagrid.py \
    -m m002 -s true -r 1 --workers 3 

# Verify 360-cell plan (9 models × 20 problems × 2 arms)
python cookbook/77_neurosymbolic/run_experiment_momagrid.py --dry-run

# Launch — 3 workers (one per GPU node)
python cookbook/77_neurosymbolic/run_experiment_momagrid.py --workers 3

# Override backend for the whole run (e.g. re-score on SymPy rung)
python cookbook/77_neurosymbolic/run_experiment_momagrid.py --workers 3 --backend sympy

# Disable momagrid — fall back to local Ollama (sequential)
python cookbook/77_neurosymbolic/run_experiment_momagrid.py --no-momagrid
```

Results are written to the same `experiment_results.db` as `run_experiment.py`,
so `app_experiment.py` shows both runs side-by-side for direct sonnet vs.
open-source comparison.

### Expected timing (3 GPU workers)

| Sequential (`run_experiment.py`) | Momagrid 3× (`run_experiment_momagrid.py`) |
|---|---|
| 400 cells, ~60 min | 360 cells, ~20 min (~3× speedup) |

## Streamlit Dashboard

After running experiments, visualize and explore results via the interactive dashboard:

```bash
conda activate spl123
streamlit run cookbook/77_neurosymbolic/app_experiment.py
```

Open your browser to `http://localhost:8501`. The dashboard provides:

- **Runs tab**: Overview of all experiment runs, pass rates, backend breakdown, duration
- **Results tab**: Filterable table of all results (model × problem × solver × run) with per-cell details (decomposition, output, notes)
- **Log Viewer tab**: Individual SPL run logs with quick filters (solver_error, plan_error, Sage failures)
- **Analysis tab**: Aggregated metrics by model/tier, heatmaps (model × tier pass rate), backend comparison, failure mode breakdown
- **Edit / Notes tab**: Manual notes and status correction per result row

Filters across all views: models, tiers, backends, solver on/off, status, pass/fail, free-text search.

## Analysis & Paper Tables

Generate paper-ready markdown tables and figures from experiment results:

```bash
# Print all tables for the latest run to stdout
python cookbook/77_neurosymbolic/analyze_experiment.py

# Specify a run by source ID
python cookbook/77_neurosymbolic/analyze_experiment.py --source exp-20260615-073849

# Generate figures (heatmap, bootstrap CI, pass comparison) as PDF/PNG
python cookbook/77_neurosymbolic/analyze_experiment.py --figures ./figs --source exp-20260615-073849

# List all available experiment runs in the database
python cookbook/77_neurosymbolic/analyze_experiment.py --list-sources

# Save markdown tables to a file
python cookbook/77_neurosymbolic/analyze_experiment.py --out results.md
```

The analyzer aggregates results across multiple runs per cell (e.g., `--backend sympy --backend sage` runs 3 times each), computes mean pass rates, and outputs:

- **Pass rates** by model and arm (solver vs. LLM-only)
- **Latency** comparison
- **Per-tier breakdown** for both arms
- **Failure mode counts** (solver_error, plan_error, silent_failure, etc.)
- **Backend comparison** (SymPy vs Sage vs Lean pass rates side-by-side)
- **Figures**: heatmaps, bootstrap CI bars, and solver vs. LLM-only pass-rate comparison

All tables are formatted for direct copy into the paper (markdown, LaTeX-compatible).

## Pass criteria

| Arm | Pass statuses |
|---|---|
| solver, backend sympy/sage | `complete` (the chain verified end-to-end) |
| solver, backend lean | `machine_proved` only — `statement_checked` means the formalization typechecks but the claim is unproven; `unfaithful` means the judge gated it (§B.4) |
| LLM-only baseline | `complete` / `unverified_success` — fluent output with *no* verification, by construction |

## Key learning points

1. **The backend is a parameter, not an architecture.** Swapping
   SymPy → Sage → Lean changes *what stands behind* `CALL`/the kernel —
   the workflow shape, the prompts, and the harness stay fixed. That is the
   "seamless dual-processing" claim made concrete.
2. **Sage is the umbrella, not a sidecar** (plan §A.1): the passagemath wheels
   run in the same interpreter, so `solve_step_with_sage` is a drop-in
   TOOL_API — and `galois` / `conic` / `rank` reach PARI with no new SPL
   constructs.
3. **Proof failure is data, not an error** (§B.2): the lean arm never blocks —
   it returns its badge as the status, and the harness counts
   `statement_checked` and `unfaithful` outcomes separately from
   `machine_proved`.
4. **The checked artifact never round-trips through the LLM** (recipe 67's
   lesson, at every rung): `PREV` resolution, `make_theorem` splicing, and
   kernel-checked citations are all deterministic.

## Related

- Recipe 67 (`67_symbolic_math/`) — the SymPy rung + the original A/B harness
- Recipe 75 (`75_sage_math/`) — the Sage rung under `--kernel-name sagemath`
  (the kernel-route alternative to this recipe's in-process TOOL_API route)
- Recipe 76 (`76_lean_proof/`) — the Lean rung, stdlib tier
- Recipe 71 `lean_payoffs.spl` — the same Lean spine promoting cached
  textbook sections to two-axis badge sets
- [`docs/DEV/spl3-lean.md`](../../docs/DEV/spl3-lean.md),
  [`docs/DEV/spl3-sagemath.md`](../../docs/DEV/spl3-sagemath.md) — what shipped
