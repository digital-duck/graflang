# Recipe 67 — Symbolic Math Solver

> **GraphLang port.** Lifted from SPL.py's `cookbook-solver/067_symbolic_math` with `spl3 util spl2graph` (no model was involved). The Python tools travel inside the graph as `SOLVE` nodes (`backend: kernel`), so `graf run` needs the `kernel` extra (`pip install 'graflang[kernel]'`) and the libraries named below, not SPL.py. Commands use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`.
> `sympy_llm.spl`, `sympy_llm_v2.spl`, `sympy_math_multi_step.spl` are SPL workflows that graphs here call (`procedure_ref`); running those graphs also needs SPL.py importable (`pip install 'graflang[spl]'`).
> The lift skipped statements GraphLang has no node for: sympy_llm.spl: COMMIT inside a WHILE body was skipped (a LOOP body cannot reach wf_exit); sympy_llm_v2.spl: COMMIT inside a WHILE body was skipped (a LOOP body cannot reach wf_exit).
> `sympy_tools.spl` define tools only (no workflow) and are not ported.
> Dropped from the commands, as `graf run` has no such option: `--self-healing`.
> Not ported: `case-3-experiment.md`, `readme-momagrid.md`, `case-2-linkedin-v1.1.md`, `run_analysis.py`, `run_experiment.sh`, `app.py`, `app_experiment.py`, `run_experiment.py`, `case-1.md`, `case-2-linkedin-v1.0.md`, `test_run_with_sonnet-4-6.md`, `case-2-linkedin-v0.1.md`, `experiment_results.db`, `case-2-log.md`, `case-2-log-1.md`, `test_run_with_rnj-1.md`, `case-2-hackernews.md` (the SPL original's tool registration, experiment and app scripts).
> Smoke test (2026-11-01, placeholder model, no real model call): runs end to end with the placeholder model. This is a run-through of the graph, not a check that the answers are right: run it with a real model before you rely on it.

**Pattern:** `CREATE TOOL_API` (deterministic SymPy) sandwiched between two `CREATE FUNCTION` (LLM) steps

This recipe ships two workflows that share the same kernel architecture and
prompt-design philosophy:

| File | Workflow | Handles |
|---|---|---|
| [`hello_symbolic_math.graph.yaml`](hello_symbolic_math.graph.yaml) | `math_solver` | a problem that needs **one** symbolic operation |
| [`sympy_math_multi_step.graph.yaml`](sympy_math_multi_step.graph.yaml) | `math_solver_multi_step` | a problem that needs a **chain** of operations, run step-by-step via `CALL <workflow>` |

## What this demonstrates

The kernel as a **deterministic, symbolic substrate**. A math question flows through
three regimes, each handled by the tool best suited for it:

```
Probabilistic (LLM)    — parse natural language → SymPy expression + operation
Deterministic (SymPy)  — compute the exact symbolic result via the kernel
Probabilistic (LLM)    — explain that exact result in plain English
```

The LLM never approximates the math — it only does the two things language models
are uniquely good at: understanding the question and explaining the answer. SymPy
computes the answer exactly, every time.

## Architecture

```
GENERATE parse_math_problem()  → probabilistic: NL → "<expression>|<operation>"
CALL solve_with_sympy()        → deterministic: exact symbolic computation (no LLM)
GENERATE explain_solution()    → probabilistic: plain-English explanation of the exact result
```

`solve_with_sympy` supports `solve` / `roots`, `diff` / `derivative`, `integrate`,
`simplify`, `expand`, and `factor` — dispatched from the operation string the LLM
extracts from the question.

## Prerequisites

```bash
pip install sympy
```

(or run with `--self-healing` and let the kernel install it on first use)

## Run

```bash
graf run ~/.graflang/solvers/symbolic_math/hello_symbolic_math.graph.yaml \
    --adapter ollama --model gemma3

# Custom problem
graf run ~/.graflang/solvers/symbolic_math/hello_symbolic_math.graph.yaml \
    --adapter ollama --model gemma3 \
    --param problem="differentiate 3x cubed plus 2x"

# With self-healing (auto-installs sympy if missing)
graf run ~/.graflang/solvers/symbolic_math/hello_symbolic_math.graph.yaml \
    --adapter ollama --model gemma3 \
    --param problem="integrate sine of x"
```

## Key learning points

1. **Hallucination is structurally impossible on the computation.** The expression
   is parsed by the LLM, but the *answer* comes only from `solve_with_sympy` — exact
   symbolic algebra, not a language model's guess.

2. **`CREATE TOOL_API` imports lazily, at call time.** `solve_with_sympy` imports
   SymPy inside the function body so `--self-healing` can install it on first use
   without failing the whole workflow at parse time.

3. **The LLM is told to trust the symbolic result.** `explain_solution`'s prompt
   explicitly says "Do not re-derive the answer — trust the symbolic result above
   as exact," keeping the LLM in its lane (explanation, not computation).

4. **`EXCEPTION WHEN BudgetExceeded`** falls back to returning the raw SymPy result
   if the explanation step runs out of budget — the user still gets the exact
   answer, just without the narrative wrapper.

## See also: [`case-1.md`](case-1.md) — why the multi-step variant exists

[`case-1.md`](case-1.md) documents a head-to-head where `gemma3` correctly parsed
*"differentiate e\*\*x and simplify it if necessary"* into `exp(x)|diff, simplify`
in **9 tokens / 1.1s**, while `gemma4:12b` — a newer, larger model — burned its
**entire 1000-token budget** on the same prompt and returned nothing parseable
(`GENERATE chain returned empty content for @parsed`). It only succeeded once the
compound clause ("...and simplify it...") was removed from the prompt.

That's not a math-capability gap — the LLM never does the math. It's a
**complexity cliff in instruction-following**: the moment a single `GENERATE`
has to absorb a compound, multi-clause instruction, weaker contract-following
shows up as wasted budget and empty output rather than a wrong-but-usable
answer. `sympy_math_multi_step.graph.yaml` is the structural fix — see below.

---

# `sympy_math_multi_step.graph.yaml` — chains of operations, step-by-step

**Pattern:** decompose once (LLM) → `CALL` a reusable sub-`WORKFLOW` once per
step, in a `WHILE` loop, threading the running result deterministically →
explain the whole verified chain once (LLM)

## What this adds

`hello_symbolic_math.graph.yaml` handles problems that resolve to **one** `<expression>|<operation>`
pair. Many real problems don't — *"differentiate e\*\*x and then simplify the
result"*, *"expand (x+1) squared, then factor the expanded form"* — they're a
**chain**, where each operation acts on the previous one's exact result.

Rather than asking one `GENERATE` to plan the whole chain *and* get every
intermediate expression right in a single shot (the failure mode documented in
[`case-1.md`](case-1.md)), this workflow keeps every individual LLM call as
terse and single-clause as the prompts `gemma3` already handles cleanly:

```
Probabilistic (LLM)    — decompose the problem into an ORDERED list of
                         single-operation steps: "<expression>|<operation>",
                         where every step after the first uses the literal
                         placeholder PREV for "the previous step's result"
Deterministic (loop)   — CALL solve_one_step(...) once per step — a reusable
                         sub-WORKFLOW that resolves PREV by string-substitution
                         (never round-tripped through the LLM) and computes the
                         exact SymPy result
Probabilistic (LLM)    — explain the fully-computed, verified chain in
                         plain English, once, at the end
```

The LLM's two jobs shrink to exactly what it's good at — *splitting a compound
sentence into ordered clauses* and *narrating an already-correct chain* — and
never includes "track a running numeric expression across steps," which is
where `gemma4:12b` got lost.

## Architecture

```
GENERATE decompose_problem()        → probabilistic: NL → ordered "<expr>|<op>" lines (PREV chains them)
WHILE step in chain:
    CALL solve_one_step(step, running_expr) → sub-WORKFLOW, called once per item:
        resolve PREV → running_expr (deterministic string substitution)
        CALL solve_step_with_sympy() → deterministic: exact symbolic computation
        RETURN "<bare_result>|<human_readable_line>"
    split_part(...) → thread <bare_result> into the NEXT call's running_expr
GENERATE explain_chain()             → probabilistic: plain-English walkthrough of the verified chain
```

`solve_one_step` is a `WORKFLOW` `CALL`ed from another `WORKFLOW` — the same
"`CALL <workflow>` step-by-step" composition `self_refine.spl` uses for
`critique_workflow` (see `cookbook/05_self_refine/self_refine.spl`).

## Run

```bash
graf run ~/.graflang/solvers/symbolic_math/sympy_math_multi_step.graph.yaml \
    --adapter ollama --model gemma3

# Custom multi-step problem
graf run ~/.graflang/solvers/symbolic_math/sympy_math_multi_step.graph.yaml \
    --adapter ollama --model gemma3 \
    --param problem="expand (x+1) squared, then factor the expanded form"

# With self-healing (auto-installs sympy if missing)
graf run ~/.graflang/solvers/symbolic_math/sympy_math_multi_step.graph.yaml \
    --adapter ollama --model gemma3 \
    --param problem="differentiate e**x and then simplify the result"
```

Each run writes the verified, ordered chain to `<log_dir>/chain_trace.md` —
e.g. for *"expand (x+1) squared, then factor the expanded form"*:

```
1. expand((x + 1)**2) = x**2 + 2*x + 1
2. factor(x**2 + 2*x + 1) = (x + 1)**2
```

confirming the result of step 1 (`x**2 + 2*x + 1`) really did flow into step 2's
`factor(...)` call — not just that both steps individually succeeded.

## Example runs — model comparison on a chained problem

Same workflow, same problem — *"differentiate 3\*x\*\*3-x, then factor if needed"*
— run against three adapters/models. The symbolic computation is identical and
exact in every run (SymPy doesn't care which LLM is driving); what differs is
whether each model honors the terse-output contract at *both* ends of the
chain — `decompose_problem` (planning) and `explain_chain` (narration):

| Model | `decompose_problem` | chain (verified, identical every time) | `explain_chain` | Verdict |
|---|---|---|---|---|
| `claude_cli` | 6 tokens, 3.3s → `3*x**3 - x\|diff` / `PREV\|factor` | `9*x**2 - 1` → `(3*x - 1)*(3*x + 1)` | 69 tokens, 3.0s — terse, faithful, done | ✅ clean |
| `gemma3` (ollama) | 19 tokens, 3.2s → `(3*x**3 - x)\|diff` / `PREV\|factor` | same | 127 tokens, 2.6s — a bit more verbose, still correct and on-contract | ✅ works |
| `gemma4:12b` (ollama) | 389 tokens, 19.3s → `3*x**3-x\|diff` / `PREV\|factor` (eventually correct, ~20-65x the cost) | same | **1000 tokens, 39.7s → empty.** `WARNING: GENERATE chain returned empty content for @explanation` — `Output: (no COMMIT)` | ❌ fails |

```
graf run ~/.graflang/solvers/symbolic_math/sympy_math_multi_step.graph.yaml --llm claude_cli \
   --param problem="differentiate 3*x**3-x, then factor if needed, finally solve for x"
...
Output:  We're asked to find the derivative of 3x³ - x and then factor the result if
possible. First, taking the derivative term by term gives us 9x² - 1. This
expression is a difference of squares, so it can be factored into (3x - 1)(3x + 1).
The final answer is **(3x - 1)(3x + 1)**.
LLM calls: 2  Latency: 6500ms
```

```
$ graf run ~/.graflang/solvers/symbolic_math/sympy_math_multi_step.graph.yaml --llm ollama:gemma4:12b \
      --param problem="differentiate 3*x**3-x, then factor if needed"
...
GENERATE segment 1 (explain_chain) -> 1000 tokens, 39730ms
WARNING:spl.executor:GENERATE chain returned empty content for @explanation — variable unchanged
RETURN: 0 chars | status=complete, steps=2

Status:  complete
Output:  (no COMMIT)
LLM calls: 2  Latency: 59187ms
```

What makes this run more telling than `case-1.md`'s original comparison:
**`gemma4:12b` got the symbolic chain exactly right this time** — `decompose_problem`
eventually emitted a correct two-step plan, and the deterministic
`solve_one_step` chain computed and threaded `9*x**2 - 1 → (3*x - 1)*(3*x + 1)`
flawlessly (it always does — that part never depends on the LLM). It still
**failed the workflow outright**, and this time at the *easiest* step in the
whole pipeline: narrating an already-correct, already-verified result in plain
English. It burned its full 1000-token budget and produced nothing — the same
"wandered off into reasoning instead of answering" signature as the `case-1.md`
failure, just relocated to a different `GENERATE`.

That generalizes the lesson from `case-1.md`: this isn't a quirk of the parsing
prompt specifically — it's `gemma4:12b`'s general tendency to **overthink past
a strict, terse-output contract**, wherever that contract appears in the
pipeline. `claude_cli` and `gemma3` both honor it consistently, at both ends of
the chain, at a fraction of the token cost.

> **The bigger point — and arguably the real finding of this recipe:** the
> *answer* in every single run above was identical and exact —
> `(3*x - 1)*(3*x + 1)`, computed by SymPy, not by any LLM. The only thing that
> ever varied was whether the surrounding model could hold up its end of a
> terse output contract. That reframes "which model should I use here?"
> entirely: once a deterministic symbolic substrate owns the computation, a
> **small model that reliably honors a narrow contract beats a larger model
> that doesn't** — not by a small margin, but outright (one delivered a
> complete, correct, friendly explanation; the other delivered nothing). For
> *educational* tooling especially — where "always correct, always explained"
> is the entire point — small-model-plus-symbolic-reasoning isn't a budget
> compromise. It's the architecture that actually works, and the bigger model
> is the one making the trade-off, not the smaller one.

## Key learning points

1. **`CALL <workflow>(...)` composes workflows step-by-step**, exactly like
   `CALL <procedure>(...)` composes procedures (recipe 25) — `solve_one_step`
   is `CALL`ed once per item from inside a `WHILE` loop, with each call's output
   threaded into the next call's input via plain string variables.

2. **The chained value never round-trips through the LLM.** `PREV` is resolved
   to the running expression by deterministic string substitution inside
   `solve_one_step`; the LLM is never asked to read back its own (or SymPy's)
   prior numeric output and re-emit it — which is exactly the kind of multi-hop
   string task where weaker instruction-following shows up first (see `case-1.md`).

3. **Splitting one big LLM job into several small ones isn't just safer — it
   shrinks what any *one* `GENERATE` has to get right.** `decompose_problem`
   only orders clauses; `solve_one_step` does no LLM work at all; `explain_chain`
   only narrates an already-verified result. None of them needs to "hold" a
   compound instruction across the whole computation the way the single-step
   `parse_math_problem` does in `case-1.md`'s failing run.

4. **Two SPL gotchas surfaced (and fixed) while building this recipe** — worth
   knowing if you write similar chains:
   - `EVALUATE @val WHEN = 'PREV'` **never matches**, even when `@val` really is
     `'PREV'` — the executor lower-cases the right-hand literal but *not* the
     left-hand value. Normalize both sides yourself: `CALL lower(@val) INTO
     @val_lc` first, then compare against a lower-case literal.
   - f-string `{...}` interpolation only substitutes bare `{@var}` placeholders
     (regex `\{@(\w+)\}`) — **not** expressions like `{@i + 1}`. Compute a
     display variable first (`@step_no := @i + 1`) and interpolate that.

5. **Deterministic helpers mirror recipe 13's map-reduce pattern.** `step_count`
   and `extract_step` are zero-token `CREATE TOOL_API` functions — the same
   "count, then index" shape as `chunk_plan` / `extract_chunk` in
   `cookbook/13_map_reduce/tools.py` — used here to drive the `WHILE` loop over
   the LLM-decomposed step list without any further LLM calls.

---

## SPL Benefits — a reflection

Going from "solve one symbolic operation" (`hello_symbolic_math.graph.yaml`) to "solve a
*chained sequence* of operations" (`sympy_math_multi_step.graph.yaml`) is a genuinely
good showcase of why a **declarative agentic workflow language** is worth having
— not just that it works, but *why* it's worth it.

**Nothing about the kernel, the adapters, or the SymPy integration moved.** The
entire upgrade — from one operation to a chain of arbitrarily many — was
expressible as new declarative surface: a `CREATE FUNCTION` prompt template, a
`CREATE TOOL_API` for bookkeeping, a sub-`WORKFLOW`, and a `WHILE` + `CALL`
loop. No new Python plumbing, no new orchestration layer, nothing touched in
`executor.py`. That's the payoff of the declarative model: the *shape* of the
solution (single-step vs. chained) lives entirely in the script, while the
substrate (deterministic SymPy sandwiched between probabilistic LLM calls)
stays untouched and trustworthy underneath.

**Composability is real, not aspirational.** `CALL <workflow>` let this recipe
lift the exact same "parse → compute → trace" shape into a reusable unit and
run it N times with threaded state — the same pattern `self_refine.spl` uses
for `critique_workflow`, just applied to a completely different domain (symbolic
math vs. iterative critique). That's a strong signal the abstraction
*generalizes* rather than being a one-off trick: the same `CALL <workflow>`
mechanism solves "critique a draft repeatedly" and "run one symbolic step at a
time," with nothing in common between the domains except the composition
pattern itself.

**The tax is small, and now it's paid once.** The exercise also surfaced a few
sharp edges — `EVALUATE` string-comparison case-sensitivity, f-string
interpolation limits (§ Key learning points, above) — that aren't obvious until
you hit them. Documenting them here means the next recipe author doesn't
rediscover them the hard way. That's a fairly modest price for "rewrite the
script, not the engine" — and arguably the central case for SPL's flexibility:
**a multi-step symbolic-math solver is, in the end, just a `.spl` rewrite.**
