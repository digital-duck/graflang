# Changelog

## 0.1.0

First release: an early prototype. The graph (`*.graph.yaml`) is the program; the model changes the topology instead of writing code.

- `graf run`: token-passing dataflow over typed nodes (GENERATE, EVALUATE, SOLVE, ASSERT, LOOP, FORK/JOIN, GUARD, MUTATE, ...), with `--llm ADAPTER:MODEL` (default `claude_cli`; `--adapter mock` runs offline), run logs, and a results folder.
- Cedar `GUARD` and `MUTATE` checks (via `cedarpy`), fail-closed.
- `graf validate`, `graf info`, `graf check`; `graf compile` (Rust generator) is a stub and needs `pip install graflang[grafc]`.
- `graf vis`: draw a workflow (control flow first, data edges on demand, loops that collapse); engines cytoscape, graphviz, mermaid, ascii, and pyvis / graphify as extras.
- Shared libraries: dd-llm (adapters), dd-logging (logs), zinet (graph algorithms and drawing).
- The import package is `graphlang` (the PyPI name is `graflang`).
