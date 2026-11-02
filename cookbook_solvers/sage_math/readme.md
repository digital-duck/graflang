# Recipe 75 — SageMath Solver (the second rung of the verifier ladder)

> **GraphLang port.** Lifted from SPL.py's `cookbook-solver/075_sage_math` with `spl3 util spl2graph` (no model was involved). The Python tools travel inside the graph as `SOLVE` nodes (`backend: kernel`), so `graf run` needs the `kernel` extra (`pip install 'graflang[kernel]'`) and the libraries named below, not SPL.py. Commands use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`.
> The lift skipped statements GraphLang has no node for: basic_sagemath.spl: tool 'isinstance' has no Python source in the SPL: the node names it but cannot run it.
> The Sage steps are `SOLVE` nodes with `backend: kernel` and `kernel_name: sagemath`, so the graph needs the SageMath Jupyter kernel (`pip install 'spl-llm[sage]'`, `python -m sage.repl.ipython_kernel.install --user`, check with `jupyter kernelspec list`) and no flag; `graf run --kernel-name sagemath` sets the kernel for the nodes that name none. The lift left the Sage statements as bare expressions, so they were rewritten by hand into kernel nodes (the preflight `isinstance(1, Integer)`, `version()`, the four operations, the timer) and the last `ASSERT` checks the result of the operation that ran.
> Test run (2026-11-01, `claude_cli` `claude-sonnet-5-5`, solver on): completes; "what is the Galois group of x^5 - x - 1 over the rationals?" gives transitive group 5 of degree 5, S₅ (order 120), and the explanation says the quintic is not solvable by radicals. A run that completes does not show the answer is right: read the output before you rely on a recipe.

**Pattern:** `SOLVE`/`ASSERT` routed to the **SageMath Jupyter kernel** via
`spl3 run sandwiched between two `CREATE FUNCTION`
(LLM) steps

This recipe is the companion to recipe 67 (SymPy), one rung up the
**verifier ladder** of
[`docs/DEV/sage_lean_integration_plan.md`](../../docs/DEV/sage_lean_integration_plan.md):

```
numeric spot-check (NumPy) → exact symbolic instance (SymPy / Sage) → machine-checked proof (Lean)
```

It is the first cookbook demonstration of the **A-1 milestone**: the
`kernel_name` plumbing that lets any SPL workflow run under any installed
Jupyter kernel spec — here, SageMath, whose kernel preloads the full Sage
namespace (PARI, GAP, Singular, Maxima, …).

## What this demonstrates

The same three-regime sandwich as recipe 67, with two upgrades:

```
Probabilistic (LLM)    — parse natural language → Sage expression + operation
Deterministic (Sage)   — exact computation via SOLVE in the Sage kernel
Probabilistic (LLM)    — explain that exact result in plain English
```

1. **The math SymPy can't reach.** Every operation here lives beyond (or far
   beyond) SymPy's comfort zone — that's §A.1 of the plan, made concrete:

   | Operation | Computes | Engine under the hood |
   |---|---|---|
   | `galois` | Galois group of a polynomial over ℚ | PARI |
   | `conic` | exact rational-point decision on a conic over ℚ | Sage number theory |
   | `rank` | Mordell–Weil rank of an elliptic curve | PARI/mwrank |
   | `factor` | exact factorization over ℚ | FLINT |

2. **No `TOOL_API` wrapper for the math.** In recipe 67 the symbolic work runs
   inside a `CREATE TOOL_API` body (exec'd in-process). Here the deterministic
   step is `SOLVE` itself — the statement routes to the kernel, and under
   `--kernel-name sagemath` the kernel namespace *is* Sage. The integration
   surface is exactly one CLI flag, which is the whole point of A-1.

## Architecture

```
ASSERT isinstance(1, Integer)   → preflight: fails fast unless we're on the Sage rung
SOLVE @sage_banner := version() → engine-of-record logged (passagemath 10.8.x)
GENERATE parse_math_problem()   → probabilistic: NL → "<expression>|<operation>"
EVALUATE @operation_lc          → dispatch to one SOLVE per operation:
    SOLVE ... galois_group() / Conic(...).has_rational_point() /
              EllipticCurve(...).rank() / factor(...)
ASSERT len(str(_spl_solve_result)) > 0   → kernel state persists across statements
GENERATE explain_solution()     → probabilistic: plain-English explanation
```

The preflight is worth a pause: under the Sage kernel the *preparser* turns
integer literals into Sage `Integer`s, so `isinstance(1, Integer)` is `True`.
Under the plain `python3` kernel, `Integer` is a `NameError` and the workflow
**refuses to run on the wrong rung** — no silent downgrade, the same honesty
principle as the plan's fallback-tiering design (§A.2).

## Prerequisites

```bash
conda activate spl123
pip install 'spl-llm[sage]'                          # passagemath wheels — no source build
python -m sage.repl.ipython_kernel.install --user    # register the 'sagemath' kernel spec
jupyter kernelspec list                              # verify: 'sagemath' should be listed
```

## Run

```bash
# Default problem: Galois group of x^5 - x - 1
graf run cookbook_solvers/sage_math/basic_sagemath.graph.yaml \
    --llm ollama:gemma3

# Rational point on a conic (Legendre-style question)
graf run cookbook_solvers/sage_math/basic_sagemath.graph.yaml \
    --llm claude_cli \
    --param problem="does x^2 + y^2 = 3*z^2 have a rational solution?"

# Elliptic curve rank (curve 11a1)
graf run cookbook_solvers/sage_math/basic_sagemath.graph.yaml \
    --llm claude_cli \
    --param problem="what is the rank of the elliptic curve y^2 + y = x^3 - x^2 - 10*x - 20"

# Exact factorization over Q
graf run cookbook_solvers/sage_math/basic_sagemath.graph.yaml \
    --llm claude_cli \
    --param problem="factor x^4 - 1 over the rationals"
```

`--kernel-name sagemath` implies `--kernel`. If the spec is missing, the CLI
fails fast with install instructions (never a stack trace).

## Verified example runs (2026-06-10)

All four operations, run against the live Sage kernel:

| Problem | LLM parse → | Sage computed (exact) |
|---|---|---|
| Galois group of `x^5 - x - 1` | `x^5 - x - 1\|galois` | `Transitive group number 5 of degree 5` (= S₅) |
| rational solution of `x^2 + y^2 = 3*z^2` | `x^2 + y^2 - 3*z^2\|conic` | `(False, 3)` — no rational point; 3 is the obstruction prime |
| rank of `y^2 + y = x^3 - x^2 - 10*x - 20` | `[0, -1, 1, -10, -20]\|rank` | `0` (curve 11a1) |
| factor `x^4 - 1` over ℚ | `x^4 - 1\|factor` | `(x - 1) * (x + 1) * (x^2 + 1)` |

And the wrong-rung check: the same script under `--kernel` (plain python3)
fails immediately at the preflight —
`ASSERT kernel error: NameError: name 'Integer' is not defined`.

### Model notes — recipe 67's finding, reconfirmed

- **The contract cliff moved, but it's the same cliff.** The `rank` rule asks
  the LLM to read Weierstrass coefficients `[a1, a2, a3, a4, a6]` off an
  equation — the most "mathematical" parse in the recipe. `claude_cli` did it
  correctly from the raw equation; `gemma3` emitted the equation itself
  (with markdown-escaped carets) and the SOLVE failed. Rephrase the problem
  with explicit coefficients and `gemma3` is flawless. Same lesson as
  recipe 67/case-1: keep each `GENERATE`'s job small and mechanical, or use a
  model that holds the contract.
- **Exact computation ≠ correct narration.** In one `gemma3` run the Sage
  result was exactly right (`Transitive group number 5 of degree 5`, which is
  S₅, order 120) but the explanation claimed the group "has five elements."
  The verifier ladder bounds what can be wrong: the *math* is exact and
  auditable in the log; only the prose needs review. That is precisely the
  claim-trust vs exposition-trust split the plan's badge model formalizes
  (§B.1).

## Key learning points

1. **One flag widens the verification substrate.** Nothing in the parser, AST,
   or executor changed between recipe 67 and this recipe — `--kernel-name
   sagemath` swaps the entire deterministic regime from "SymPy in-process" to
   "full Sage distribution in a managed kernel." That is the locked design
   decision (kernel as universal interface) paying out.

2. **The Sage preparser works *for* you in SOLVE templates.** The substituted
   expression `x^5 - x - 1` is preparsed in the kernel: `^` means power,
   integers are exact `Integer`s, `1/2` would be an exact `Rational`. The LLM
   can speak natural Sage notation.

3. **Symbolic globals make quoting unnecessary.** `@expression` substitutes
   as *bare code*, not a string. Sage predefines symbolic `x`, and the setup
   step runs `var('x y z')`, so `QQ['x'](x^5 - x - 1)` and
   `QQ['x,y,z'](x^2 + y^2 - 3*z^2)` coerce symbolic expressions into exact
   polynomial rings — no string-escaping in sight. (Corollary: the LLM's
   expression is *executed* in the kernel — same trust model as
   `CALL run_python`, fine for a local demo, worth remembering for anything
   internet-facing.)

4. **Kernel state persists across statements.** The post-dispatch
   `ASSERT len(str(_spl_solve_result)) > 0` reads a variable the *previous*
   SOLVE left in the kernel — the A-1 parity property (state persistence,
   tested in `tests/test_kernel.py`) visible from SPL.

5. **SPL gotchas surfaced while writing this recipe** (extending recipe 67's
   list — paid once, documented here):
   - **`^` cannot appear literally in a SOLVE/ASSERT template** in the `.spl`
     source — the SPL lexer rejects it (`Lexer error: Unexpected character '^'`).
     It is fine inside `$$ … $$` prompt bodies, inside string literals, and in
     *runtime-substituted* variable values (the kernel preparses those).
   - **`==` cannot appear in a template either** — SPL's `=` token renders into
     the Python template as a single `=` (kwarg form), so an equality check
     becomes a syntax error in the kernel. Prefer `isinstance(...)`, `in`,
     `>`/`<`, or truthiness.
   - **`@var` inside a string literal is not substituted.** Markers are
     produced from `@var` *tokens*; `'@expression'` stays a literal. Pass
     expressions bare and let Sage coerce (point 3).
   - **`EVALUATE` lower-cases only the right-hand literal** — normalize with
     `CALL lower(...)` first (recipe 67, gotcha 4 — still true).

## Where this goes next (per the plan)

- **A-2** — `verifier: "sage"` nodes in `graph_lib` + domain YAML
  `kernel_name`, so concept-book notebooks (recipes 71/73/74) carry the Sage
  kernel in their `.ipynb` metadata.
- **A-4** — upgrade geometry-domain verifiers (conics, projective duality) to
  Sage, seed `classical_mechanics` with SageManifolds.
- **Part B** — the third rung: Lean 4 + mathlib, `machine_proved`.
