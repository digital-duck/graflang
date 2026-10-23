
## Directory layout

```markdown

graflang/
├── LICENSE                 # Apache 2.0
├── README.md               # The vision, CLI usage (grafr / grafc), and link to the paper
├── pyproject.toml          # Python project config (for the `grafr` dynamic interpreter)
├── graphlang/              # GraphLang source
|   ├── schema/
│   ├── graflang-ir.json    # The tightened JSON Schema we defined
|   └── grafr/                  # The dynamic Python interpreter
│       ├── __init__.py
│       ├── runtime.py          # The NetworkX-based topological executor
│       ├── resolver.py         # The 3-tier resource resolver
│       └── cedar_guard.py      # Integration with the `cedar-policy` Python bindings
|   └── grafc/                  # The static compiler (stubbed for now, Rust target later)
│       └── compiler.py         # Translates Graph IR + Cedar to Rust AST
├── cookbook/
│   └── code_pipeline/
│       ├── code_pipeline.graph.yaml  # The masterpiece file above
│       ├── 00_analyze_spec.spl       # (copied from SPL.py)
│       ├── 01_generate_code.spl      # (copied from SPL.py)
│       ├── 02_review_code.spl        # (copied from SPL.py)
│       ├── 03_improve_code.spl       # (copied from SPL.py)
│       ├── 04_test_code.spl          # (copied from SPL.py)
│       ├── 05_document_code.spl      # (copied from SPL.py)
│       ├── 06_extract_spec.spl       # (copied from SPL.py)
│       ├── 07_spec_judge.spl         # (copied from SPL.py)
│       └── policies/
│           └── mutation_safety.cedar # The Cedar policy file
└── tests/
    └── test_topology.py    # Validates the YAML against the JSON schema

```
---

## Gap tracker (reconcile at the end)

Running list of discrepancies between README.md (Qwen draft), this design doc, and the code as files are populated. Add rows as they are found; mark resolved when fixed.

### Naming decisions (intentional, not gaps)

- Language is **GraphLang**; repo is **graflang** because searching "graphlang" on GitHub mostly returns LangGraph hits.
- `examples/` renamed to `cookbook/` on purpose, matching `SPL.py/cookbook`.
- Import name is `graphlang`; the pip package is named `graflang` (unique on PyPI/GitHub).
- `graphlang/` is the Python package layer; `grafr` = runner, `grafc` = transpiler/compiler, chosen to be unique.

### Decisions on process (Wen)

- Interaction nets are the **foundation, not a strict spec**: the theory is ~30 years old, so GraphLang may depart from it where useful. Gaps #6-#8 should be read as "decide and document the departure", not "conform".
- Final review of the populated codebase uses **rigorous best-practice standards** (correctness, tests, structure, security, packaging), plus a check of code against the documented design.
- Qwen's code is pasted as-is, then corrected in place by Claude where wrong; Wen keeps the originals in chat history.
- Nothing is committed yet; Wen will say when.

### Open items

Note: rows citing "README" refer to the archived Qwen draft `archive/README-qwen-v0.1.md`; apply the fixes to the new README when it is written.

| # | Area | Gap / question | Status |
|---|---|---|---|
| 1 | Paths | README quick start still says `examples/code_pipeline/` and top-level `policies/`; update to `cookbook/code_pipeline/` and `cookbook/code_pipeline/policies/` (rename is intentional) | open (README edit only) |
| 2 | README | `resources.procedures` lists 3 `.spl` files and `analyze` references `procedures.analyze_spec`, which is not declared; this doc has 8 files (00-07) | open |
| 3 | README | YAML example uses `@test_passed`, `@cycle`, `@in_analysis` with no declared port/variable | open |
| 4 | README | Roadmap ticks "Cedar integration" but `cedar_guard.py` does not exist yet | open |
| 5 | README | `MUTATE` is a headline feature but has no schema entry or example; `code_pipeline` does not use it | open |
| 6 | Semantics | README claims "strongly confluent"; holds only for the deterministic core, not for LLM-sampling nodes or `LOOP`. Wording needs qualifying | open |
| 7 | Semantics | Node ports (`trigger`/`complete`/`pass`/`fail`) read as dataflow, not interaction-net principal/auxiliary ports with rewrite rules; define how `grafr` realises interaction-net semantics | open |
| 8 | Semantics | Cedar role: `GUARD` checkpoint nodes (README) vs. Cedar gating whether any rewrite fires (see readme-claude.md); pick the primary model | open |
| 9 | Facts | README says SPL has 15 adapters / 1,200 runs; paper draft v3.0 says 14 adapters and 1,320 runs in places | open |
| 10 | README | Paper citation says "forthcoming"; no draft in repo yet | open |
| 11 | Tooling | README describes `grafc` as "compiles to Rust"; this doc calls it a stub, with the Rust target later | open |
| 12 | Schema | Define explicit `FORK` (one in, n out, forwards the same value; duplicator-like) and `JOIN` (n in, one out; define the rule, prefer collecting over first-arrival). No implicit fan-out or desugaring (Wen). The archived README's names `FORK`/`JOIN` are kept (Wen prefers shorter names) | open |
| 13 | Paths | `readme-qwen.md` lists the Cedar policy at `graphlang/policies/mutation_safety.cedar`; the design doc puts it at `cookbook/code_pipeline/policies/mutation_safety.cedar`. Decide whether policies are per-example or shared library policies | open |
