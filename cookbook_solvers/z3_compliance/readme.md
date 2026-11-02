# Recipe 102 — Z3 SMT Compliance Checker

> **GraphLang port.** Lifted from SPL.py's `cookbook-solver/102_z3_compliance` with `spl3 util spl2graph` (no model was involved). The Python tools travel inside the graph as `SOLVE` nodes (`backend: kernel`), so `graf run` needs the `kernel` extra (`pip install 'graflang[kernel]'`) and the libraries named below, not SPL.py. Commands use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`.
> Not ported: `tools.py` (the SPL original's tool registration, experiment and app scripts).
> Test run (2026-11-01, `claude_cli` `claude-sonnet-5-5`, solver on): the graph completed (1 model calls, 205 tokens in / 264 out in total); the explanation prompt shows an empty policy text, as in the SPL original. A run that completes does not show the answer is right: read the output before you rely on a recipe.

**The key story:** Five loan eligibility rules interact in a way that traps a specific applicant profile: a self-employed applicant with income $40K–$49K is ineligible even with a 700 credit score — UNLESS they also have collateral. Z3 surfaces this hidden constraint in milliseconds. LLM traces rules linearly and misses the interaction.

## What it demonstrates

| Axis | solver=ON | solver=OFF |
|---|---|---|
| Engine | Z3 SMT theorem prover | LLM sequential rule tracing |
| Output | SAT → qualifying profile; UNSAT → contradiction proof | "A customer who earns X and has Y would qualify" |
| Guarantee | Formally proven (all rule combinations) | Plausible but misses compound cases |
| Verification | `ASSERT is_satisfiable` (C1: status oracle) | — |
| Solver class | C1 (categorical: SAT / UNSAT / UNKNOWN) | — |

## The hidden constraint

Rule R3: `self_employed → income ≥ $50,000`  
Rule R2: `income ≥ $30,000 OR has_collateral`  
Rule R4: `credit_score ≥ 650 OR (credit_score ≥ 600 AND income ≥ $80,000)`

If `self_employed=True` AND `income=$45,000` AND `credit_score=700`:
- R3 is violated (income < $50K required for self-employed)
- R4 passes (700 ≥ 650 ✓)
- LLM often approves this applicant, focusing on the high credit score
- Z3 correctly returns `INELIGIBLE` because R3 fails

Z3 finds this by exhaustively checking all rule interactions — not just left-to-right tracing.

## Default problem (QuickLoan Policy v2.1)

| Rule | Description |
|---|---|
| R1 | Age ≥ 18 |
| R2 | Income ≥ $30K OR has_collateral |
| R3 | self_employed → income ≥ $50K |
| R4 | credit_score ≥ 650 OR (credit_score ≥ 600 AND income ≥ $80K) |
| R5 | months_employed ≥ 12 OR has_collateral |

Z3 finds a qualifying profile: `age=18, income=50000, credit_score=650, months_employed=12, has_collateral=False, self_employed=False`.

## Install

```bash
conda activate graf

# https://github.com/Z3Prover/z3/wiki#background
# https://z3prover.github.io/papers/programmingz3.html
pip install z3-solver
```

## Run commands

```bash
# solver=ON — Z3 theorem prover
graf run cookbook_solvers/z3_compliance/z3_compliance.graph.yaml \
    --llm claude_cli --param use_solver=true

# solver=OFF — LLM manual tracing
graf run cookbook_solvers/z3_compliance/z3_compliance.graph.yaml \
    --llm claude_cli --param use_solver=false

# Custom policy text
graf run cookbook_solvers/z3_compliance/z3_compliance.graph.yaml \
    --llm claude_cli --param use_solver=true \
    --param "policy_text=Subscription eligibility: user must be 13+, account in good standing, and premium_tier=true or lifetime_member=true."
```


## TOOL_API reference

| Function | Purpose |
|---|---|
| `get_default_policy()` | Returns hardcoded QuickLoan policy JSON — demo / fast-path fallback when no `policy_text` is supplied |
| `is_empty_policy(policy_text)` | Returns `"true"` if `policy_text` is empty (user did not pass `--param policy_text=...`); deterministic branch, no LLM call |
| `parse_policy_json(json_str)` | Strips markdown fences, parses and validates LLM-extracted policy JSON; falls back to default if malformed |
| `check_z3_eligibility(policy_json)` | Z3 SAT/UNSAT check → qualifying profile or contradiction |
| `is_satisfiable(result_json)` | ASSERT gate: `status == "SAT"` |
| `format_z3_report(result_json, policy_json)` | Markdown report of Z3 results |

## Real-world applications

- **Insurance underwriting**: detect when coverage clauses make certain claim types impossible
- **Regulatory compliance**: verify that rule sets from different departments don't conflict
- **Access control**: prove that a permission matrix has no dead locks (users who can never access required resources)
- **Tax code**: find edge cases where two deduction rules cancel each other out

## Z3 as a SolverHub in miniature

Z3's internal architecture (Figure 1 of the [Z3 programming guide](https://z3prover.github.io/papers/programmingz3.html)) is itself a composition of specialist sub-solvers — SAT core, arithmetic solver, array solver, bit-vector solver, quantifier engine — coordinated by a central engine that routes each constraint to the best-suited internal solver. This is the SolverHub model applied within a single tool: a registry of solvers, each with a defined domain, composed by a dispatch layer. The parallel validates the architecture: the right abstraction at the problem layer is a registry + advisor, whether the registry spans open-source libraries (SolverHub) or internal algorithmic engines (Z3).

## Related recipes

- r78: constraint optimization via PuLP (LP/MILP — continuous variables, not logic)
- r105: Prolog inference — backward chaining for contract/compliance satisfiability
- r108: robust MILP — uncertainty over scenarios, not rule satisfiability
