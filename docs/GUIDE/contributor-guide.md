# Contributor guide

How the code is organised, how to test it, and how to extend it. Read [`../DEV/readme-design.md`](../DEV/readme-design.md) too: it holds the numbered gap table (open and resolved items) and the written semantics. Update that table when you close or open a gap.

## Layout

```
graphlang/
  schema/      graflang-ir.json (node/edge schema), graph_delta.schema.json (MUTATE deltas)
  policies/    shared Cedar policies: graph_safety.cedar, mutation_safety.cedar
  grafr/       the dynamic interpreter (runtime, executors, CLI)
  grafc/       the compiler (mostly a stub; hand-written Cedar compiler, Rust codegen)
  grafv/       `graf vis`: workflow -> networkx model and a style; the engines are zinet's (`zinet.vis`)
cookbook/      example graphs: code_pipeline, self_refine, concept_book
tests/         pytest
docs/DEV/      design notes and the gap table
```

Imports are `graphlang.grafr...` and `graphlang.grafc...`.

## Setup and tests

```bash
pip install -e ".[dev]"
pytest                                        # everything
pytest tests/test_grafr_loop.py::test_name    # one test
```

Tests use the `mock` adapter; none needs an LLM. Known failures: `tests/test_cedar_compiler.py` and `tests/test_policy_slicer.py` exercise the hand-written Cedar compiler in `grafc/cedar/` (gap #18). Do not treat them as regressions from other work, but do not hide them either.

## grafr internals

- `runtime.py` loads YAML into a `networkx.MultiDiGraph` (a `triggers` and a `binds` edge may join the same pair) and runs it as token-passing dataflow. This is not interaction-net rewriting (gap #26). Nodes may re-fire; `JOIN` is a barrier; `FORK` emits on all control ports; `--max-steps` raises `RunLimitExceeded`. The schema is validated on load, and a missing schema is an error.
- `nodes/`: one executor per node type, subclasses of `NodeExecutor` (`nodes/base.py`), registered in `nodes/__init__.py`.
- `expr.py`: the safe condition evaluator. Any new condition feature goes here; never use `eval`.
- `adapters.py`: `mock` plus dd-llm adapters (`make_llm`, `resolve_model`). `procedures.py`: runs `procedure_ref` SPL workflows. `resolver.py`: the `resources` block.
- `cedar_guard.py`: Cedar via the official engine (`cedarpy`).
- `topology.py`: static checks behind `graf validate` and `tests/test_topology.py`.
- `cli.py`: a `click` group named `main`.

### Adding a node type or executor

1. Add the type to the enum in `graphlang/schema/graflang-ir.json` if it is new.
2. Write a `NodeExecutor` subclass in `graphlang/grafr/nodes/` and register it with `register_executor("TYPE", ...)`. Tests can swap executors the same way and restore `_EXECUTORS` afterwards (see `tests/test_grafr_runtime.py`).
3. Teach `topology.py` any config the node requires.
4. Add tests; document the semantics in `readme-design.md`.

### Adding a CLI command

Add a function to the package it belongs to (`graphlang/grafr/cli.py`, `grafc/cli.py` or `grafv/cli.py`) decorated with `@click.command("name")` and `click.argument`/`click.option`, then register it in `graphlang/cli.py` (`main.add_command(...)`). Keep rich output consistent with the existing commands.

## Cedar: fail closed

Cedar skips a policy that errors, for example a `forbid` that reads a context attribute that is not there. The `forbid` then silently stops applying, and a catch-all `permit` allows the request. `CedarGuard` therefore allows only if Cedar says Allow *and* no evaluation error occurred. When you add a policy that reads a new context attribute, make `GUARD`'s `context_mapping` and `MUTATE`'s context supply it. Edit `mutation_safety.cedar` carefully: strings are not valid on the left of `in [..]` in Cedar; use `[..].contains(x)`.

## Open questions you will run into

- **Cedar compiler in `grafc`**: repair the ~1,500-line hand-written one, or generate Rust that calls the official `cedar-policy` crate (gap #18, a decision for the owner).
- **Semantics**: whether to document the departure from interaction-net rewriting (#7, #26), and review of the LOOP design (#28).
- **Stubs**: `SOLVE` without `expression`/`procedure_ref` (#31), PII detection (#30).

## Conventions

- Vocabulary is settled by the owner: `FORK`/`JOIN` (short names, no implicit fan-out), port exclusion rather than Pauli-exclusion wording. Do not reintroduce superposition, entanglement or conservation language.
- Do not reuse unsupported numbers from the Qwen draft paper (40% fewer loops, 2x faster audits). No experiments exist.
- Treat Qwen-originated files (`docs/DEV/readme-qwen.md` is the raw transcript; `qwen-file-map.md` maps it to the repo) as unreviewed drafts; verify with tests before building on them.
