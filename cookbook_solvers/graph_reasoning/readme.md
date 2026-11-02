# Recipe 81 — Graph Reasoning

> **GraphLang port.** Lifted from SPL.py's `cookbook-solver/081_graph_reasoning` with `spl3 util spl2graph` (no model was involved). The Python tools travel inside the graph as `SOLVE` nodes (`backend: kernel`), so `graf run` needs the `kernel` extra (`pip install 'graflang[kernel]'`) and the libraries named below, not SPL.py. Commands use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`.
> Test run (2026-11-01, `claude_cli` `claude-sonnet-5-5`, solver on): the graph completed (2 model calls, 537 tokens in / 247 out in total). A run that completes does not show the answer is right: read the output before you rely on a recipe.

**Category:** reasoning · **Tier:** 2 · **Requires:** `networkx` (already installed — no pip install needed)

## What this demonstrates

This recipe extends the verifier ladder (67/75/78/79/80) into **discrete / combinatorial math** — shortest path, bipartite check, cycle detection — a problem class distinct from the continuous math (SymPy/Sage, recipes 67/75/77) and linear programming (PuLP, recipe 78) rungs already in the cookbook.

| Stage | Mode | Tool | Why |
|-------|------|------|-----|
| Parse natural-language graph problem | **Probabilistic** | LLM (`formulate_graph_code`) | LLMs read prose; graph solvers don't |
| Generate networkx code | **Probabilistic** | LLM | Code synthesis from intent |
| Run graph algorithm | **Deterministic** | `networkx` | Exact shortest path / bipartite / cycle answer |
| Gate on success | **Deterministic** | `ASSERT is_ok()` | Formal boundary: execution stops if the tool call failed |
| Repair failed code | **Probabilistic** | LLM (`repair_graph_code`) | LLM sees the actual exception; rewrites code |
| Interpret result | **Probabilistic** | LLM (`interpret_graph_result`) | Plain-English explanation of the verified answer |
| Round-trip check | **Deterministic** | `classify_roundtrip()` | Confirms the LLM's own restated "Final answer" matches the networkx ground truth |

**Key property:** networkx computes the graph answer; the LLM never traces the algorithm itself. The round-trip classifier is a second, independent check — it catches the LLM narrating a *different* number than the one it was just handed, which the ASSERT gate alone would not catch (ASSERT only checks the tool succeeded, not that the LLM repeated its answer faithfully).

## Setup

```bash
conda activate spl123
# networkx is already part of the spl123 environment — nothing to install
python3 -c "import networkx; print(networkx.__version__)"
```

## `enable_solver=false` vs `enable_solver=true`

- **`enable_solver=false`** (ARM B, unaided baseline): the LLM reasons about the graph entirely in prose — no networkx call happens at all. This is where LLMs are known to silently miscount edge weights or forget a node while "mentally" running Dijkstra.
- **`enable_solver=true`** (ARM A, default): the LLM writes runnable networkx code from the problem text; the code is executed by the deterministic `run_networkx()` tool; `ASSERT is_ok(@solution)` gates on successful execution (with up to `max_tries` repair attempts fed the real Python traceback); the LLM then narrates the verified result and restates a `Final answer: <value>` line, which `classify_roundtrip()` cross-checks against networkx's own computed value.

## Run

```bash
# Default problem (6-warehouse shortest-path network)
graf run cookbook_solvers/graph_reasoning/graph_reasoning.graph.yaml \
    --llm claude_cli

# Unaided baseline arm
graf run cookbook_solvers/graph_reasoning/graph_reasoning.graph.yaml \
    --llm claude_cli --param enable_solver=false

# Custom problem
graf run cookbook_solvers/graph_reasoning/graph_reasoning.graph.yaml \
    --llm ollama:gemma3 \
    --param problem="Is the graph with edges A-B, B-C, C-D, D-A bipartite?"

```

## Default problem

> A logistics network connects 6 warehouses (A, B, C, D, E, F) by roads with these distances in miles: A-B:4, A-C:2, B-C:1, B-D:5, C-D:8, C-E:10, D-E:2, D-F:6, E-F:3. What is the shortest route from warehouse A to warehouse F, and what is its total distance?

**Known optimum** (verifiable by hand): A → C → B → D → E → F, distance = 2+1+5+2+3 = **13**.

Verified end-to-end (2026-07-17) with `--llm ollama:gemma3` and `--llm claude_cli`: both produced correct networkx code, `ASSERT is_ok` passed on the first attempt, and the round-trip check returned `match`.

## Execution flow

```
GENERATE formulate_graph_code(@problem)   -- LLM writes networkx code
    │
CALL run_networkx(@code)                  -- networkx executes
    │
WHILE @tries < @max_tries                 -- repair loop on Error
    │
ASSERT is_ok(@solution)                   -- hard gate: AssertionError if not OK
    │
GENERATE interpret_graph_result(...)       -- LLM explains + states Final answer
    │
CALL classify_roundtrip(@narrative, @solution)  -- LLM's stated answer vs ground truth
    │
CALL format_report(...)                   -- Markdown report
```

## Output format

```markdown
# Graph Reasoning Report

**Problem:** ...
**networkx status:** `OK`
**Query type:** `shortest_path`
**Ground-truth answer:** `13`
**Round-trip check:** `match`

## Interpretation
...
Final answer: 13

## Solver Code (LLM-generated, networkx)
```python
...
```
```

## Exception handling

If networkx cannot complete the computation within `max_tries`, `ASSERT is_ok` raises `AssertionError`, caught by `EXCEPTION WHEN ToolFailed THEN`. The workflow exits with `status = "error"` and `roundtrip = "unverifiable"` rather than ever returning a hallucinated graph answer.
