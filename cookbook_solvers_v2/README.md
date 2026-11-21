# cookbook_solvers_v2: the solver recipes in the layered form

Recipes of `cookbook_solvers/` (SPL.py's `cookbook-solver`, lifted with `spl2graph`) rewritten as a short top graph plus composites. The originals stay as they are. A solver recipe
has one shape: set up (the default data, the solver switch), then **either** the solver arm (the tools compute, an `ASSERT` checks, the model explains) **or** the LLM-only arm
(the model reasons alone). The layered form makes those three stages composites, and every step is named after the tool or prompt it runs (`validate_schema`, not `tool_3`):

```
<recipe>     prepare -> solver on? -> solver_arm | solver off? -> llm_only -> exit
```

Each recipe's `readme.md` is the original's (what it shows, the results of the 2026-11-01 test run) with a layered-port note on top; its commands use `cookbook_solvers_v2/`.

| Recipe | Original | Composites |
|---|---|---|
| [`bayesian_opt`](bayesian_opt) | `cookbook_solvers/bayesian_opt` | `llm_only`, `prepare`, `solver_arm` |
| [`data_quality`](data_quality) | `cookbook_solvers/data_quality` | `llm_only`, `prepare`, `solver_arm` |
| [`gambit_3player`](gambit_3player) | `cookbook_solvers/gambit_3player` | `llm_only`, `prepare`, `solver_arm` |
| [`global_minlp`](global_minlp) | `cookbook_solvers/global_minlp` | `llm_only`, `prepare`, `solver_arm` |
| [`insurance_policy_z3`](insurance_policy_z3) | `cookbook_solvers/insurance_policy_z3` | `llm_only`, `prepare`, `solver_arm` |
| [`nash_game_theory`](nash_game_theory) | `cookbook_solvers/nash_game_theory` | `llm_only`, `prepare`, `solver_arm` |
| [`openspiel_cfr`](openspiel_cfr) | `cookbook_solvers/openspiel_cfr` | `llm_only`, `prepare`, `solver_arm` |
| [`optuna_blackbox`](optuna_blackbox) | `cookbook_solvers/optuna_blackbox` | `llm_only`, `prepare`, `solver_arm` |
| [`pandera_schema`](pandera_schema) | `cookbook_solvers/pandera_schema` | `llm_only`, `prepare`, `solver_arm` |
| [`prolog_inference`](prolog_inference) | `cookbook_solvers/prolog_inference` | `llm_only`, `prepare`, `solver_arm` |
| [`shapely_geo`](shapely_geo) | `cookbook_solvers/shapely_geo` | `llm_only`, `prepare`, `solver_arm` |
| [`stackelberg_game`](stackelberg_game) | `cookbook_solvers/stackelberg_game` | `llm_only`, `prepare`, `solver_arm` |

Not yet ported (35): the other recipes of `cookbook_solvers/`. The ones with more than one graph or a different shape (`constraint_opt`, `portfolio_opt`, `symbolic_math`, `neurosymbolic`, `lean_proof`,
`z3_compliance`, `pii_compliance`) need their groups chosen by hand; the rest have the two-arm shape and are one command each.

## Port one

```bash
python scripts/port_recipe.py solvers NAME [NAME ...]      # copy, compact, name the steps, group into prepare / solver_arm / llm_only, prettify, validate
pytest tests/test_cookbook_solvers_v2.py -q                 # every recipe in this folder is checked
```

## Checked

`tests/test_cookbook_solvers_v2.py`: every graph validates with no errors or warnings; the top level has at most 10 boxes; and each recipe, run beside its original on the **mock**
adapter (the tools really run in a Jupyter kernel; the mock model answers with text that names its prompt), gives the same outputs with the solver switch on and off. About 4 s a recipe.
Not checked: a real model's answers (the structure and the prompts are equal, not the text a model gives).

Needs the libraries each recipe names (see its readme) in the `graf` conda env, and the `kernel` extra.
