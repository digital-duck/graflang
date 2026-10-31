# Changelog

## Unreleased

- A node's `config.model` is replaced by `config.llm: adapter[:model]` (the `--llm` spec). It beats the run's `--llm`, which beats the adapter default (`claude-sonnet-5-5` for `claude_cli`), so each task can choose its own model, or even its own adapter (created on first use; `llm.call` logs what ran). `:model` names a model on the run's adapter. `model:` on a GENERATE node is an error in `graf validate`; bindings `models:` / `model: $x` become `llms:` / `llm: $x`; the `mock` adapter answers every node. Before, the default acted as an override and node `model:` hints were ignored under `claude_cli`. A cassette records the default too (old ones still replay). SPL.py's lifter writes `llm: ":<model>"` for `USING MODEL`.

- `graf compile` takes `--lang rust|spl` (default rust) and `--dry-run`; `graf export-spl` is now `graf compile --lang spl`. Both languages run `graf validate`'s checks first and read compact, parts and elaborate files like `graf run` does. `graf check` is removed: it duplicated `validate` (schema, resources) and its extra analysis crashed on every graph; `graf compile --dry-run` is its replacement. `--target` is replaced by `--lang`.

## 0.1.1

- `graf vis`: nodes are labelled by what they do (`draft`, `write file`, `set iteration`, `repeat while ...`) with underscores shown as spaces, and show no type line (the colour and legend say it); the id and type are in the side panel. A node's `config.label` is used as written when present.
- Requires zinet 0.2.1.

## 0.1.0

First release: an early prototype. The graph (`*.graph.yaml`) is the program; the model changes the topology instead of writing code.

- `graf run`: token-passing dataflow over typed nodes (GENERATE, EVALUATE, SOLVE, ASSERT, LOOP, FORK/JOIN, GUARD, MUTATE, ...), with `--llm ADAPTER:MODEL` (default `claude_cli`; `--adapter mock` runs offline), run logs, and a results folder.
- Cedar `GUARD` and `MUTATE` checks (via `cedarpy`), fail-closed.
- `graf validate`, `graf info`, `graf check`; `graf compile` (Rust generator) is a stub and needs `pip install graflang[grafc]`.
- `graf vis`: draw a workflow (control flow first, data edges on demand, loops that collapse); engines cytoscape, graphviz, mermaid, ascii, and pyvis / graphify as extras.
- Shared libraries: dd-llm (adapters), dd-logging (logs), zinet (graph algorithms and drawing).
- The import package is `graphlang` (the PyPI name is `graflang`).
