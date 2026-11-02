# Recipe 120 — Insurance Policy Z3 Inference Engine

> **GraphLang port.** Lifted from SPL.py's `cookbook-solver/120_insurance_policy_z3` with `spl3 util spl2graph` (no model was involved). The Python tools travel inside the graph as `SOLVE` nodes (`backend: kernel`), so `graf run` needs the `kernel` extra (`pip install 'graflang[kernel]'`) and the libraries named below, not SPL.py. Commands use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`.
> Not ported: `tools.py` (the SPL original's tool registration, experiment and app scripts).
> Test run (2026-11-01, `claude_cli` `claude-sonnet-5-5`, solver on): the graph completed (1 model calls, 378 tokens in / 248 out in total). A run that completes does not show the answer is right: read the output before you rely on a recipe.

**The key story:** Same 3-customer insurance policy as r105 (Prolog), now solved by Z3's Fixedpoint (Datalog) engine. Z3 applies the closed-world assumption strictly: it cannot infer `catastrophic_event` implies `emergency_event` from real-world semantics — it checks only what is explicitly stated. Carol's blocking fact (`emergency_event` absent) is machine-extracted and named in the output, eliminating the semantic-drift failure observed in r105's LLM explanation phase.

## What it demonstrates

| Axis | solver=ON | solver=OFF |
|---|---|---|
| Engine | Z3 Fixedpoint (Datalog) | LLM sequential rule tracing |
| Verdict | Per-customer SAT / UNSAT | "alice qualifies, bob doesn't" |
| Guarantee | Sound: only KB-stated facts used | Injects world-knowledge (semantic drift) |
| Blocking facts | Machine-extracted (abductive diagnosis) | Hallucinated or missed |
| Verification | `ASSERT inference_verified` (C1) | — |
| Solver class | C1 (categorical: ELIGIBLE / NOT ELIGIBLE) | — |

## vs. r105 (Prolog-style)

| | r105 (pure Python) | r120 (Z3 Fixedpoint) |
|---|---|---|
| Engine | Custom backward-chaining | Z3 SMT solver (Datalog engine) |
| Proof certificate | No — verdict only | Yes — `Z3 Proved` predicates listed per customer |
| Blocking diagnosis | No | Yes — `Missing / Blocking` column names exact absent facts |
| LLM semantic drift | Reproduced in explanation phase | Prevented: missing facts are anchored to machine output |
| Domain sort | Any (Python strings) | BitVecSort(8) — Z3 Datalog requires finite domain |

## Knowledge base (ComprehensiveAuto_v3)

**Facts:**

| Customer | has_comprehensive | policy_active | deductible_met | emergency_event | catastrophic_event |
|---|---|---|---|---|---|
| alice | ✓ | ✓ | ✓ | ✓ | — |
| bob | — | — | — | — | — |
| carol | ✓ | ✓ | — | — | ✓ |

**Rules:**

| ID | Rule |
|---|---|
| R2 | `claim_covered(X) :- deductible_met(X)` |
| R3 | `claim_covered(X) :- catastrophic_event(X)` |
| R1 | `eligible_claim(X) :- has_comprehensive(X), policy_active(X), claim_covered(X)` |
| R4 | `emergency_claim(X) :- eligible_claim(X), emergency_event(X)` |

## Expected Z3 output

| Customer | Eligible | Z3 Proved | Missing / Blocking |
|---|---|---|---|
| alice | ✓ | has_comprehensive, policy_active, deductible_met, emergency_event, claim_covered, eligible_claim, emergency_claim | — |
| bob | ✗ | — | eligible_claim (blocked by: has_comprehensive, policy_active, claim_covered); emergency_event |
| carol | ✗ | has_comprehensive, policy_active, catastrophic_event, **claim_covered, eligible_claim** | **emergency_event** |

Carol's row is the key finding: Z3 proved `claim_covered` and `eligible_claim` via the catastrophic_event path (R3 → R1), but `emergency_event` is the single, exact, machine-named blocking fact. No semantic inference is possible.

## Run results — solver=ON vs solver=OFF

Both runs used `claude_cli` / `claude-sonnet-4-6` on the same KB (3 customers, 4 rules).

| Metric | solver=ON | solver=OFF |
|---|---|---|
| Timestamp | 2026-09-06 21:35:03 | 2026-09-06 21:35:18 |
| Tokens in | 409 | 367 |
| Tokens out | 280 | 924 |
| Total tokens | 689 | 1,291 (+87%) |
| Latency | 13.7s | 32.1s (2.3×) |
| Alice | ✓ ELIGIBLE | ✓ ELIGIBLE |
| Bob | ✓ NOT ELIGIBLE | ✓ NOT ELIGIBLE |
| Carol | ✓ NOT ELIGIBLE | ✓ NOT ELIGIBLE |
| Carol blocking fact | `emergency_event` (machine-extracted by Z3) | `emergency_event` (identified via explicit KB list) |

### solver=ON explanation (key quote)

> *"Carol (DENIED): Z3 proved `catastrophic_event` and `eligible_claim`, but `emergency_event` is absent. Despite having a catastrophic event, no rule in the knowledge base derives `emergency_event` from `catastrophic_event`. The `emergency_claim` predicate therefore cannot fire."*
>
> *"Z3 cannot hallucinate missing rules."*

### solver=OFF trace (notable)

The LLM produced a full ASCII proof tree with `✓`/`✗` annotations per fact, including both R2 and R3 paths for `claim_covered`. It correctly denied Carol and added an adjuster note: *"If the claim is reclassified as an emergency event by an adjuster, R4 would fire and she would qualify. Recommend human review."* — actionable reasoning not present in the Z3 explanation.

### Comparison with r105

r105's solver=OFF **incorrectly approved Carol** by inferring `catastrophic_event ⊆ emergency_event` from world knowledge. r120's solver=OFF correctly denies Carol because the prompt explicitly lists customer facts row-by-row — the LLM is anchored to the KB rather than reasoning from a prose description.

The r105 semantic-drift failure was partly prompt design, not purely a solver problem. r120 solver=ON remains the authoritative path: Z3's `Missing / Blocking` output is formally derived and cannot drift regardless of prompt phrasing.

| Recipe | Engine | Carol verdict | Blocking fact named | Source |
|---|---|---|---|---|
| r105 solver=ON | Python backward-chaining | ✓ NOT ELIGIBLE | No | solver |
| r105 solver=OFF | LLM from prose description | ✗ ELIGIBLE (wrong) | — | LLM |
| r105 solver=ON explain | LLM post-hoc | ✗ "solver defect" (wrong) | — | LLM |
| r120 solver=ON | Z3 Fixedpoint | ✓ NOT ELIGIBLE | `emergency_event` | machine |
| r120 solver=OFF | LLM from explicit fact list | ✓ NOT ELIGIBLE | named in trace | LLM (anchored) |

## Run commands

```bash
# solver=ON — Z3 Fixedpoint inference
graf run cookbook_solvers/insurance_policy_z3/insurance_policy_z3.graph.yaml \
    --adapter claude_cli \
    --param use_solver=true

# solver=OFF — LLM manual rule tracing (r105 baseline)
graf run cookbook_solvers/insurance_policy_z3/insurance_policy_z3.graph.yaml \
    --adapter claude_cli \
    --param use_solver=false
```

## Install

```bash
conda activate spl123
pip install z3-solver  # already present if r102 has been run
```

**Note:** Z3's Datalog engine requires a finite domain sort. This recipe uses `BitVecSort(8)` (8-bit integers, 256 values) to represent customers. `IntSort` is rejected by Z3 Datalog as an infinite sort.

## TOOL_API reference

| Function | Purpose |
|---|---|
| `get_default_policy()` | Returns ComprehensiveAuto_v3 KB as JSON (facts + rules + customer list) |
| `run_z3_inference(policy_json)` | Z3 Fixedpoint inference; returns per-customer verdicts, proved predicates, missing facts |
| `inference_verified(result_json)` | ASSERT gate: status OK and results exist |
| `format_z3_report(result_json)` | Markdown table with Z3 Proved and Missing/Blocking columns |

## How the Z3 Fixedpoint engine works

1. Predicates declared as Z3 `Function(name, BitVecSort(8), BoolSort())`
2. Facts added as ground unit clauses: `fp.add_rule(has_comprehensive(ALICE))`
3. Rules added as universally quantified Horn clauses:
   ```python
   fp.add_rule(ForAll([x], Implies(And(p(x), q(x)), r(x))))
   ```
4. Z3 computes the least fixed point (forward chaining over the finite domain)
5. Queries: `fp.query(emergency_claim(CAROL))` → `sat` or `unsat`
6. Abductive diagnosis: for `unsat`, check each body predicate of R4 to find which is unsat, recurse one level for derived predicates

## Why this prevents LLM semantic drift

In r105, both solver=OFF (LLM tracing) and the solver=ON explanation step incorrectly granted Carol eligibility by inferring `catastrophic_event ⊆ emergency_event` from world knowledge. Z3 prevents this in two ways:

1. **Solver verdict is sound** — `fp.query(emergency_claim(CAROL))` returns `unsat` because `emergency_event(carol)` is simply not in the KB
2. **Explain prompt is anchored** — the `Missing / Blocking` column names `emergency_event` explicitly; the LLM explain prompt instructs: *"Do NOT infer that any missing fact is implied by another present fact"*

## Related recipes

- r102: Z3 SMT compliance checker — satisfiability over numeric/boolean constraints
- r105: Prolog-style inference — custom backward-chaining engine (same KB, no Z3)
- r103: GE data quality — declarative expectations (different solver class: C1 row-level)
