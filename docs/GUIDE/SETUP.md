# Setup

Install GraphLang, check that it works, and (optionally) connect a real LLM. Next: [TUTORIAL.md](TUTORIAL.md) walks through a first workflow; [USER-GUIDE.md](USER-GUIDE.md) is the reference.

> **Status:** early prototype. `graf run` (the runtime) works end to end on the bundled workflows. `graf compile` (the Rust compiler) is a stub.

## Requirements

- Python 3.11 or newer
- A conda env or venv of your own (the repo's work has used a conda env named `graf`)

## Install

From the repository root:

```bash
pip install -e ../dd-llm -e ../dd-logging -e ../zinet   # first, from sibling checkouts, until dd-llm, dd-logging and zinet >=0.2.0 are on PyPI
pip install -e ".[dev]"                     # runtime + pytest
```

If `pip` says `No matching distribution found for dd-llm>=0.2.0`, the first line is what is missing (PyPI only has dd-llm 0.1.0).

Optional extras:

| Extra | Adds | When you need it |
|---|---|---|
| `dev` | `pytest`, `pytest-asyncio` | running the tests |
| `anthropic`, `gemini` | the provider SDK, through dd-llm | those providers (the `openai` SDK is already a core dependency; only `claude_cli`, `gemini_cli` and `echo` need none; see below) |
| `spl` | SPL.py (`spl-llm`) | only `procedure_ref` nodes, which run SPL.py workflows |
| `vis`, `graphify` | `pyvis`, `graphify` | `graf vis --engine pyvis` / `--engine graphify` (the default engine, `graphviz` and `mermaid` need nothing extra) |
| `grafc` | `jinja2` | the compiler templates |

Core dependencies (`click`, `ruamel.yaml`, `networkx`, `jsonschema`, `cedarpy`, `dd-llm`, `rich`, `dd-llm[openai]`, `dd-logging`, `zinet`) come with the base install. `zinet` is the shared graph library: `graf vis` draws through it. `dd-llm` is the shared LLM layer that provides the adapters, and its `openai` SDK serves openai, openrouter, ollama, deepseek and qwen. `cedarpy` is the official Cedar engine and is required: `grafr` imports it at startup.

One console script is installed, `graf`, with the subcommands `run`, `validate`, `info`, `compile`, `check` and `vis`. `python -m graphlang ...` does the same thing.

## Check the install

```bash
graf --help
graf validate cookbook/self_refine/self_refine.graph.yaml
graf run cookbook/self_refine/self_refine.graph.yaml --adapter mock --param topic="rain"
graf vis cookbook/self_refine/self_refine.graph.yaml     # opens a picture of the workflow in your browser
pytest
```

`--adapter mock` calls no LLM and prints placeholder text, so it needs no network and costs nothing. Seeing `✓ Workflow completed` means the runtime, schema validation and Cedar import all work.

`pytest` has known failures: `tests/test_cedar_compiler.py` and `tests/test_policy_slicer.py` test the hand-written Cedar compiler in `grafc/cedar/`, which is unfinished (gap #18 in `docs/DEV/readme-design.md`). Everything else should pass.

## Connect a real LLM

Adapters come from [dd-llm](https://github.com/digital-duck/dd-llm), which is already installed with `graf`. `claude_cli` needs nothing else. `openai`, `openrouter`, `ollama`, `deepseek` and `qwen` work out of the box (the `openai` SDK is a core dependency). The others need their SDK, as an extra:

```bash
pip install -e ".[anthropic]"    # anthropic
pip install -e ".[gemini]"       # gemini
```

Adapter names: `claude_cli`, `gemini_cli`, `openai`, `anthropic`, `gemini`, `vertex`, `openrouter`, `ollama`, `deepseek`, `qwen`, `azure_openai`, `bedrock`, `momagrid`, `echo`. Keys come from the usual environment variables (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`, ...); see the dd-llm README.

Then choose the adapter and model at run time. The graph says *what* to generate; you choose *who* generates it:

```bash
graf run cookbook/self_refine/self_refine.graph.yaml \
    --llm claude_cli:claude-haiku-5-5 \
    --param topic="rain"
```

- `claude_cli` runs the Claude Code CLI on your subscription (dd-llm strips `ANTHROPIC_API_KEY` from the child process so it cannot bill the paid API).
- `ollama` needs a running Ollama server with the model pulled, and the `openai` extra (it speaks the OpenAI-compatible API).
- A `model:` written inside a node is only a hint. It is used when you give no `--model` (or `--llm ADAPTER:MODEL`) and it fits the adapter; `ollama/gemma3` is ignored under `claude_cli`.

Nodes that use `procedure_ref` (the `code_pipeline` procedures `00`-`07`) run SPL.py workflows, so they need SPL.py importable (`pip install -e ".[spl]"`, `pip install -e /path/to/SPL.py`, or `export SPL_PY_PATH=/path/to/SPL.py`) and only execute under a real adapter. Their logs go to `<graph folder>/.grafr/logs` (git-ignored).

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `ModuleNotFoundError: cedarpy` | base install missing; reinstall with `pip install -e ".[dev]"` |
| `adapter ... needs dd-llm` | dd-llm is missing; `pip install -e /path/to/dd-llm` |
| `adapter ... needs an extra package` | the provider SDK is missing; install the matching extra (`.[anthropic]`, `.[gemini]`) |
| `Unknown adapter ...` or `... API key required` | misspelled adapter name, or the provider's key variable is not set |
| `procedure_ref nodes need SPL.py` | install the `spl` extra or set `SPL_PY_PATH` |
| `✗ Run failed: stopped after N node firings` | a loop or retry wire never ended; fix the condition, or raise `--max-steps` (default 1000) |
| `✗ Run failed: ... unknown variable` | a condition reads an `@variable` that is not bound; the message names the node |
| Output is `[Mock LLM response ...]` | you passed `--adapter mock`; drop it (the default is `claude_cli`) or choose another adapter |

## For contributors

See [contributor-guide.md](contributor-guide.md) for the code layout, how to add a node type, and the design conventions.
