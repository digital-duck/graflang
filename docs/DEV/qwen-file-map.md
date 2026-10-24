# Qwen transcript: file map and first findings

Source: `readme-qwen.md` (9,087 lines, 371 KB). Read in sections: the work-graph part (lines 1-866, handled separately, see `work-graph-qwen-review.md`) and the GraphLang part (867-9087).

All code blocks that carry a path were extracted mechanically to a staging folder outside the repo (`<scratchpad>/qwen-extract/`, 72 files, with the original Qwen paths; later revisions of a file are `.v2`). Nothing was written into the repo. The extraction script is `<scratchpad>/tools/extract_qwen.py` (it reads the transcript, never modifies it).

## How the conversation went (GraphLang part)

| Lines | Topic |
|---|---|
| 867-1010 | SPL paper recalled; dynamic interpreter (dev) vs static compile (deploy); first YAML IR |
| 1010-1055 | fermion/boson analogy (Qwen: fermions = nodes, bosons = edges, Pauli exclusion = unique ids/type safety) |
| 1055-1306 | interaction nets, HVM; first SPL graph IR with `rewrite_rules`; Rust compiler offered |
| 1307-1881 | SPL grammar mapped to node types; `graph2spl`, `spl2graph`, first JSON schema, Streamlit page |
| 1882-2132 | 3-tier composition (inline / reference / sub-graph); recipe A revised |
| 2133-2470 | `050_code_pipeline` ported; resource resolver |
| 2472-2870 | vocabulary pruned and extended (`FORK`, `JOIN`, `CONTEXT`, `MUTATE`, `RECOVER`...); tightened schema; paper plan; `MUTATE` delta schema; interpreter prototype |
| 2871-3240 | Cedar `GUARD` node; `grafr`/`grafc` names; BibTeX; license advice (Apache 2.0) |
| 3240-3850 | final `code_pipeline.graph.yaml`; `mutation_safety.cedar`; README (archived as `archive/README-qwen-v0.1.md`) |
| 3851-4868 | `grafr` package; ports of self-refine and concept-book recipes |
| 4868-9087 | `grafc` package: analyzer, optimizer, Rust codegen, a hand-written Cedar lexer/parser/type checker/compiler, policy slicing, caching, composition, visualizer |

## Proposed placement

Qwen put `grafr/`, `grafc/`, `schema/` and `examples/` at the repo root. Your layout nests them under `graphlang/` and renames `examples/` to `cookbook/`. Mapping:

| Qwen path | Put it at | Notes |
|---|---|---|
| `pyproject.toml` | `pyproject.toml` | **edit**: name must be `graflang`, scripts `grafr` and `grafc`, packages under `graphlang` |
| `schema/graflang-ir.json` (block at 2526-2613, no path heading) | `graphlang/schema/graflang-ir.json` | valid JSON; lacks `GUARD` (see findings) |
| `schema/graph_delta.schema.json` (2683-2726) | `graphlang/schema/graph_delta.schema.json` | **not valid JSON as written** (leading `//` comment, odd `anyOf`); needs rewriting |
| `grafr/*.py`, `grafr/nodes/*.py` | `graphlang/grafr/...` | imports are relative (`from .x`), so they move cleanly; `runtime.py` finds the schema at `parent.parent/schema/...`, which breaks after the move (see findings) |
| `grafc/*.py`, `grafc/rust_gen/**`, `grafc/cedar/**` | `graphlang/grafc/...` | your design doc has only a stubbed `compiler.py`; Rust was postponed |
| `code_pipeline.graph.yaml` (3266-3430, no path heading) | `cookbook/code_pipeline/code_pipeline.graph.yaml` | |
| `examples/self_refine/**` | `cookbook/self_refine/**` | prompts are `.md` files |
| `examples/concept_book/**` | `cookbook/concept_book/**` | |
| `policies/mutation_safety.cedar` | `cookbook/code_pipeline/policies/mutation_safety.cedar` | open: gap #13 (per-example or shared) |
| `tests/test_cedar_compiler.py`, `tests/test_policy_slicer.py` | `tests/` | they test the hand-written Cedar compiler (see findings) |
| `README.md` | not used | archived |
| `scripts/graph2spl.py`, `spl3/graph_ir.py`(+v2), `spl3/resolver.py` | **hold**: these are SPL.py-side (`spl3` is its package) | decide where `spl2graph`/`graph2spl` live |
| `graphlang/interpreter.py` (early prototype) | skip | superseded by `grafr/runtime.py` |
| `src/workgraph/**` | skip | belongs to work-graph; reviewed separately |
| `context.rs`, `policies.rs` (8489, 8509) | `graphlang/grafc/rust_gen/templates/*.rs.j2` | Qwen gives them as snippets with no `.j2` path |
| 8708 (`guard.py` update), 8950 (CLI addition) | merge into `grafr/nodes/guard.py`, `grafc/cli.py` | snippets, not whole files |

Files Qwen never produced although your design doc lists them: `tests/test_topology.py`; the eight `.spl` procedure files and their prompts for `code_pipeline` (copy from `SPL.py/cookbook/050_code_pipeline`).

## First findings (verified mechanically unless marked)

Checked: every extracted Python file parses (except a truncated work-graph snippet that is not ours), and the three graph YAMLs were validated against Qwen's own schema.

1. **Flagship does not validate against its own schema.** `code_pipeline.graph.yaml` uses a `GUARD` node (inside the `LOOP` subgraph); the schema's node-type enum has no `GUARD`. The self-refine and concept-book files validate.
2. **`runtime.py` builds a plain `nx.DiGraph`.** A `triggers` edge and a `binds` edge between the same two nodes overwrite each other (one edge per node pair), and parallel edges are impossible. It should be a `MultiDiGraph`, which also matches the decision that edges are shareable carriers.
3. **The executor keeps a `visited` set**, so a node never runs twice: the retry wire in `LOOP` (`fail -> gen.trigger`) cannot re-execute anything. `FORK`/`JOIN` are not barriers in the main loop. It is a breadth-first walk of `triggers` edges, i.e. dataflow, not interaction-net rewriting (gap #7).
4. **Schema path breaks after the move.** `runtime.py` looks for `parent.parent / "schema" / "graflang-ir.json"`; with your layout the schema is at `graphlang/schema/`. It silently skips validation if the file is absent (`if schema_path.exists()`), so a wrong path means no validation and no error.
5. **`cedarpy` is not installed here and `cedar_guard.py` has a stub** ("In production, this would use cedarpy"). Cedar enforcement in `grafr` is not real yet.
6. **The hand-written Cedar compiler (`grafc/cedar/*`, about 1,500 lines).** Qwen wrote its own lexer, parser, type checker and Rust generator for Cedar, instead of using the official `cedar-policy` Rust crate (or `cedarpy` from Python). Reimplementing a formally verified language invites semantic drift. You said you would extend Cedar if necessary; this is a decision for you, not a default. (Judgement, not tested.)
7. **Unsupported numbers in the draft paper.** Qwen's abstract says topological constraints "reduce hallucination-induced infinite loops by 40%" and the plan hypothesizes audits "2x faster". No such experiment exists. They must not appear in any paper text.
8. **Citations need checking.** The Cedar entry's title, authors and venue look wrong to me (I believe the Cedar paper is "Cedar: A New Language for Expressive, Fast, Safe, and Analyzable Authorization", OOPSLA 2024), the SymPy entry is an `@misc` with a `journal` field, and the Lean key is `deMoura2021lean4` in the table but `de Moura2021lean4` in the entry. Verify each before use. (Not yet checked online.)
9. **Counts.** Qwen says "74 recipes" in places and the SPL paper says 78; "15 adapters" vs 14.
10. **`MUTATE` is described as validated by schema, but the interpreter prototype says "schema validation would happen here in production".** The delta schema is also invalid JSON (see mapping).
11. **Vocabulary that you have since changed:** Qwen calls `FORK`/`JOIN` superposition/entanglement (dropped), maps Pauli exclusion to unique ids and type safety (we use port exclusion), and treats conservation as a goal (dropped).

Next step suggestion: place the files that need no edits first (prompts, `examples/*.yaml`, `grafr/nodes/*`), then fix items 1-4 in `grafr`, and treat `grafc` as a stub until you decide on item 6.

## Placement done

Copied from the staging folder into the repo (verbatim, nothing edited; no file with content was overwritten):

- `pyproject.toml` (still Qwen's: gap #15)
- `graphlang/schema/` (2 files), `graphlang/grafr/` (13), `graphlang/grafc/` (21; where Qwen gave a later revision `.v2`, the later one was used)
- `cookbook/code_pipeline/code_pipeline.graph.yaml` (filled the empty file), `cookbook/self_refine/` (4), `cookbook/concept_book/` (5)
- `tests/test_cedar_compiler.py`, `tests/test_policy_slicer.py`
- three empty `__init__.py` files (`graphlang/`, `grafc/cedar/`, `grafc/rust_gen/`) so the packages import

Already in the repo from you and left alone: `graphlang/policies/{graph_safety,mutation_safety}.cedar` (identical to Qwen's), `cookbook/code_pipeline/readme.md`.

Not copied: README (archived), work-graph files, the early interpreter prototype, the two Rust-template snippets with no file path (`context.rs`, `policies.rs`, near lines 8489 and 8509), and the first (`v1`) revisions that Qwen later replaced.

`spl2graph` went to the SPL.py repo as `spl3/spl2graph.py` (see gap #21).

`graph2spl` went to the SPL.py repo as `scripts/graph2spl.py` (verbatim plus a status banner; it parses but is a sketch, not a faithful inverse of `spl2graph`).

## grafr runtime fixes (done)

Rewritten `graphlang/grafr/runtime.py` (plus small changes to `resolver.py`, `nodes/generate.py`, `nodes/solve.py`, `nodes/__init__.py` (new `register_executor`), `cli.py` and `schema/graflang-ir.json` (`GUARD`)). Findings 2-4 above are fixed; finding 4 was partly my error (the schema path was fine, the silent skip was not). New tests: `tests/test_grafr_runtime.py` (12). Executors are still mocks (gaps #23-#25).

## grafr: LOOP, conditions and a real LLM (done)

New: `grafr/expr.py` (safe evaluator), `grafr/adapters.py` (`mock` and SPL.py adapters, with `claude_cli` verified live), LOOP execution in `runtime.py`, last-writer-wins binds, input type coercion, `--model` and `--max-steps`. Changed: GENERATE/EVALUATE/SOLVE/ASSERT executors, `cli.py` (default adapter is now `mock`), and the cookbook YAMLs (LOOP `outputs`/`index_var`, missing binds, policy path). Tests: `test_grafr_expr.py` (24), `test_grafr_loop.py` (11), `test_grafr_adapters.py` (8), `test_grafr_runtime.py` (13). Semantics are written up at the end of `readme-design.md`.

## grafr: GUARD/Cedar, MUTATE, procedures, static checks, packaging (done)

`cedar_guard.py` now wraps the official engine (fail-closed); `GUARD` has `context_mapping`; `MUTATE` is implemented in the runtime; `procedure_ref` nodes run SPL.py workflows (`procedures.py`); `topology.py` backs `grafr validate` and `tests/test_topology.py`; `pyproject.toml` rewritten; the eight `.spl` files copied into `cookbook/code_pipeline/`. Fixed in Qwen's files: the dataclass bug in `grafc/cedar/ast_nodes.py` (it now imports), the `in [..]` Cedar syntax in `mutation_safety.cedar`, and the flagship's dead edge. Tests: 99 pass in the `spl123` env (93 in `graf`, where SPL.py is not installed) plus 10 failing Cedar-compiler tests (gap #18). Details at the end of `readme-design.md`.

