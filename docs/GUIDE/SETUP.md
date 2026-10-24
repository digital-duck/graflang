# Setup

Install GraphLang, check that it works, and (optionally) connect a real LLM. Next: [TUTORIAL.md](TUTORIAL.md) walks through a first workflow; [USER-GUIDE.md](USER-GUIDE.md) is the reference.

> **Status:** early prototype. `grafr` (the runtime) works end to end on the bundled workflows. `grafc` (the Rust compiler) is a stub.

## Requirements

- Python 3.11 or newer
- A conda env or venv of your own (the repo's work has used a conda env named `graf`)

## Install

From the repository root:

```bash
pip install -e ".[dev]"     # runtime + pytest
```

Optional extras:

| Extra | Adds | When you need it |
|---|---|---|
| `dev` | `pytest`, `pytest-asyncio` | running the tests |
| `spl` | SPL.py (`spl-llm`) | real LLM adapters (`claude_cli`, `ollama`, ...) and `procedure_ref` nodes |
| `grafc` | `jinja2` | the compiler templates |

Core dependencies (`click`, `ruamel.yaml`, `networkx`, `jsonschema`, `cedarpy`, `rich`) come with the base install. `cedarpy` is the official Cedar engine and is required: `grafr` imports it at startup.

Two console scripts are installed, `grafr` and `grafc`. `python -m graphlang.grafr.cli ...` and `python -m graphlang.grafc.cli ...` do the same thing.

## Check the install

```bash
grafr --help
grafr validate cookbook/self_refine/self_refine.graph.yaml
grafr run cookbook/self_refine/self_refine.graph.yaml --param topic="rain"
pytest
```

The `run` uses the default `mock` adapter, which calls no LLM and prints placeholder text, so it needs no network and costs nothing. Seeing `✓ Workflow completed` means the runtime, schema validation and Cedar import all work.

`pytest` has known failures: `tests/test_cedar_compiler.py` and `tests/test_policy_slicer.py` test the hand-written Cedar compiler in `grafc/cedar/`, which is unfinished (gap #18 in `docs/DEV/readme-design.md`). Everything else should pass.

## Connect a real LLM

Real adapters come from SPL.py and must be importable. Pick one:

```bash
pip install -e ".[spl]"            # from PyPI
pip install -e /path/to/SPL.py     # a local checkout
export SPL_PY_PATH=/path/to/SPL.py # or point at a checkout without installing
```

Then choose the adapter and model at run time. The graph says *what* to generate; you choose *who* generates it:

```bash
grafr run cookbook/self_refine/self_refine.graph.yaml \
    --adapter claude_cli --model claude-haiku-5-5 \
    --param topic="rain"
```

- `claude_cli` runs the Claude Code CLI on your subscription (SPL.py strips `ANTHROPIC_API_KEY` for it).
- `ollama` needs a running Ollama server with the model pulled.
- A `model:` written inside a node is only a hint. It is used when you give no `--model` and it fits the adapter; `ollama/gemma3` is ignored under `claude_cli`.

Nodes that use `procedure_ref` (the `code_pipeline` procedures `00`-`07`) run SPL.py workflows and only execute under a real adapter. Their logs go to `<graph folder>/.grafr/logs` (git-ignored).

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `ModuleNotFoundError: cedarpy` | base install missing; reinstall with `pip install -e ".[dev]"` |
| `Unknown adapter ...` or an SPL.py import error | SPL.py is not installed; see "Connect a real LLM" |
| `✗ Run failed: stopped after N node firings` | a loop or retry wire never ended; fix the condition, or raise `--max-steps` (default 1000) |
| `✗ Run failed: ... unknown variable` | a condition reads an `@variable` that is not bound; the message names the node |
| Output is `[Mock LLM response ...]` | you are on the default `mock` adapter; pass `--adapter` |

## For contributors

See [contributor-guide.md](contributor-guide.md) for the code layout, how to add a node type, and the design conventions.
