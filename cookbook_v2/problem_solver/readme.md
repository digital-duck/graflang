# problem_solver

A problem in words goes in; a report comes out that says **which exact solver answered, or that a model answered alone**. It mixes both kinds of compute: the model reads, chooses and writes (probabilistic), and a catalogue solver computes and checks (deterministic: SymPy, Z3, OR-Tools, cvxpy, SQLite).

```
problem -> understand -> choose -> bind -> fields -> pick (MUTATE) -> [solver] -> report
              (model)    (model)  (model + program check, one repair)   (policy)   (exact)
                           |          |                       |
                       no_solver   unbound                 refused    -> fallback (a model answers alone) -> report: UNVERIFIED
```

| | |
|---|---|
| Input | `problem` (TEXT) |
| Output | `report` (TEXT): starts with `SOLVED BY THE CATALOGUE SOLVER <name>` or `UNVERIFIED`, then the answer |
| Model calls | 4 on a path with a solver (understand, choose, bind, and what the solver makes) plus its own; 3 to 5 when a model answers alone |
| Catalogue | `symbolic_math` (SymPy), `z3_compliance` (Z3), `route_optimization` (OR-Tools), `portfolio_opt` (cvxpy, live prices), `sql_verifier` (SQLite): the recipes of `cookbook_solvers_v2/`, listed in `tools/solvers.json` |

## How it works

1. **understand**: the model restates the problem and its kind. It does not solve it.
2. **choose**: the model sees the catalogue (made from `tools/solvers.json`) and names ONE solver, or `none`. An unknown name counts as `none`. Error exit `no_solver` (`E_NO_SOLVER`).
3. **bind**: the model proposes the solver's inputs as JSON; a program (`tools/solver_tool.py`) checks them against the solver's declared inputs (unknown names, a missing required one, a value that is not plain text). A refusal goes back to the model with the reason, **once**. Error exit `unbound` (`E_UNBOUND`).
4. **pick**: the program, not the model, writes the `add_part` delta (the model never writes wiring); `MUTATE` checks it (policy `policies/solve.cedar`, the catalogue in the graph file, `parts_policy`: no e-mail, webhook or file writes, at most 8 model calls in the added solver) and adds the solver. `fields` holds one node per input name; the delta wires the solver's inputs from them and its output to `report`.
5. **fallback**: when there is no solver, the inputs cannot be bound, or the graph refuses the delta, a model answers alone. The report says **UNVERIFIED** and why. Nothing is hidden: a model's answer is never presented as a checked one.

## Run

```bash
graf run cookbook_v2/problem_solver/problem_solver.graph.yaml --bind cookbook_v2/problem_solver/problem_solver.bind.yaml \
    --llm claude_cli:claude-haiku-5-5 --param problem="Which employees in the Engineering department earn more than 100000? List their names and salaries."
graf run cookbook_v2/problem_solver/problem_solver.graph.yaml --bind cookbook_v2/problem_solver/problem_solver.bind.yaml --param problem="Write a two-line poem about autumn rain."
```

The bind file caps the run at 16 model calls. Always cap a real run.

Tried with `claude_cli:claude-haiku-5-5` (2026-11-22): the employees question chose `sql_verifier`, bound the question and an independently written reference query, and the solver's SQL result matched the reference (6 calls). The poem chose `none` and a model answered alone, marked UNVERIFIED (3 calls). Other solvers (`symbolic_math` needs SPL.py; `portfolio_opt` needs the network; `z3_compliance` and `route_optimization` run fixed demo models) were not run from this recipe.

## What to know

- **The solvers are demos, not general tools.** `sql_verifier` knows one sample `employees` table. `z3_compliance` checks one loan-rules model whatever `policy_text` says. `route_optimization` and `symbolic_math` are general for their kind. The catalogue text says what each is for, but the model can still pick wrongly: read the "Why" line in the report.
- **Required input means the problem must supply it.** The recipes carry demo defaults; `sql_verifier`'s fixed reference query gave a false `mismatch` on any other question, so the reference query is now an input the `bind` step writes independently.
- Adding a solver: put its recipe's inputs and output in `tools/solvers.json`, its path in `pick`'s `catalogue` (`problem_solver.graph.yaml`), and one node per new input name in `fields/fields.graph.yaml`. `tests/test_problem_solver.py` fails when these disagree.
- Not tried: a real run through the Cedar-refused path (the delta is built by a program from a validated manifest, so refusal is a safety net), or a problem that fits two solvers.

Offline checks: `pytest tests/test_problem_solver.py` (a scripted model; `sql_verifier` really runs on SQLite).
