# GraphLang cookbook

Example workflows, each in its own folder with a `readme.md` (what it shows, how to run it, what to check). Run any of them from the repo root:

```bash
graf validate cookbook/<recipe>/<recipe>.graph.yaml     # the structure
graf run cookbook/<recipe>/<recipe>.graph.yaml --param key=value
```

A real run calls a real model and is billed (or uses your `claude_cli` subscription); give it a budget with a `--bind` file (`limits: {max_llm_calls: N}`). The recipe readmes say how many calls each makes.

## Status

**Validated** means the recipe's owner ran it for real and checked the output (as of 2026-10-31). It is a different thing from the automated tests (`pytest`), which cover every recipe's structure and most of their runs offline, with stub models or recorded answers.

| Recipe | Shows | Needs | LLM calls | Validated |
|---|---|---|---|---|
| [`self_refine`](self_refine) | three `GENERATE` nodes in a line, each node choosing its own LLM (`ollama:gemma3` → haiku → sonnet) | `claude_cli`, a running Ollama with `gemma3` | 3 | ✅ |
| [`chain_of_thought`](chain_of_thought) | a graph lifted from an SPL workflow; the topic reaches every step; a recorded cassette replays it with no model | `claude_cli` (or `--replay`) | 3 | ✅ |
| [`parts_demo`](parts_demo) | a named subgraph (part) used twice; `steps:` shorthand versus nodes and edges; an LLM per step | `claude_cli`, a running Ollama | 3 | ✅ |
| [`solver_check`](solver_check) | deterministic `SOLVE` (kernel and subprocess backends) and `ASSERT` routing | none: no model is called | 0 | ✅ |
| [`ts_verify`](ts_verify) | an LLM writes TypeScript, real tools (`tsc`, Node) judge it, and their errors drive the retry | `claude_cli`, Node 22.18+ | up to 3 | ✅ |
| [`code_pipeline`](code_pipeline) | procedures, a Cedar-guarded retry loop, `MUTATE`, `RECOVER` | `claude_cli` or Ollama, SPL.py (it runs `.spl` procedures) | up to 16 | ✅ |
| [`code_parts`](code_parts) | vibe-coding with a safety net: spec gate, review, a project folder as output (`FILES`), and a verification loop that runs the generated code | `claude_cli`; Python for the verification | 3 + one per repair round | ✅ |
| [`your_book`](your_book) | a book on any subject for a chosen audience (`intro` … `research`) and style: a `LOOP` that writes, reviews and revises one chapter per iteration | `claude_cli` or Ollama | 2 + 2 per chapter, plus a revision for each chapter sent back | ✅ |
| [`compliance_audit`](compliance_audit) | an LLM lists data types; deterministic rules and a Cedar guard decide the release | `claude_cli` | 1 if compliant at once, 3 if it must redact | ✅ |
| [`lifted_tool`](lifted_tool) | a Python tool lifted from SPL into a `SOLVE` node that carries its own source | none: no model is called | 0 | not yet |
| [`pocketflow`](pocketflow) | acceptance samples lifted from SPL's PocketFlow set (`majority_vote`, `debate`, `text_transformer`) | `claude_cli` (or `--replay`) | 3 (`majority_vote`), 11 (`debate`), 0 (`text_transformer`) | not yet |
| [`elaborate_demo`](elaborate_demo) | one template (a part) applied to every node of a graph of things | `claude_cli` | 1 per concept (4) | not yet |
| [`container_demo`](container_demo) | a program run inside Docker (no network, read-only) | a running Docker daemon | 0 | not yet |

The **Needs** and **LLM calls** columns summarise each recipe's own readme; check there before a run. "Not yet" means not yet validated by the owner, not known to be broken: each of these has automated tests, and `graf validate` passes for all of them.

## Reading order

1. `self_refine`: the smallest graph, and how a node names its LLM (`llm: "adapter:model"`).
2. `parts_demo`: how the compact `steps:` form relates to nodes and edges, and how a part is reused.
3. `chain_of_thought`: a graph that came from an SPL script, and a cassette that replays it offline.
4. `solver_check` and `ts_verify`: deterministic steps and real tools judging an LLM's output.
5. `code_pipeline` and `code_parts`: the same task two ways (SPL procedures; parts and a verification loop).

Recipes that are not in the table above are not part of the cookbook. New recipes go in the table with "not yet" until they are validated.
