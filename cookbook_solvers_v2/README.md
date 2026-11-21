# cookbook_solvers_v2: the solver recipes in the layered form

43 of the 47 recipes of `cookbook_solvers/` (SPL.py's `cookbook-solver`, lifted with `spl2graph`) rewritten as a short top graph plus composites. The originals stay as they are. A solver recipe
has one shape: set up (the default data, the solver switch), then **either** the solver arm (the tools compute, an `ASSERT` checks, the model explains) **or** the LLM-only arm
(the model reasons alone). The layered form makes those stages composites, and every step is named after the tool or prompt it runs (`validate_schema`, not `tool_3`):

```
<recipe>     prepare -> solver on? -> solver_arm | solver off? -> llm_only -> exit
```

Three variants of that shape occur and are handled by `scripts/port_recipe.py`: the plain one above (the switch is normalised in `prepare`); the **timed** one (`mode`, `llm_only`, `solver_arm`: the
switch is normalised and the solver arm is a retry loop, with the timing steps left at the top level); and recipes built from stages with the choice in the middle, where the groups were chosen by hand
(`z3_compliance`, `trading_rule_z3`, `scipy_nonlinear`, `portfolio_opt`, `pii_compliance`, `sage_math`, `code_pytest`, `synthetic_problems`). A recipe with several graphs has each graph's parts
prefixed with its name (`portfolio_optimization_solver_arm`).

Each recipe's `readme.md` is the original's (what it shows, the results of the 2026-11-01 test run) with a layered-port note on top; its commands use `cookbook_solvers_v2/`.

| Recipe | Original | Composites |
|---|---|---|
| [`auto_planning`](auto_planning) | `cookbook_solvers/auto_planning` | `llm_only`, `mode`, `solver_arm` |
| [`bayesian_opt`](bayesian_opt) | `cookbook_solvers/bayesian_opt` | `llm_only`, `prepare`, `solver_arm` |
| [`code_pytest`](code_pytest) | `cookbook_solvers/code_pytest` | `drafts`, `repair` |
| [`compsci_materials`](compsci_materials) | `cookbook_solvers/compsci_materials` | `llm_only`, `mode`, `solver_arm` |
| [`compsci_physics`](compsci_physics) | `cookbook_solvers/compsci_physics` | `llm_only`, `mode`, `solver_arm` |
| [`data_eng_text2spl`](data_eng_text2spl) | `cookbook_solvers/data_eng_text2spl` | `llm_only`, `mode`, `solver_arm` |
| [`data_quality`](data_quality) | `cookbook_solvers/data_quality` | `llm_only`, `prepare`, `solver_arm` |
| [`demand_forecast`](demand_forecast) | `cookbook_solvers/demand_forecast` | `llm_only`, `prepare`, `solver_arm` |
| [`financial_calc_verifier`](financial_calc_verifier) | `cookbook_solvers/financial_calc_verifier` | `llm_only`, `mode`, `solver_arm` |
| [`gambit_3player`](gambit_3player) | `cookbook_solvers/gambit_3player` | `llm_only`, `prepare`, `solver_arm` |
| [`global_minlp`](global_minlp) | `cookbook_solvers/global_minlp` | `llm_only`, `prepare`, `solver_arm` |
| [`graph_reasoning`](graph_reasoning) | `cookbook_solvers/graph_reasoning` | `llm_only`, `mode`, `solver_arm` |
| [`hard_milp_scip`](hard_milp_scip) | `cookbook_solvers/hard_milp_scip` | `llm_only`, `prepare`, `solver_arm` |
| [`insurance_policy_z3`](insurance_policy_z3) | `cookbook_solvers/insurance_policy_z3` | `llm_only`, `prepare`, `solver_arm` |
| [`job_shop`](job_shop) | `cookbook_solvers/job_shop` | `llm_only`, `prepare`, `solver_arm` |
| [`logic_puzzle_solver`](logic_puzzle_solver) | `cookbook_solvers/logic_puzzle_solver` | `llm_only`, `mode`, `solver_arm` |
| [`minizinc_cp`](minizinc_cp) | `cookbook_solvers/minizinc_cp` | `llm_only`, `prepare`, `solver_arm` |
| [`nash_game_theory`](nash_game_theory) | `cookbook_solvers/nash_game_theory` | `llm_only`, `prepare`, `solver_arm` |
| [`openspiel_cfr`](openspiel_cfr) | `cookbook_solvers/openspiel_cfr` | `llm_only`, `prepare`, `solver_arm` |
| [`optuna_blackbox`](optuna_blackbox) | `cookbook_solvers/optuna_blackbox` | `llm_only`, `prepare`, `solver_arm` |
| [`pandera_schema`](pandera_schema) | `cookbook_solvers/pandera_schema` | `llm_only`, `prepare`, `solver_arm` |
| [`pii_compliance`](pii_compliance) | `cookbook_solvers/pii_compliance` | `pii_compliance_extract`, `pii_compliance_llm_only`, `pii_compliance_solver_arm` |
| [`platypus_moea`](platypus_moea) | `cookbook_solvers/platypus_moea` | `llm_only`, `prepare`, `solver_arm` |
| [`portfolio_opt`](portfolio_opt) | `cookbook_solvers/portfolio_opt` | `portfolio_comparison_optimizers`, `portfolio_comparison_report`, `portfolio_comparison_tables`, `portfolio_optimization_llm_only`, `portfolio_optimization_prepare`, `portfolio_optimization_solver_arm` |
| [`production_sustainability`](production_sustainability) | `cookbook_solvers/production_sustainability` | `llm_only`, `prepare`, `solver_arm` |
| [`progressive_hedging`](progressive_hedging) | `cookbook_solvers/progressive_hedging` | `llm_only`, `prepare`, `solver_arm` |
| [`prolog_inference`](prolog_inference) | `cookbook_solvers/prolog_inference` | `llm_only`, `prepare`, `solver_arm` |
| [`property_based_code_verify`](property_based_code_verify) | `cookbook_solvers/property_based_code_verify` | `llm_only`, `mode`, `solver_arm` |
| [`pyomo_stochastic`](pyomo_stochastic) | `cookbook_solvers/pyomo_stochastic` | `llm_only`, `prepare`, `solver_arm` |
| [`robust_milp`](robust_milp) | `cookbook_solvers/robust_milp` | `llm_only`, `prepare`, `solver_arm` |
| [`route_optimization`](route_optimization) | `cookbook_solvers/route_optimization` | `llm_only`, `mode`, `solver_arm` |
| [`sage_math`](sage_math) | `cookbook_solvers/sage_math` | `dispatch`, `explain`, `parse`, `setup` |
| [`scipy_nonlinear`](scipy_nonlinear) | `cookbook_solvers/scipy_nonlinear` | `formulate`, `llm_only`, `solver_arm` |
| [`shapely_geo`](shapely_geo) | `cookbook_solvers/shapely_geo` | `llm_only`, `prepare`, `solver_arm` |
| [`simpy_des`](simpy_des) | `cookbook_solvers/simpy_des` | `llm_only`, `prepare`, `solver_arm` |
| [`sql_verifier`](sql_verifier) | `cookbook_solvers/sql_verifier` | `llm_only`, `mode`, `solver_arm` |
| [`stackelberg_game`](stackelberg_game) | `cookbook_solvers/stackelberg_game` | `llm_only`, `prepare`, `solver_arm` |
| [`supply_sourcing`](supply_sourcing) | `cookbook_solvers/supply_sourcing` | `llm_only`, `prepare`, `solver_arm` |
| [`synthetic_problems`](synthetic_problems) | `cookbook_solvers/synthetic_problems` | `init`, `suite`, `variants` |
| [`trading_rule_z3`](trading_rule_z3) | `cookbook_solvers/trading_rule_z3` | `audit`, `policy`, `snapshot` |
| [`unit_dimensional_check`](unit_dimensional_check) | `cookbook_solvers/unit_dimensional_check` | `llm_only`, `mode`, `solver_arm` |
| [`workforce_3obj`](workforce_3obj) | `cookbook_solvers/workforce_3obj` | `llm_only`, `prepare`, `solver_arm` |
| [`z3_compliance`](z3_compliance) | `cookbook_solvers/z3_compliance` | `llm_only`, `policy`, `solver_arm` |

**Not ported (4 of 47):** `constraint_opt` (4 graphs), `symbolic_math` (4), `lean_proof` and `neurosymbolic`. Their solver arm is a retry loop kept in long form whose nodes are interleaved with timing and
bookkeeping steps, so no group has a single entry and one way out (`graf group` refuses it, correctly); grouping them needs the loops opened and rewired by hand, not just a choice of nodes.
`hello_symbolic_math`-style graphs with no switch are left flat inside a recipe that is otherwise ported.

## Port one

```bash
python scripts/port_recipe.py solvers NAME [NAME ...]                       # infer the groups (plain and timed shapes), name the steps, prettify, validate
python scripts/port_recipe.py solvers NAME --list                           # the steps, named, to choose groups from
python scripts/port_recipe.py solvers NAME part=step,step part2=step,...    # explicit groups (several graphs: graph:part=step,step)
pytest tests/test_cookbook_solvers_v2.py -q                                  # every graph in this folder is checked (about 3 minutes)
```

## Checked

`tests/test_cookbook_solvers_v2.py`, for **every graph** of every recipe here: it validates with no errors or warnings; the top level has at most 10 boxes; and, run in the recipe's folder beside
its original on the **mock** adapter (the tools really run in a Jupyter kernel; the mock model answers with text that names its prompt), it gives the same outputs with the solver switch on and off.
What the comparison ignores because it differs from run to run: a solver's solve time, a temporary file name, a timestamp, the digits of a number past the third decimal (a live market feed, a numerical
solver), and node and procedure names inside messages. A run that cannot finish on the mock must fail the same way in both. Not checked: a real model's answers.

Needs the libraries each recipe names (see its readme) in the `graf` conda env, and the `kernel` extra.
