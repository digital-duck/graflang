# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

GraphLang: a graph-first language for agentic workflows. The graph (YAML, `*.graph.yaml`) is the program; the LLM mutates topology instead of writing code. It evolves from the sibling repo SPL.py (`spl3` package). Early prototype; much of the code was drafted by Qwen and then adopted/fixed piecemeal. `README.md` is aspirational (some claims, e.g. Rust compilation and Cedar enforcement, are not implemented yet).

**Read `docs/DEV/readme-design.md` first**: it holds the gap table (numbered items, status open/resolved) and the written semantics of LOOP/conditions/data/LLM. Update that table when you close or open a gap. `docs/DEV/qwen-file-map.md` explains where the Qwen-generated files came from; `docs/DEV/readme-qwen.md` (9k lines) is the raw transcript, so grep it rather than reading it.

## Commands

```bash
pip install -e ".[dev]"                      # extras: dev, anthropic/gemini (provider SDKs via dd-llm; the openai SDK is core), spl (procedure_ref only), grafc (jinja2)
pytest                                       # all tests
pytest tests/test_grafr_loop.py::test_name   # single test
graf run cookbook/self_refine/self_refine.graph.yaml --param key=value   # adapter defaults to `claude_cli` (real LLM!); add `--adapter mock` to run offline; --param is repeatable
graf validate|info <graph.yaml>
graf run ... --log-level debug --log-format jsonl|text|both --log-dir DIR --no-log --output-dir DIR --save-nodes --no-output   # logs default to ~/.graflang/logs
graf compile|check <graph.yaml>
graf vis <graph.yaml> [--engine cytoscape|graphviz|pyvis|graphify|mermaid] [-o FILE] [--no-open]   # draw the workflow (default ~/.graflang/vis/); `python -m graphlang ...` also works
```

`graf` is one `click` group (`main` in `graphlang/cli.py`); each command lives in its package (`grafr/cli.py`: run/validate/info, `grafc/cli.py`: compile/check, `grafv/cli.py`: vis) as a plain `@click.command("name")` and is registered in `graphlang/cli.py`. There are no `grafr`/`grafc` console scripts. Imports in tests must be `graphlang.grafr...` / `graphlang.grafc...`. Tests under `tests/test_cedar_compiler.py` and `test_policy_slicer.py` exercise the hand-written Cedar compiler and have known failures (gap #18).

Real LLM calls: `--llm claude_cli:<model-id>` (same as `--adapter claude_cli --model <id>`; `--llm` wins) goes through dd-llm (`/home/papagame/projects/digital-duck/dd-llm`, a core dependency; `pip install -e` it if missing). `procedure_ref` nodes additionally need SPL.py importable (`pip install -e /path/to/SPL.py` or set `SPL_PY_PATH`). Default `mock` adapter needs no LLM; tests use it.

## Architecture

- `graphlang/schema/`: `graflang-ir.json` (node/edge schema, validated by the runtime; a missing schema is an error, not a silent skip) and `graph_delta.schema.json` (MUTATE delta, enforced by `MUTATE`).
- `graphlang/grafr/`: the dynamic interpreter.
  - `runtime.py` loads YAML into a `networkx.MultiDiGraph` and executes it as **token-passing dataflow** (not true interaction-net rewriting, gap #26). Two edge types: `triggers` (control tokens between ports like `complete`/`pass`/`fail`) and `binds` (data, keyed by port name; last writer wins). Nodes may re-fire (retry wires work), `JOIN` is a barrier, `FORK` emits on all control ports, `--max-steps` bounds runaway loops (`RunLimitExceeded`).
  - `nodes/`: one executor per node type (GENERATE, EVALUATE, SOLVE, ASSERT, LOOP, GUARD, MUTATE, CONTEXT...), registered via `register_executor` in `nodes/__init__.py`. `LOOP` runs its `subgraph` once per iteration, with condition checked before each iteration.
  - `expr.py`: safe expression evaluator for `@var` conditions (no `eval`; whitelisted functions). Use it for any new condition syntax.
  - `adapters.py`: `mock` plus dd-llm adapters. `resolver.py`: resolves the `resources` block (procedures/prompts/policies, three-tier composition).
  - `cedar_guard.py`: Cedar checks for GUARD/MUTATE via the official engine (`cedarpy`), fail-closed (any evaluation error denies); callers must pass every attribute the policies read. `topology.py` backs `graf validate`. `procedures.py` runs a node's `procedure_ref` SPL workflow through SPL.py's executor. `MUTATE` validates (schema, structure, Cedar, budget) and applies deltas; a MUTATE inside a LOOP body affects only that iteration's copy (gap #32). `SOLVE` with neither `expression` nor `procedure_ref` is still a stub that yields True (gap #31).
- `graphlang/grafc/`: the compiler, mostly a stub. `cedar/` is a ~1,500-line hand-written Cedar lexer/parser/type checker/compiler (open decision: keep, or use the official `cedar-policy` crate); `rust_gen/` is Rust codegen; also analyzer/optimizer/visualizer.
- Logging: dd-logging (`/home/papagame/projects/digital-duck/dd-logging`, a core dependency; `pip install -e` it if missing) via `graphlang/logging_config.py`. Use `get_logger("grafr.<module>")` and `log_event(_log, "noun.verb", **fields)` (fields land as JSONL keys); never `logging.getLogger` or `print` for run diagnostics. Nothing is logged until `setup_logging` is called (the CLI does).
- `graphlang/grafv/`: `graf vis`. `model.py` turns a workflow YAML into a `networkx` graph (LOOP bodies become `parent` nodes, ids `<loop>/<node>`); `engines.py` draws it through a registry (`ENGINES`): `cytoscape` (default; self-contained HTML, Cytoscape.js bundled in `data/`, positions from `dot -Tjson` when Graphviz is installed), `graphviz` (SVG), `pyvis` and `graphify` (optional extras `vis`, `graphify`; `required: True` makes a missing package a clear error), `mermaid` (text; `open: False`). Add an engine by adding a `to_x(G, out, note)` function and an `ENGINES` entry.
- `graphlang/policies/`: shared Cedar policies (`graph_safety.cedar`, `mutation_safety.cedar`), referenced from graph YAMLs via `resources.policies`.
- `cookbook/`: example graphs (`code_pipeline`, `self_refine`, `concept_book`) with their `prompts/`. `code_pipeline` has its `.spl` procedures (`00`-`07`) next to the graph; running them for real needs SPL.py importable.

## Conventions

- Vocabulary is deliberately settled by the owner: node types `FORK`/`JOIN` (short names, no implicit fan-out), port exclusion rather than Pauli-exclusion wording. Don't reintroduce Qwen's superposition/entanglement/conservation language.
- Do not reuse unsupported claims from the Qwen draft paper (e.g. "40% fewer loops", "2x faster audits"); no experiments exist.
- Treat Qwen-originated files as unreviewed drafts; verify behaviour with tests before building on them.
