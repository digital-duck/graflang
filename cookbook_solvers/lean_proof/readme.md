# Recipe 76 — Lean Proof: generate-then-verify at proof grade

> **GraphLang port.** Lifted from SPL.py's `cookbook-solver/076_lean_proof` with `spl3 util spl2graph` (no model was involved). The Python tools travel inside the graph as `SOLVE` nodes (`backend: kernel`), so `graf run` needs the `kernel` extra (`pip install 'graflang[kernel]'`) and the libraries named below, not SPL.py. Commands use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`.
> Dropped from the commands, as `graf run` has no such option: `--kernel`.
> Test run (2026-11-01, `claude_cli` `claude-sonnet-5-5`, solver on): the graph completed (2 model calls, 189 tokens in / 37 out in total); Lean 4 is used for real (`~/.elan/bin/lean`, SPL.py's `LeanREPL`): the commutativity claim comes back `machine_proved` with a kernel-checked proof. The tool `run_python` runs in the shared kernel session so the Lean REPL started by one node is there for the next. A run that completes does not show the answer is right: read the output before you rely on a recipe.

The **B-3** milestone recipe of
[`docs/DEV/sage_lean_integration_plan.md`](../../docs/DEV/sage_lean_integration_plan.md):
the top rung of the **verifier ladder**. SymPy/Sage verify *instances*
(this eigenpair works); Lean verifies *statements* (the theorem itself).
The workflow is the conjecture-checking loop a mathematician runs by hand,
expressed declaratively.

> **Status: implemented.** Built on `spl3/lean_bridge.py` (milestone B-1,
> 15/15 tests green against the live REPL). An earlier prepared-but-untested
> draft of this recipe — written against a *planned* B-1 API — is preserved
> in git history (commit `00f1c2b`); this version is rewritten against the
> API that actually landed.

## What it demonstrates

```spl
@claim (prose)
   │ GENERATE formalize_claim                LLM   (probabilistic)
   ▼
@lean_stmt — a bare Lean 4 proposition
   │ statement_ok — does `example : <stmt> := by sorry` elaborate?
   │                                         Lean  (deterministic gate)
   │   ↺ fail → GENERATE fix_formalization(claim, stmt, lean feedback)  ≤ max_tries
   ▼
   │ GENERATE judge_faithfulness             LLM   (probabilistic — §B.4:
   │           does the Lean prop say what the prose says? the one link
   │           nothing machine-checks)
   ▼
   │ find — exact? probe: is this already a known lemma?
   │                                         Lean  (deterministic, zero tokens)
   │   hit → the suggestion IS the proof (citation path, B-5 seed)
   │   miss ↓
   │ GENERATE write_tactics                  LLM   (probabilistic — ONLY the
   │           tactic block; make_theorem splices the verified statement in
   │           verbatim, so the LLM can never prove a different statement)
   ▼
@proof — theorem spl_claim : <stmt> := by <tactics>
   │ check — kernel-check                    Lean  (deterministic gate)
   │   ↺ fail → GENERATE repair_tactics(stmt, tactics, lean feedback)   ≤ max_tries
   ▼
@badge: machine_proved | statement_checked | unverified
   ▼
@report — prose claim and Lean statement side by side
   │ machine_proved only → cache_put(badges='machine_proved',
   │           verifier='lean', statement=@lean_stmt)   (B-4: the badge
   │           lands in Layer 2 cache provenance; `spl3 cache show <key>`
   │           renders prose and statement together for the §B.4 audit)
   ▼
@cache_key
```

Design points carried over from the plan:

- **Repair loops are capped** (`@max_tries`, default 3) and fed Lean's
  *actual diagnostics* (`_spl_lean.feedback`) — the generate-then-verify
  spine at proof grade. On exhaustion the claim keeps its lower badge:
  **Lean failure never blocks delivery, it only withholds the higher badge**
  (§B.2).
- **The faithfulness gap is surfaced, not hidden** (§B.4): a kernel-checked
  proof means "this *Lean statement* is proved" — the informal↔formal
  correspondence is judged by a separate LLM call (FAITHFUL/UNFAITHFUL +
  reason) and rendered in the report next to the prose claim for human audit.
- **Citation before proving** (§B.4/B-5): `exact?` runs before any
  proof-writing LLM call. On a hit, the library lemma is the proof — zero
  tokens, and a citation into a curated library is stronger correspondence
  evidence than a bespoke proof of a bespoke statement.
- **The verified statement never round-trips through the LLM** (recipe 67's
  lesson): `make_theorem` assembles `theorem spl_claim : <stmt> := by <tactics>`
  deterministically in-process.

## Kernel-side API (`spl3/lean_bridge.py`, milestone B-1)

The recipe drives one persistent `LeanREPL` instance (`_spl_lean`) inside
the IPython kernel via `CALL run_python(...)`:

| Call | Contract |
|---|---|
| `LeanREPL().start()` | Spawn the persistent `leanprover-community/repl` (pinned `v4.30.0`), warm up a base environment; stdlib-only by default — pass `project_dir=`/`imports=` for mathlib. |
| `statement_ok(stmt) -> bool` | Elaborate `example : <stmt> := by sorry` in a fresh env forked from the warm base (env-id hygiene, §B.2). `True` iff it typechecks with only the sorry warning. |
| `check(code) -> dict` | Kernel-check a full declaration; `['ok']` is `True` iff no errors and no sorries. |
| `feedback -> str` | Lean's diagnostics from the most recent call — fed back into the repair prompts. |
| `find(stmt) -> str \| None` | `exact?` probe; returns the suggested term/lemma or `None`. |
| `repl_available() -> bool` | Toolchain probe; lets tests skip when the REPL is absent. |

Timeouts restart the REPL transparently; crashes recover on the next call
(see `tests/test_lean_bridge.py::TestTimeoutAndRestart`).

## Setup (one-time)

```bash
bash cookbook/tools/lean/setup_lean.sh   # elan + pinned repl v4.30.0, built with lake
```

## Run

```bash
# Default claim: "addition of natural numbers is commutative"
graf run cookbook_solvers/lean_proof/lean_proof.graph.yaml --llm claude_cli

# Local model
graf run cookbook_solvers/lean_proof/lean_proof.graph.yaml --llm ollama:gemma3

# Your own claim
graf run cookbook_solvers/lean_proof/lean_proof.graph.yaml --llm claude_cli \
    --param claim="for any natural number n, n^2 >= n" \
    --param max_tries=3

```

## Verified example runs (2026-06-11, `--llm claude_cli`)

| Claim | Formalization | Path | Badge | LLM calls |
|---|---|---|---|---|
| addition of natural numbers is commutative *(default)* | `∀ n m : Nat, n + m = m + n` | citation — `exact?` returned `Nat.add_comm`, zero proof tokens | `machine_proved` | 2 |
| for any natural number n, n² ≥ n | `∀ n : Nat, n ^ 2 ≥ n` | LLM proof — `intro n; exact Nat.le_self_pow (by decide) n`, kernel-checked first try | `machine_proved` | 3 |

Failure mode also exercised: before the prompts warned that mathlib is not
imported, the model reached for `ring` (unknown tactic in stdlib), burned the
3-try repair cap — fed Lean's real diagnostics each round — and the run
completed with `statement_checked`: the badge was withheld, delivery wasn't
blocked, exactly the §B.2 contract.

## Good first claims

Stdlib-decidable or simple-tactic territory (the default REPL is
stdlib-only; point it at a mathlib project for the full library):

- *addition of natural numbers is commutative* (`Nat.add_comm`)
- *for any natural number n, n² ≥ n* (`omega`/`induction` territory)
- *n + 0 = n for every natural number* (`rfl`)

## Files

| File | Purpose |
|---|---|
| `lean_proof.graph.yaml` | The workflow (validated; warnings are linter heuristics — the WHILE loops are bounded by `@tries < @max_tries`) |
| `readme.md` | This file |

## Relation to the milestones

| Milestone | This recipe's role |
|---|---|
| B-1 (`lean_bridge`) | Consumer — drives the persistent `LeanREPL` from the kernel |
| B-2 (statement checking) | Stage 1 + the faithfulness judge (Stage 2) |
| **B-3 (proof + repair loop)** | **This recipe** (Stage 3b) |
| B-4 (`machine_proved` badge) | Producer — a kernel-checked run writes the `machine_proved` claim badge to the Layer 2 cache with `verifier='lean'` and the statement stored for side-by-side audit (`statement_checked` is recipe-internal: well-formedness isn't a trust badge) |
| B-5 (mathlib citation) | Stage 3a — the `find`/`exact?` citation path |
