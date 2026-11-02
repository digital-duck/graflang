# Recipe 127 — PII Data-Flow Compliance with Three Engines

> **GraphLang port.** Lifted from SPL.py's `cookbook-solver/127_pii_compliance` with `spl3 util spl2graph` (no model was involved). The Python tools travel inside the graph as `SOLVE` nodes (`backend: kernel`), so `graf run` needs the `kernel` extra (`pip install 'graflang[kernel]'`) and the libraries named below, not SPL.py. Commands use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`.
> Not ported: `bench_engines.py`, `rules.json`, `tools.py` (the SPL original's tool registration, experiment and app scripts).
> Test run (2026-11-01, `claude_cli` `claude-sonnet-5-5`, solver on): all 2 graphs completed (1 model calls, 141 tokens in / 20 out in total). A run that completes does not show the answer is right: read the output before you rely on a recipe.

**The idea:** an LLM finds the personal data in a document (a *PII map*: types only, never the values); Boolean rules then decide whether the document may be sent to a destination. The rules are checked by one of three engines that **must give the same answer**:

| Engine | What it is | Needs |
|---|---|---|
| `stdlib` | a small evaluator in the standard library (the baseline) | nothing |
| `sympy` | `sympy.logic` `satisfiable` | `pip install sympy` |
| `z3` | the Z3 SMT solver | `pip install z3-solver` |

The default rules are an **illustration, not legal advice or a real GDPR / PCI rule set**:

| Rule | Meaning |
|---|---|
| R1 | PII sent to an external destination (`external_api`, `third_party_vendor`) must be masked |
| R2 | A social security number never leaves externally, even masked |
| R3 | Card numbers must always be masked |

## Customize the rules

The rules live in [`rules.json`](rules.json), which you can edit: `external_destinations` (which destinations count as external), `variables` (the facts the rules may use) and `rules` (each one `id`, `desc`, `expr`). An `expr` is built from `{"var": ...}`, `not`, `and`, `or`, `implies` and `const`. The facts available are `has_ssn`, `has_ccn`, `has_email`, `has_name`, `has_address`, `has_dob`, `has_phone`, `has_pii`, `is_masked`, `is_external` (the full list is `KNOWN_FACTS` in `tools.py`).

```bash
python cookbook-solver/127_pii_compliance/tools.py my_rules.json    # validates the file and checks the rules are consistent
graf run cookbook_solvers/pii_compliance/compliance_check.graph.yaml --adapter echo \
    --param rules_file=my_rules.json --param destination=external_api \
    --param 'pii_map={"entities":[{"type":"SSN","masked":false}]}'
```

With no `rules_file` the workflows use `rules.json`. A file that is missing, not JSON, or uses an undeclared fact is reported as an `ERROR` verdict and the workflow fails; it is never silently replaced by the defaults.

## What it demonstrates

1. **With concrete facts, nothing needs solving.** The facts come from the LLM's PII map, so "do the facts satisfy the rules" is plain evaluation. All three engines return the same violated rules on every one of the 16 fact assignments (tested). A solver earns its place on **search** questions: *are the rules mutually consistent?* (`rules_consistent`), *is there any compliant assignment?*, *which rules conflict?*
2. **Fail closed.** If the LLM's reply cannot be read as a PII map, the verdict is NOT COMPLIANT (`UNREADABLE_PII_MAP`), never "no PII found".
3. **No sensitive values in logs.** The extraction prompt asks for the *type* of data only.
4. **Ablation.** `use_solver=false` lets the LLM judge compliance itself; the report labels that verdict unverified.

## Measured on one machine (not quoted from elsewhere)

Produced by `python cookbook-solver/127_pii_compliance/bench_engines.py` (re-run it on your machine):

```
Python 3.11.5 on Linux-6.8.0-138-generic-x86_64-with-glibc2.35
16 fact assignments, 3 rules; engines agree on every assignment: True

| Engine | Packages | Import (ms) | Installed (MB) | One check (ms, median) | Consistency search (ms) |
|---|---|---|---|---|---|
| stdlib | standard library | 0 | 0 | 0.005 | 0.01 |
| sympy | sympy 1.14.0, mpmath 1.3.0 | 194 | 81 | 0.714 | 0.28 |
| z3 | z3-solver 5.3.1.0 | 33 | 86 | 1.265 | 1.00 |
```

Read it with care: it is one machine, one Python, one run, and only three Boolean rules. On this run SymPy is **not** lighter than Z3 (similar install size, and about six times slower to import), and for a plain check of concrete facts both solvers are two orders of magnitude slower than the standard-library evaluator. That is the honest reason to keep `stdlib` as the default and to reach for a solver when you ask search questions or the rules include arithmetic (which SymPy's Boolean logic does not handle, and Z3 does).

## Run

```bash
# the LLM extracts the PII map, the chosen engine checks the rules
graf run cookbook_solvers/pii_compliance/pii_compliance.graph.yaml --adapter claude_cli \
    --param engine=stdlib --param destination=external_api

# no LLM: check a PII map directly (this is also what GraphLang calls as a procedure)
graf run cookbook_solvers/pii_compliance/compliance_check.graph.yaml --adapter echo \
    --param 'pii_map={"entities":[{"type":"SSN","masked":false}]}' --param destination=external_api --param engine=z3

# ablation: the LLM judges compliance itself
graf run cookbook_solvers/pii_compliance/pii_compliance.graph.yaml --adapter claude_cli --param use_solver=false
```

## Files

| File | What |
|---|---|
| `tools.py` | the three engines, fact derivation, and the `@spl_tool` functions |
| `pii_compliance.graph.yaml` | LLM extraction, then the rule check (or the LLM ablation) |
| `compliance_check.graph.yaml` | the deterministic check only, no LLM call |
| `bench_engines.py` | measures the engines on your machine |
| `tests/test_pii_compliance_recipe.py` | agreement of the engines, fail-closed cases, both workflows run |

The same workflow as a GraphLang graph (extract, check, redact, re-check, Cedar release guard) is in [graflang](https://github.com/digital-duck/graflang), `cookbook/compliance_audit`.
