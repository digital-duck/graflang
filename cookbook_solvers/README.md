# Solver recipes

SPL.py's `cookbook-solver` recipes lifted to GraphLang with `spl3 util spl2graph` (see each recipe's readme for what changed). Run one with `graf run cookbook_solvers/NAME/NAME.graph.yaml --param key=value`; the commands in each readme are already rewritten.

| Recipe | From | Graphs | Test run (claude_cli, claude-sonnet-5-5) |
|---|---|---|---|
| [`symbolic_math`](symbolic_math) | `067_symbolic_math` | `hello_symbolic_math`, `sympy_llm`, `sympy_llm_v2`, `sympy_math_multi_step` | completed |
| [`sage_math`](sage_math) | `075_sage_math` | `basic_sagemath` | completed (SageMath kernel) |
| [`lean_proof`](lean_proof) | `076_lean_proof` | `lean_proof` | completed, `machine_proved` |
| [`neurosymbolic`](neurosymbolic) | `077_neurosymbolic` | `symbolic_math` | completed (rungs sympy, sage and lean tried; lean has no Mathlib here) |
| [`constraint_opt`](constraint_opt) | `078_constraint_opt` | `constraint_opt`, `resource_allocation`, `staff_scheduling`, `supply_chain` | completed |
| [`code_pytest`](code_pytest) | `079_code_pytest` | `code_pytest` | completed |
| [`graph_reasoning`](graph_reasoning) | `081_graph_reasoning` | `graph_reasoning` | completed |
| [`logic_puzzle_solver`](logic_puzzle_solver) | `082_logic_puzzle_solver` | `logic_puzzle_solver` | completed |
| [`unit_dimensional_check`](unit_dimensional_check) | `083_unit_dimensional_check` | `unit_dimensional_check` | completed |
| [`sql_verifier`](sql_verifier) | `084_sql_verifier` | `sql_verifier` | completed |
| [`property_based_code_verify`](property_based_code_verify) | `085_property_based_code_verify` | `property_based_code_verify` | completed |
| [`financial_calc_verifier`](financial_calc_verifier) | `086_financial_calc_verifier` | `financial_calc_verifier` | completed |
| [`route_optimization`](route_optimization) | `087_route_optimization` | `route_optimization` | completed |
| [`compsci_physics`](compsci_physics) | `090_compsci_physics` | `physics_conservation` | completed |
| [`compsci_materials`](compsci_materials) | `092_compsci_materials` | `materials_crystal` | completed |
| [`auto_planning`](auto_planning) | `093_auto_planning` | `auto_planning` | completed |
| [`data_eng_text2spl`](data_eng_text2spl) | `094_data_eng_text2spl` | `text2sql_quality` | completed |
| [`job_shop`](job_shop) | `098_job_shop` | `job_shop` | completed |
| [`portfolio_opt`](portfolio_opt) | `099_portfolio_opt` | `portfolio_optimization`, `portfolio_comparison` (the SPL file has two workflows; each is its own graph) | completed (defaults changed to target 0.08, cap 0.25: SPL's 0.12 and 0.20 made Markowitz and CVaR infeasible) |
| [`supply_sourcing`](supply_sourcing) | `100_supply_sourcing` | `supply_sourcing` | completed |
| [`production_sustainability`](production_sustainability) | `101_production_sustainability` | `production_sustainability` | completed |
| [`z3_compliance`](z3_compliance) | `102_z3_compliance` | `z3_compliance` | completed |
| [`data_quality`](data_quality) | `103_data_quality` | `data_quality` | completed |
| [`pandera_schema`](pandera_schema) | `104_pandera_schema` | `pandera_schema` | completed |
| [`prolog_inference`](prolog_inference) | `105_prolog_inference` | `prolog_inference` | completed |
| [`shapely_geo`](shapely_geo) | `106_shapely_geo` | `shapely_geo` | completed |
| [`workforce_3obj`](workforce_3obj) | `107_workforce_3obj` | `workforce_3obj` | completed |
| [`robust_milp`](robust_milp) | `108_robust_milp` | `robust_milp` | completed |
| [`synthetic_problems`](synthetic_problems) | `109_synthetic_problems` | `synthetic_problem_gen` | completed |
| [`nash_game_theory`](nash_game_theory) | `110_nash_game_theory` | `nash_game_theory` | completed |
| [`stackelberg_game`](stackelberg_game) | `111_stackelberg_game` | `stackelberg_game` | completed |
| [`optuna_blackbox`](optuna_blackbox) | `112_optuna_blackbox` | `optuna_blackbox` | completed |
| [`bayesian_opt`](bayesian_opt) | `113_bayesian_opt` | `bayesian_opt` | completed |
| [`scipy_nonlinear`](scipy_nonlinear) | `114_scipy_nonlinear` | `scipy_nonlinear` | completed |
| [`gambit_3player`](gambit_3player) | `115_gambit_3player` | `gambit_3player` | completed |
| [`openspiel_cfr`](openspiel_cfr) | `116_openspiel_cfr` | `openspiel_cfr` | completed |
| [`pyomo_stochastic`](pyomo_stochastic) | `117_pyomo_stochastic` | `pyomo_stochastic` | completed |
| [`trading_rule_z3`](trading_rule_z3) | `118_trading_rule_z3` | `trading_rule_z3` | completed |
| [`demand_forecast`](demand_forecast) | `119_demand_forecast` | `demand_forecast` | completed |
| [`insurance_policy_z3`](insurance_policy_z3) | `120_insurance_policy_z3` | `insurance_policy_z3` | completed |
| [`platypus_moea`](platypus_moea) | `121_platypus_moea` | `platypus_moea` | completed |
| [`global_minlp`](global_minlp) | `122_global_minlp` | `global_minlp` | completed (grid-search fallback: no Couenne/Bonmin) |
| [`hard_milp_scip`](hard_milp_scip) | `123_hard_milp_scip` | `hard_milp_scip` | completed |
| [`simpy_des`](simpy_des) | `124_simpy_des` | `simpy_des` | completed |
| [`progressive_hedging`](progressive_hedging) | `125_progressive_hedging` | `progressive_hedging` | completed |
| [`minizinc_cp`](minizinc_cp) | `126_minizinc_cp` | `minizinc_cp` | completed (Python fallback: no MiniZinc binary) |
| [`pii_compliance`](pii_compliance) | `127_pii_compliance` | `compliance_check`, `pii_compliance` | completed |

## Test run, 2026-11-01

Every graph was run with `graf run ... --llm claude_cli:claude-sonnet-5-5`, the solver switch on (`use_solver`/`enable_solver` = true), under a `--bind` file capping a run at 20 model calls, 500 steps and 800 s. All 47 recipes complete. The graphs make 1 to 4 model calls each, about 1,000 to 3,000 tokens a run, and take 5 to 25 s. The latest run of each graph is in the recipe's `output/` folder (`result.json`, per-node files in `nodes/`, `run.txt`). A graph that completes does not show its answer is right: I read every output, and the notes below are what I found.

Libraries installed into the `graf` conda env for the run (none were present before): `mip`, `ortools`, `python-constraint`, `yfinance`, `cvxpy`, `pyomo`, `optuna`, `platypus-opt`, `shapely`, `simpy`, `pygambit`, `statsmodels`, `scikit-optimize`, `pyscipopt`, `pymoo`, `hypothesis`, `highspy`, `nashpy`, `open_spiel`, `minizinc`, `pandera`, and for Sage `pip install 'spl-llm[sage]'` plus `python -m sage.repl.ipython_kernel.install --user`.

| Needs outside pip | Recipes | State here |
|---|---|---|
| SageMath kernel (`graf run --kernel-name sagemath`, or `kernel_name: sagemath` on a node) | `sage_math`, `neurosymbolic` (default rung) | works |
| Lean 4 + the SPL REPL | `lean_proof`, `neurosymbolic` (lean rung) | works for claims over `Nat`; no Mathlib, so claims over `ℝ` come back `unverified` (see *Installing Mathlib*, below) |
| Couenne / Bonmin | `global_minlp` | not installed; the grid-search fallback answered (the report says so) |
| MiniZinc binary | `minizinc_cp` | not installed; the Python backtracking fallback answered |
| SPL.py importable (`procedure_ref`) | `symbolic_math`, `neurosymbolic`, `code_pytest` | works |

Things to know about the results: `portfolio_comparison` defaults differ from SPL (see its readme); `z3_compliance`'s explanation prompt gets the policy Z3 checked, where the SPL original passed the empty `policy_text` of the default demo.

### What had to be fixed

Fixes in GraphLang itself:

- **f-strings** in expressions (`f'{@a}: {@b}'`). The lift of SPL's string building produced them everywhere.
- **`procedure_ref` into an `.spl` file with several workflows** ran the last workflow of the file, so a step summary came back blank. It now runs `config.workflow`, else the workflow named like the ref.
- **A kernel can be chosen**: `kernel_name` on a `SOLVE` node, or `graf run --kernel-name` (SPL's `--kernel-name`). One kernel per name is kept for the run.
- **A `solvers` root** in the app, next to `apps` and `cookbook`.

Fixes in the lifted graphs:

| Recipe | Problem | Fix |
|---|---|---|
| `constraint_opt` (4 graphs) | the SPL builtins `_total_input_tokens` / `_total_output_tokens` are not variables here | `globals().get('_total_input_tokens', 0)` |
| `symbolic_math`, `neurosymbolic` | a loop bound `< @in_n_steps` compared a number with text | `< int(@in_n_steps)` |
| `symbolic_math`, `neurosymbolic` | the SPL workflows `IMPORT` library `.spl` files that were not copied | copied `sympy_tools.spl`, `sympolic_tools.spl` next to the graphs |
| `neurosymbolic` | the tool imports a helper module of the SPL original | copied `roundtrip_checks.py`, added its folder to the tool's search path |
| `auto_planning`, `lean_proof`, `neurosymbolic`, `sql_verifier` | a model step's input port was named after the SPL function's parameter, but the variable feeding it had another name, so `{{in_problem}}` went to the model unfilled | renamed the port after the variable |
| `lean_proof`, `neurosymbolic` | SPL's `run_python` runs in the persistent kernel, so a Lean REPL started by one step is there for the next; the lift made it a subprocess, and every later step saw no REPL | `run_python` now executes in the shared kernel session (23 nodes) |
| `sage_math` | the Sage steps were bare expressions (`version()`, `factor(...)`), so the graph did not validate | rewritten as `backend: kernel` nodes with `kernel_name: sagemath`; the last `ASSERT` checks the result of the operation that ran |
| `demand_forecast` | the model that makes the JSON got "use the default dataset" and no data | it is given the default dataset to return |
| `pii_compliance` | the rules file path was relative to the SPL recipe folder | `Path('cookbook_solvers')/'pii_compliance'/'rules.json'` |

### Lessons for `spl3 util spl2graph`

The lift (`SPL.py/spl3/spl2graph.py`) got the structure right in every recipe: nodes, edges, prompts and the Python tools all came across. What it could not carry is what the SPL runtime does implicitly. Each lesson below is now fixed in `spl2graph` (SPL.py, with tests in `tests/test_spl2graph.py`) or checked by `graf validate`; the recipes in this folder were lifted before the fixes and patched by hand, as the table above says. Lifting all 54 workflows again with the fixed tool gives graphs that pass `graf validate` with no errors, and the re-lifted `sage_math` runs unedited.

1. **A prompt placeholder no port fills.** `GENERATE f(@x)` where `f` declares `(problem TEXT)` made a port `in_problem` fed by `@x`. Inside a `LOOP` body an outer variable reaches a node by its own name, so the port was never fed, the prompt kept `{{in_problem}}` and the model answered without its input (four recipes, no error). *Fixed:* the port and the placeholder are named after the variable passed in (`{{in_x}}`), in one pass so swapped names (`f(@b, @a)`) cannot mix. *Checked:* `graf validate` now reports a prompt that uses `{{in_x}}` when the node has no `in_x` or nothing feeds it.
2. **Tool return types.** Every lifted tool was `out_type: TEXT`, so a number or list reached the next node as text. *Fixed:* the type comes from the Python return annotation (`bool`, `int`, `float` to `BOOL`, `INTEGER`, `REAL`; `dict`, `list` to `JSON`).
3. **Files the graph needs.** A library `.spl` that a procedure `IMPORT`s, the procedure files themselves, and a helper module a tool imports (`roundtrip_checks.py`) are not copied. *Fixed:* the lift names each of them in a warning ("copy it next to the graph").
4. **Persistent kernel state and `SOLVE` statements.** SPL runs `SOLVE`, `run_python` and `ASSERT` in one kernel session whose variables survive; a bare `SOLVE` expression such as Sage's `factor(...)` made a graph that did not validate. *Fixed:* a `SOLVE` statement is a `backend: kernel` node (`result` is the expression, quoted markers become `str(x)`), `spl3 util spl2graph --kernel-name sagemath` writes `kernel_name` on it, a call to a Python builtin or to a name only the kernel knows (`isinstance(1, Integer)`) becomes a kernel node too, and `_spl_solve_result` is bound to the latest `SOLVE` result. For tools that keep an object across steps (a Lean REPL), GraphLang's shared kernel session does the rest.
5. **f-strings.** `f'{@x}'` in an assignment read `@x`, not the node's port `@in_x`. *Fixed.*
6. **Several workflows in one `.spl`.** With `--workflow NAME` the file is now `NAME.graph.yaml`, so lifting two workflows of one file no longer overwrites the first.
7. **Not fixed, by design.** SPL builtins such as `_total_input_tokens` and `_total_output_tokens` are not variables in a graph (`constraint_opt` was patched by hand to `globals().get(...)`); a number read back from a tool as text still needs `int(...)` in a condition unless the tool is annotated (point 2); a path a recipe reads (`rules.json`) stays relative to the SPL folder. A prompt that uses `{x}` for a workflow variable that is not a parameter is left as text and the lift warns.
8. **A smoke test with a placeholder model proves little.** Recipes that "ran end to end" with the mock still had empty prompts (point 1) or a dead step (point 4). Run a lifted recipe with a real model, as above, and run `graf validate` first.

### Regenerating the recipes with the fixed `spl2graph`

All 55 graphs were lifted again from `SPL.py/cookbook-solver` with the fixed tool (`--kernel-name sagemath` for `sage_math`, `--workflow` for the two `portfolio_opt` workflows) and compared with the hand-patched graphs in this folder, node by node (ids, types, ports, config, edges, loops included). The comparison script and the full report are in the session scratch folder (`compare.py`, `compare.txt`).

- **3 graphs are identical** (`data_quality`, `pandera_schema`, `hello_symbolic_math`); the other 52 differ only as listed here.
- **Port and placeholder names (about 35 prompts).** The lift names them after the variable passed in (`{{in_solution}}`); the hand patches kept the SPL parameter name where the port happened to be fed (`{{in_solution_json}}`). Same wiring, same prompt text.
- **Fixed by the lift now, as by hand before:** `_total_input_tokens` / `_total_output_tokens` (`globals().get(...)`), `run_python` in the shared kernel (a docstring differs, the code is the same), tool `out_type` from the annotation (`BOOL` for `tool_10` and the like), `float(@in_n_steps)` in the four loops (the hand patch said `int(...)`), the unfed GENERATE ports, and `sage_math` as kernel nodes (cosmetics: the lift writes no `type: TEXT` key on them, `out_type: JSON` for the preflight `isinstance` check).
- **Still by hand, not in the lift:** `pii_compliance` (the rules file path), `neurosymbolic` (the `roundtrip_checks.py` search path in the tool code), `demand_forecast` (the default dataset given to the prompt).
- **Run test.** The regenerated versions of the recipes that needed hand fixes (`auto_planning`, `constraint_opt` x4, `lean_proof`, `sql_verifier`, `symbolic_math` x4, `code_pytest`) were run as before (`claude_cli` `claude-sonnet-5-5`, solver on, capped at 20 calls each): all 12 complete and give the same results as the hand-patched graphs (plan valid and round trip matching, `machine_proved`, `VERIFIED` with 27 tests, x = ±1/3, `Optimal`). The folder keeps the hand-patched graphs, since they hold the three fixes above.

## Installing Mathlib for the Lean rung (not done here)

`lean_proof` proves claims over `Nat` with the Lean 4 standard library alone. The Lean rung of `neurosymbolic` starts the REPL with Mathlib (`LeanREPL.mathlib()`), so a claim over `ℝ` comes back `unverified` until Mathlib is installed. Nobody has installed it on the test machine; to do so, from the SPL.py checkout:

```bash
bash cookbook/tools/lean/setup_lean.sh --with-mathlib    # ~5 GB of prebuilt oleans (about 7 GB with the project); 10 to 20 minutes
```

It enables Mathlib in the `spl_lean` lake project, runs `lake update mathlib` and `lake exe cache get` (it retries the download up to three times). To keep the Lean stack on another disk, set `ELAN_HOME`, `SPL_LEAN_REPL_DIR` and `SPL_LEAN_PROJECT_DIR` before running it and keep them set in your shell profile, because the REPL reads the same variables at run time. Check it with `graf run cookbook_solvers/neurosymbolic/symbolic_math.graph.yaml --param backend=lean --param problem="the square of any real number is nonnegative"`; the first start is slow because the REPL imports Mathlib once. The details are in SPL.py's `docs/GUIDE/SETUP.md`, section 6.
