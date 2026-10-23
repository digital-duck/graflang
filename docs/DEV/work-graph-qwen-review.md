# Review: Qwen's work-graph suggestions vs the real codebase

**Status (after Wen's decisions):** MCP server put off; `utils validate-pack` built; layered-graph design written (work-graph `docs/DEV/README-design.md` section 15) and built with the Layers tab (parent and child canvases); item 3 prompt skipped for now. The text below is the review as first written. Terminology is "layered graph", not "leveled".

Source: the "Work-Graph" part of `readme-qwen.md` (the "GraphLang" part of that file is still empty). Checked against `/home/papagame/projects/digital-duck/work-graph` (git clean at `f618315`, read-only so far; nothing changed there).

## Headline

Qwen reviewed a *description* of work-graph, not the code. Its snippets use names and a storage model that do not exist, so none of them can be pasted in as-is. Several of its claims about the repo are also wrong or already done. The ideas are mostly sound; the code needs rewriting against the real modules.

## What work-graph actually is (relevant facts)

- Graph data lives in **`<home>/out/graph.json`** (a NetworkX `MultiDiGraph` via `query.load_graph`). **SQLite (`workgraph.sqlite3`) holds only comments, uid history, sessions and sync state**: tables `files`, `comments`, `sessions`, `synced`, `node_ids`. There is **no `nodes` or `edges` table**.
- **Layered graphs already exist** (commit "add layered graphs"): `schema.py` has `PREFIX_LAYER`, `layer_of()`, `RELATION_RULES`; `refs.merge_layers` resolves cross-layer edges and `/**` sub-graph endpoints in memory; layers are fixed names (repo, process, product, org).
- `query.py` search functions take a **`list[Doc]`** (from `build_docs`), not the graph. `neighbors(M, node)` exists.
- Domain packs are validated on load: `Domain._check` already checks unknown stage references in `stages.next`, `flow_relations`, `expectations` and `classifiers`.
- `mcp` is installed in the base env; the `mcp` extra is declared but unused (design doc row "MCP server": not built). Search/show/context exist as CLI commands.
- The design doc's own status table (docs/DEV/README-design.md) lists what is built vs planned. Qwen did not use it.

## Item by item

| # | Qwen suggestion | Verdict | Problems with the snippet | Recommendation |
|---|---|---|---|---|
| 1 | **MCP server** (`mcp_server.py`) | Worth doing; not built | Imports `keyword_search(G, ...)`, `semantic_search(G, ...)`, `get_neighborhood`, `default_graph_path` from `query`/`paths`: none exist with those signatures (`keyword_search` takes `list[Doc]`; there is `paths.out_dir()`; `neighbors` not `get_neighborhood`). Reloads the graph on every tool call. Uses `r["id"]`/dict results where search returns tuples. `mcp.run(transport="sse", host=..., port=...)` is not the FastMCP signature. | **Do**, rewritten on `build_docs` + `keyword_search` + `neighbors` + `status`/`show`. Cache the loaded graph with mtime check. stdio only to start. Tests with the SDK's in-memory client. |
| 2 | **Recursive CTE** for `/**` and `part_of` | **Reject as written** | Queries an `edges` table that does not exist. `/**` expansion is already done in memory by `refs._descendants` (`nx.ancestors` on a small layer graph), which is not a bottleneck: layer files are hand-authored and small. | **Drop** for now. Only revisit if graph.json is moved into SQLite, which is a bigger decision (see item 6). |
| 3 | **`validate_domain_pack`** | Partly redundant | Re-implements checks `Domain.load/_check` already do, and wrongly: expects `domain`/`label` keys as required (label is optional), treats `next` check but not the real `use`/`match`/`kinds` processor fields, ignores `expectations`, `processors`, `ignore`. | **Do a thin version**: `workgraph utils validate-pack <path>` that calls `Domain.load` and reports its `ValueError` plus a few extra checks (processor `use` names exist, `kinds`). Small, mostly CLI wiring. |
| 4 | **SPL-style `llm_items` prompt** | Needs a diff against the real prompt first | Written without seeing `processors.py`' current prompt. Reads `domain_pack.get("processors", [{}])[0]["kinds"]` (first processor, wrong), hardcodes fallback `design`/`task`, truncates content to 4000 chars inside an f-string with a `# comment` that would be sent to the LLM, and ignores existing prompt caching (cache key is backend + prompt hash, so any change invalidates cached results). | **Hold** until I read the current prompt. Only adopt if it is demonstrably better on `examples/` (a live run uses the LLM, so ask first). |
| 5 | **`graphrag_retrieve`** / `ask` | Reasonable; overlaps `/workgraph` command | `keyword_search(G, query)` wrong signature; the "trim to max_nodes" step uses `list(set)[:n]`, which is arbitrary, not seeds-first as the comment claims; uses `G.predecessors/successors` on a MultiDiGraph (works) but edge dedupe by string key is fine. Output format is a good idea. | **Defer** until MCP exists: `get_node_context` with hop expansion and a compact text serializer covers most of it; `ask` can come after. |
| 6 | **Layered graph (meta-graph)** (layers as nodes, layer dependencies as edges, `level`, `storage`) | **The valuable idea; needs design, not code** | Qwen's `topology.py` hardcodes `symbol/file/repo/product/org` and a `storage` field, and proposes moving nodes to SQLite tables. That conflicts with the current model (graph.json is canonical; fixed layer names in `schema.py`). `Macro/Micro` was already rejected by Wen in favor of relative coarse/fine levels. | **Design first** (see below). Built as the "layer graph" in work-graph (see Status below). It is not a bridge to GraphLang: the two tools mean different things by a graph (see `readme-claude.md`, "work-graph vs GraphLang"). |

## Things Qwen got wrong about the repo (do not carry into docs)

- "52 passing tests" is from the design doc; fine. But the design doc also says 50 pass in conda base and the UI module is skipped; any new tests must run in the `graf` env.
- Suggests `blake3`/`xxhash` content hashing as if absent: results are already cached by backend + prompt hash, and file scanning reuses graphify's ignore cache.
- Suggests a custom domain pack directory "in `~/workgraph/custom/`" as a future item: **already built** (`custom/domains/`, "yours win").
- Suggests Cytoscape.js/pyvis integration: **already built** (`viz.py`, bundled Cytoscape.js, `workgraph viz`).
- Suggests a "Graph Health" dashboard and plugin system: not built, but reasonable; low priority.

## Proposed order of work

1. **MCP server** (item 1), rewritten against the real API, with tests. Highest value for the Claude Code workflow, self-contained, no schema change.
2. **`utils validate-pack`** (item 3), thin and honest.
3. **Layered-graph design note** (item 6): write the design in `docs/DEV/` first and relate it to the existing `layer_of`/`PREFIX_LAYER`. No code until agreed.
4. Items 2, 4 and 5: skipped or deferred as above.

## Decisions I need from Wen

1. Go ahead with 1 and 2 as described? (Changes only `work-graph`: new `mcp_server.py`, a CLI subcommand, tests, `pyproject` script entry, README/CLAUDE.md lines. I would not commit.)
2. For item 6: should the leveled design be written as a doc in `work-graph/docs/DEV/` or here under graflang, since it feeds GraphLang?
3. OK to run the live LLM extraction later to compare item 4's prompt, or skip item 4 entirely?
