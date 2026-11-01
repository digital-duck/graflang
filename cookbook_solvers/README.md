# Solver recipes

SPL.py's `cookbook-solver` recipes lifted to GraphLang with `spl3 util spl2graph` (see each recipe's readme for what changed). Run one with `graf run ~/.graflang/solvers/NAME/NAME.graph.yaml --param key=value`; the commands in each readme are already rewritten.

| Recipe | From | Graphs | Status (placeholder-model smoke test) |
|---|---|---|---|
| [`symbolic_math`](symbolic_math) | `067_symbolic_math` | `hello_symbolic_math`, `sympy_llm`, `sympy_llm_v2`, `sympy_math_multi_step` | runs end to end with the placeholder model (needs SPL.py (procedure_ref); lift skipped statements) |
| [`sage_math`](sage_math) | `075_sage_math` | `basic_sagemath` | not runnable yet (SageMath kernel; the lift is incomplete) (not runnable yet (SageMath kernel); lift skipped statements) |
| [`lean_proof`](lean_proof) | `076_lean_proof` | `lean_proof` | runs end to end with the placeholder model (the Lean steps need a Lean installation to mean anything) |
| [`neurosymbolic`](neurosymbolic) | `077_neurosymbolic` | `symbolic_math` | validates; stops at a tool that imports `roundtrip_checks`, a helper module of the SPL original that was not ported (copy `roundtrip_checks.py` from SPL.py's `cookbook-solver/077_neurosymbolic` and make it importable to run it) (needs SPL.py (procedure_ref); lift skipped statements) |
| [`constraint_opt`](constraint_opt) | `078_constraint_opt` | `constraint_opt`, `resource_allocation`, `staff_scheduling`, `supply_chain` | runs once `pulp` is installed |
| [`code_pytest`](code_pytest) | `079_code_pytest` | `code_pytest` | runs end to end with the placeholder model (needs SPL.py (procedure_ref)) |
| [`graph_reasoning`](graph_reasoning) | `081_graph_reasoning` | `graph_reasoning` | runs end to end with the placeholder model |
| [`logic_puzzle_solver`](logic_puzzle_solver) | `082_logic_puzzle_solver` | `logic_puzzle_solver` | runs once `python-constraint` is installed |
| [`unit_dimensional_check`](unit_dimensional_check) | `083_unit_dimensional_check` | `unit_dimensional_check` | runs once `pint` is installed |
| [`sql_verifier`](sql_verifier) | `084_sql_verifier` | `sql_verifier` | runs end to end with the placeholder model |
| [`property_based_code_verify`](property_based_code_verify) | `085_property_based_code_verify` | `property_based_code_verify` | runs end to end with the placeholder model |
| [`financial_calc_verifier`](financial_calc_verifier) | `086_financial_calc_verifier` | `financial_calc_verifier` | runs end to end with the placeholder model |
| [`route_optimization`](route_optimization) | `087_route_optimization` | `route_optimization` | runs once `ortools` is installed |
| [`compsci_physics`](compsci_physics) | `090_compsci_physics` | `physics_conservation` | runs end to end with the placeholder model |
| [`compsci_materials`](compsci_materials) | `092_compsci_materials` | `materials_crystal` | runs end to end with the placeholder model |
| [`auto_planning`](auto_planning) | `093_auto_planning` | `auto_planning` | runs end to end with the placeholder model |
| [`data_eng_text2spl`](data_eng_text2spl) | `094_data_eng_text2spl` | `text2sql_quality` | runs end to end with the placeholder model |
| [`job_shop`](job_shop) | `098_job_shop` | `job_shop` | runs once `ortools` is installed |
| [`portfolio_opt`](portfolio_opt) | `099_portfolio_opt` | `portfolio_optimization`, `portfolio_comparison` (the SPL file has two workflows; each is its own graph) | `portfolio_comparison` runs; `portfolio_optimization` needs live prices (yfinance) |
| [`supply_sourcing`](supply_sourcing) | `100_supply_sourcing` | `supply_sourcing` | runs once `pulp` is installed |
| [`production_sustainability`](production_sustainability) | `101_production_sustainability` | `production_sustainability` | runs once `pulp` is installed |
| [`z3_compliance`](z3_compliance) | `102_z3_compliance` | `z3_compliance` | runs end to end with the placeholder model |
| [`data_quality`](data_quality) | `103_data_quality` | `data_quality` | runs end to end with the placeholder model |
| [`pandera_schema`](pandera_schema) | `104_pandera_schema` | `pandera_schema` | runs end to end with the placeholder model |
| [`prolog_inference`](prolog_inference) | `105_prolog_inference` | `prolog_inference` | runs end to end with the placeholder model |
| [`shapely_geo`](shapely_geo) | `106_shapely_geo` | `shapely_geo` | runs end to end with the placeholder model |
| [`workforce_3obj`](workforce_3obj) | `107_workforce_3obj` | `workforce_3obj` | runs once `pulp` is installed |
| [`robust_milp`](robust_milp) | `108_robust_milp` | `robust_milp` | runs once `mip` is installed |
| [`synthetic_problems`](synthetic_problems) | `109_synthetic_problems` | `synthetic_problem_gen` | runs end to end with the placeholder model |
| [`nash_game_theory`](nash_game_theory) | `110_nash_game_theory` | `nash_game_theory` | runs end to end with the placeholder model |
| [`stackelberg_game`](stackelberg_game) | `111_stackelberg_game` | `stackelberg_game` | runs end to end with the placeholder model |
| [`optuna_blackbox`](optuna_blackbox) | `112_optuna_blackbox` | `optuna_blackbox` | runs end to end with the placeholder model |
| [`bayesian_opt`](bayesian_opt) | `113_bayesian_opt` | `bayesian_opt` | runs end to end with the placeholder model |
| [`scipy_nonlinear`](scipy_nonlinear) | `114_scipy_nonlinear` | `scipy_nonlinear` | runs end to end with the placeholder model |
| [`gambit_3player`](gambit_3player) | `115_gambit_3player` | `gambit_3player` | runs end to end with the placeholder model |
| [`openspiel_cfr`](openspiel_cfr) | `116_openspiel_cfr` | `openspiel_cfr` | runs end to end with the placeholder model |
| [`pyomo_stochastic`](pyomo_stochastic) | `117_pyomo_stochastic` | `pyomo_stochastic` | runs end to end with the placeholder model |
| [`trading_rule_z3`](trading_rule_z3) | `118_trading_rule_z3` | `trading_rule_z3` | runs end to end with the placeholder model |
| [`demand_forecast`](demand_forecast) | `119_demand_forecast` | `demand_forecast` | runs end to end with the placeholder model |
| [`insurance_policy_z3`](insurance_policy_z3) | `120_insurance_policy_z3` | `insurance_policy_z3` | runs end to end with the placeholder model |
| [`platypus_moea`](platypus_moea) | `121_platypus_moea` | `platypus_moea` | runs once `pulp` is installed |
| [`global_minlp`](global_minlp) | `122_global_minlp` | `global_minlp` | runs end to end with the placeholder model |
| [`hard_milp_scip`](hard_milp_scip) | `123_hard_milp_scip` | `hard_milp_scip` | runs end to end with the placeholder model |
| [`simpy_des`](simpy_des) | `124_simpy_des` | `simpy_des` | runs end to end with the placeholder model |
| [`progressive_hedging`](progressive_hedging) | `125_progressive_hedging` | `progressive_hedging` | runs end to end with the placeholder model |
| [`minizinc_cp`](minizinc_cp) | `126_minizinc_cp` | `minizinc_cp` | runs end to end with the placeholder model |
| [`pii_compliance`](pii_compliance) | `127_pii_compliance` | `compliance_check`, `pii_compliance` | runs end to end with the placeholder model |
