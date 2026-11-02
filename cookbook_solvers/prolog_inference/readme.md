# Recipe 105 — Prolog-style Inference Engine

> **GraphLang port.** Lifted from SPL.py's `cookbook-solver/105_prolog_inference` with `spl3 util spl2graph` (no model was involved). The Python tools travel inside the graph as `SOLVE` nodes (`backend: kernel`), so `graf run` needs the `kernel` extra (`pip install 'graflang[kernel]'`) and the libraries named below, not SPL.py. Commands use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`.
> Not ported: `tools.py` (the SPL original's tool registration, experiment and app scripts).
> Test run (2026-11-01, `claude_cli` `claude-sonnet-5-5`, solver on): the graph completed (1 model calls, 286 tokens in / 292 out in total). A run that completes does not show the answer is right: read the output before you rely on a recipe.

**The key story:** Insurance policy with 4 rules and 3 customers. `carol` is eligible via a 4-level proof chain: `emergency_claim ← eligible_claim ← claim_covered ← catastrophic_event` (bypassing the deductible requirement). LLM traces `alice` and `bob` correctly but misses `carol`'s indirect path. The backward-chaining engine finds all proof paths automatically.

## What it demonstrates

| Axis | solver=ON | solver=OFF |
|---|---|---|
| Engine | Backward-chaining inference (Prolog-style) | LLM sequential rule tracing |
| Output | All satisfying bindings per customer | "alice qualifies, bob doesn't" |
| Guarantee | All proof paths found (complete search) | Misses indirect implications |
| Verification | `ASSERT inference_succeeded` (C1) | — |
| Solver class | C1 (categorical: ELIGIBLE / NOT ELIGIBLE) | — |

## Proof chains

```
emergency_claim(alice):
  eligible_claim(alice, emergency_repair)        [R1: comprehensive ✓, active ✓]
    claim_covered(alice, emergency_repair)       [R2: deductible_met(alice) ✓]
  emergency_event(alice) ✓
→ ELIGIBLE (3-level chain)

emergency_claim(bob):
  has_policy(bob, comprehensive) → FAIL (bob has "basic")
→ NOT ELIGIBLE (fails at rule R1, step 1)

emergency_claim(carol):
  eligible_claim(carol, emergency_repair)        [R1: comprehensive ✓, active ✓]
    claim_covered(carol, emergency_repair)       [R3: catastrophic_event(carol) ✓]
  emergency_event(carol) → NOT in facts
→ NOT ELIGIBLE via R4, BUT carol is still covered under eligible_claim
  (The recipe demonstrates the inference; a real policy would add R4 exception for catastrophic)
```

## Default knowledge base

**Facts:**
- alice: comprehensive, active, deductible_met, emergency_event
- bob: basic policy, claim_type=emergency (no policy_active)
- carol: comprehensive, active, catastrophic_event

**Rules:**
1. `eligible_claim(X, Type) :- has_policy(X, comprehensive), policy_active(X), claim_covered(X, Type)`
2. `claim_covered(X, emergency_repair) :- deductible_met(X)`
3. `claim_covered(X, emergency_repair) :- catastrophic_event(X)`
4. `emergency_claim(X) :- eligible_claim(X, emergency_repair), emergency_event(X)`

## Run results — solver=ON vs solver=OFF

Both runs used `claude_cli` / `claude-sonnet-4-6` on the same KB (3 customers, 4 rules).

### Performance

| Metric | solver=ON | solver=OFF |
|---|---|---|
| Timestamp | 2026-09-06 19:16:11 | 2026-09-06 19:16:28 |
| Tokens in | 317 | 346 |
| Tokens out | 587 | 670 |
| Total tokens | 904 | 1,016 (+12%) |
| Latency | 34.5s | 46.9s (1.4×) |
| Verdict coverage | All 3 customers, all proof paths | Sequential trace, first-path-wins |

### Verdict comparison

| Customer | Ground truth | solver=ON | solver=OFF |
|---|---|---|---|
| alice | ELIGIBLE | ✓ ELIGIBLE | ✓ ELIGIBLE |
| bob | NOT ELIGIBLE | ✓ NOT ELIGIBLE | ✓ NOT ELIGIBLE |
| carol | NOT ELIGIBLE | ✓ NOT ELIGIBLE | ✗ ELIGIBLE (wrong) |

### Analysis

**solver=ON is correct.** Carol has `comprehensive`, `policy_active`, and `catastrophic_event` — sufficient to satisfy `claim_covered` via R3. But Rule 4 additionally requires `emergency_event(carol)`, which is absent from the KB. The backward-chaining engine correctly fails the proof at R4.

**solver=OFF is wrong on carol.** The LLM reasoned semantically: *"a catastrophic event is a strict subset of emergency events — this holds ✓"* — importing real-world domain knowledge not present in the KB. From a strict logic standpoint this is an unsound inference; `emergency_event(carol)` is simply not a stated fact. The LLM's semantic intuition overrode the KB boundary.

**The LLM explanation in solver=ON is also wrong.** After receiving the correct solver output (carol=NOT ELIGIBLE), the LLM explanation step applied the same semantic injection: it constructed a proof chain that omitted the `emergency_event` requirement entirely and flagged the correct solver verdict as a "solver defect." The solver was right; its post-hoc interpreter was not.

### Key takeaway

This run pair reveals a failure mode absent from r103/r104: **the LLM explanation phase can contradict a correct solver result.** The solver's backward-chaining is sound by construction — it only accepts facts explicitly in the KB. The LLM, in both solver=OFF tracing and solver=ON explanation, injected world-knowledge (`catastrophic_event` semantically implies `emergency_event`) that is not encoded as a rule. The gap here is not about counting rows (r103/r104) but about **KB boundary enforcement**: solvers are immune to semantic drift; LLMs are not.

Token gap is smaller than r103/r104 (12% vs 70–230%) because the solver=ON explanation was verbose — the LLM wrote a detailed (incorrect) counter-argument. A tighter explain prompt scoped to "explain the solver's verdicts" rather than "evaluate the report" would reduce this.

## Run commands

```bash
# solver=ON — backward-chaining inference
graf run cookbook_solvers/prolog_inference/prolog_inference.graph.yaml \
    --llm claude_cli \
    --param use_solver=true

# solver=OFF — LLM manual tracing
graf run cookbook_solvers/prolog_inference/prolog_inference.graph.yaml \
    --llm claude_cli \
    --param use_solver=false
```

## Install

```bash
conda activate spl123
# No additional install — pure Python implementation
```

## TOOL_API reference

| Function | Purpose |
|---|---|
| `get_default_policy()` | Returns ComprehensiveAuto_v3 policy JSON with 3 customers |
| `run_inference(policy_json)` | Backward-chaining query over KB; returns eligibility per customer |
| `inference_succeeded(result_json)` | ASSERT gate: status OK and results exist |
| `format_inference_report(result_json)` | Markdown table of eligibility verdicts |

## How the inference engine works

1. **Query** `emergency_claim(alice)`: goal = `{pred: "emergency_claim", args: ["alice"]}`
2. **Rule match** R4 head `emergency_claim(?X)`: bind `?X=alice`
3. **Prove body**: `eligible_claim(alice, emergency_repair)` → recurse on R1
4. **R1 body**: `has_policy(alice, comprehensive)` → match fact ✓; `policy_active(alice)` → match fact ✓; `claim_covered(alice, emergency_repair)` → recurse on R2
5. **R2 body**: `deductible_met(alice)` → match fact ✓
6. **R4 body**: `emergency_event(alice)` → match fact ✓
7. All body goals proved → **ELIGIBLE**

## Real-world applications

- **Insurance underwriting**: find all valid claim paths across complex policy documents
- **Tax eligibility**: determine if a taxpayer qualifies for a deduction (multi-rule chains)
- **Access control**: resolve role hierarchies (manager → team_lead → engineer)
- **Legal compliance**: check if a contract clause triggers given a set of conditions

## Related recipes

- r102: Z3 SMT solver — satisfiability of constraint rules (not clausal)
- r103: GE data quality — declarative expectations over data
- r108: robust MILP — uncertainty over numeric scenarios, not logical rules
