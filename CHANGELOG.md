# Changelog

## Unreleased

- `cookbook/concept_book` is now `cookbook/your_book` (graph `your_book.graph.yaml`, workflow `your_book`), so it is not mistaken for the concept-graph-driven ConceptBook: it writes a book on any subject, for a chosen audience and style. Result folders are now named `your_book-<adapter>-<model>-<time>`.

- `your_book` takes `audience` (`intro`, `intermediate`, `advanced`, `research`; default `intro`) and `style` (free text), and every prompt uses them: the outline, each chapter, the review (which now also checks fit to the audience and style), the revision and the compile step (a "How to read this book"). This replaces `target_audience`, which was declared but never reached a node.

- `your_book`: the second chapter could repeat the first. The chapter prompt was given the loop's 0-based counter ("write chapter 1") while the outline numbers chapters from 1; a `chapter_number` step now passes the 1-based number and the total.

- `your_book` revises: the reviewer's verdict now routes an `EVALUATE`; `REVISION_NEEDED` sends the chapter and the feedback to a new `revise_chapter` step, and the book is compiled from the revised chapters (before, the verdict was collected and never used). To collect "the chapter, revised or not", a LOOP's `collect` (and the compact `out:`) now accepts a list of results, taking the one written last in each iteration, as `from` already did.

- A list in a prompt: `{{in_chapters}}` used to show Python's repr (`['chapter 1\\n...', ...]`); a list of texts now reads one after another with a blank line between, and any other list or mapping as JSON. `your_book`'s compile step had been handed 13 KB of escaped text and answered "Okay" (the book came out empty); its nodes also no longer pin `ollama:gemma3`, so the run's `--llm` applies, and its prompts ask for the text only.

- `graf create --name N --spec TEXT|@FILE [--out-dir DIR] [--llm adapter:model] [--max-rounds N] [--allow-code] [--force]`: vibe-coding for GraphLang. An LLM writes an app (a compact `.graph.yaml`, its prompts, a readme) from a plain-language spec; the result is checked like `graf validate` and by a dry run on the mock LLM, and the problems go back to the LLM for up to `--max-rounds` calls. Nothing generated is executed without `--allow-code`. The authoring guide and three example apps are shipped in the package (`graphlang/grafc/create_guide.md`, `create_examples/`).

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
