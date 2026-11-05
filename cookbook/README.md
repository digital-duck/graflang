# GraphLang cookbook

Every recipe is a graph: a `*.graph.yaml` that `graf` can validate, draw, run and describe. The recipes live in three folders, and **one file lists them all**: [`cookbook_catalog.yaml`](cookbook_catalog.yaml). It is the single source of truth. The tables below are generated from it, and so is every batch run.

| Folder | Suite | What it holds |
|---|---|---|
| [`cookbook/`](.) | `cookbook` | recipes written for GraphLang: the language's features one at a time, and small agents |
| [`cookbook_pocketflow/`](../cookbook_pocketflow) | `pocketflow` | SPL.py's PocketFlow set, lifted with `spl3 util spl2graph` |
| [`cookbook_solvers/`](../cookbook_solvers) | `solvers` | SPL.py's solver set (SymPy, Lean, Z3, MILP, game theory, ...), lifted the same way |

## Run one recipe

From the repo root, in the `graf` conda env:

```bash
graf validate cookbook/<recipe>/<recipe>.graph.yaml     # the structure; no model, free
graf run cookbook/<recipe>/<recipe>.graph.yaml --llm claude_cli:claude-sonnet-5-5 --param key=value
```

A real run calls a real model and is billed (or uses your `claude_cli` subscription); cap it with a `--bind` file (`limits: {max_llm_calls: N}`). Each recipe's `readme.md` says what it shows, which parameters it takes and what to check in the result.

## Run many: `run_all.py`

```bash
python cookbook/run_all.py --list                                  # the catalog, filtered by the options below
python cookbook/run_all.py --check --suite solvers                 # does this machine have what they need?
python cookbook/run_all.py --validate                              # `graf validate` every graph: offline, free
python cookbook/run_all.py --run --suite cookbook --workers 4      # `graf run` them (calls a model)
python cookbook/run_all.py --run --ids 'pocketflow.rag,solvers.lean_*' --llm ollama:gemma3
python cookbook/run_all.py --run --dry-run                         # print the commands only
python cookbook/run_all.py --write-readme                          # refresh the tables below
```

Select with `--suite`, `--category`, `--status`, `--needs` (for example `--needs kernel`), `--ids` (shell-style globs on the id) and `--all` (also the entries marked `active: false`, which wait for keyboard input). A run writes one log per recipe and a `results.yaml` to `cookbook/logs/<timestamp>/`.

## The catalog

An entry names a graph and says how to run it:

```yaml
- id: pocketflow.rag
  suite: pocketflow
  graph: cookbook_pocketflow/rag/rag.graph.yaml
  category: retrieval
  needs: [llm, spl]          # llm | kernel | sagemath | spl | stdin: checked by `run_all.py --check`
  params: {query: What is FAISS for?}
  status: lifted             # validated | ran | lifted | new | broken
  active: true               # in the default batch?
```

The full field list is at the top of the file. Status means:

- **validated**: the recipe's owner ran it for real and checked the output. This is different from the automated tests (`pytest`), which cover every recipe's structure and most runs offline, with stub models or recorded answers.
- **ran**: it completed under `run_all.py`; nobody has read the output yet. A run that completes does not show the answer is right.
- **lifted**: lifted from SPL.py, passes `graf validate`, not run yet.
- **new**: a GraphLang recipe that passes `graf validate` and has not been run.
- **broken**: known not to run; the entry's `note` says why.

To add a recipe: write the graph and its `readme.md`, add an entry with status `new`, run `python cookbook/run_all.py --validate --ids <id>`, then `--write-readme`.

## Reading order

1. `self_refine`: the smallest graph, and how a node names its LLM (`llm: "adapter:model"`).
2. `parts_demo`: how the compact `steps:` form relates to nodes and edges, and how a part is reused.
3. `chain_of_thought`: a graph that came from an SPL script, and a cassette that replays it offline.
4. `solver_check` and `ts_verify`: deterministic steps and real tools judging an LLM's output.
5. `code_pipeline` and `code_parts`: the same task two ways (SPL procedures; parts and a verification loop).
6. `pocketflow.*`, then `solvers.*`: the lifted sets, once the native recipes make sense.

## All recipes

<!-- catalog:begin -->

### Core recipes (`cookbook/`): 29 graphs

✅ 26 validated, ☑️ 1 ran, 🆕 2 new

| Recipe | Graph | Shows | Needs | Status |
|---|---|---|---|---|
| `agent_notes` | [`agent_notes/agent_notes.graph.yaml`](../cookbook/agent_notes/agent_notes.graph.yaml) | an agent loop (decide, act, observe): the model asks to read one note from a fixed list or answers; QUERY is the tool, behind a guard | claude_cli | ✅ validated (haiku) |
| `assembler` | [`assembler/assembler.graph.yaml`](../cookbook/assembler/assembler.graph.yaml) | a model assembles the workflow: it proposes adding one catalogue recipe, the graph checks and wires it in | claude_cli | ✅ validated (2026-11-04, haiku; picked the wrong recipe once) |
| `chain_of_thought` | [`chain_of_thought/chain_of_thought.graph.yaml`](../cookbook/chain_of_thought/chain_of_thought.graph.yaml) | a graph lifted from an SPL workflow; the topic reaches every step; a recorded cassette replays it with no model | claude_cli (or --replay) | ✅ validated |
| `chat_memory` | [`chat_memory/chat_memory.graph.yaml`](../cookbook/chat_memory/chat_memory.graph.yaml) | a chat with memory kept in a file: QUERY (last lines) in, EMIT (append) out | claude_cli | ✅ validated (haiku, two turns) |
| `code_parts` | [`code_parts/code_parts.graph.yaml`](../cookbook/code_parts/code_parts.graph.yaml) | vibe-coding with a safety net: spec gate, review, a project folder as output (FILES), and a verification loop that runs the generated code | claude_cli; Python for the verification | ✅ validated |
| `code_pipeline` | [`code_pipeline/code_pipeline.graph.yaml`](../cookbook/code_pipeline/code_pipeline.graph.yaml) | procedures, a Cedar-guarded retry loop, MUTATE, RECOVER | claude_cli or Ollama, SPL.py (it runs .spl procedures) | ✅ validated |
| `compliance_audit` | [`compliance_audit/compliance_audit.graph.yaml`](../cookbook/compliance_audit/compliance_audit.graph.yaml) | an LLM lists data types; deterministic rules and a Cedar guard decide the release | claude_cli | ✅ validated |
| `compliance_audit.compliance_audit_llm_only` | [`compliance_audit/compliance_audit_llm_only.graph.yaml`](../cookbook/compliance_audit/compliance_audit_llm_only.graph.yaml) | an LLM lists data types; deterministic rules and a Cedar guard decide the release | claude_cli | ✅ validated |
| `container_demo` | [`container_demo/container_demo.graph.yaml`](../cookbook/container_demo/container_demo.graph.yaml) | a program run inside Docker (no network, read-only) | a running Docker daemon | ✅ validated |
| `expand_demo` | [`expand_demo/expand_demo.graph.yaml`](../cookbook/expand_demo/expand_demo.graph.yaml) | one template (a part) applied to every node of a graph of things | claude_cli | ✅ validated |
| `guardrail` | [`guardrail/guardrail.graph.yaml`](../cookbook/guardrail/guardrail.graph.yaml) | a check in front of a model: off-topic questions are declined before the answering prompt sees them | claude_cli | ✅ validated (2026-11-03, haiku) |
| `heartbeat` | [`heartbeat/heartbeat.graph.yaml`](../cookbook/heartbeat/heartbeat.graph.yaml) | a beat that reports only what is new since the last beat (state in a file), run with graf watch; a quiet beat costs no model call | claude_cli | ✅ validated (2026-11-04, haiku) |
| `lifted_tool` | [`lifted_tool/lifted_tool.graph.yaml`](../cookbook/lifted_tool/lifted_tool.graph.yaml) | a Python tool lifted from SPL into a SOLVE node that carries its own source | none: no model is called | ✅ validated |
| `notes_digest` | [`notes_digest/notes_digest.graph.yaml`](../cookbook/notes_digest/notes_digest.graph.yaml) | QUERY reads a file, OBSERVE records it, EMIT writes it, all behind a Cedar GUARD | claude_cli | ✅ validated (haiku) |
| `parts_demo` | [`parts_demo/parts_demo.graph.yaml`](../cookbook/parts_demo/parts_demo.graph.yaml) | a named subgraph (part) used twice; steps: shorthand versus nodes and edges; an LLM per step | claude_cli, a running Ollama | ✅ validated |
| `pocketflow.debate` | [`pocketflow/debate.graph.yaml`](../cookbook/pocketflow/debate.graph.yaml) | acceptance samples lifted from SPL's PocketFlow set (majority_vote, debate, text_transformer) | claude_cli (or --replay) | ✅ validated |
| `pocketflow.majority_vote` | [`pocketflow/majority_vote.graph.yaml`](../cookbook/pocketflow/majority_vote.graph.yaml) | acceptance samples lifted from SPL's PocketFlow set (majority_vote, debate, text_transformer) | claude_cli (or --replay) | ✅ validated |
| `pocketflow.text_transformer` | [`pocketflow/text_transformer.graph.yaml`](../cookbook/pocketflow/text_transformer.graph.yaml) | acceptance samples lifted from SPL's PocketFlow set (majority_vote, debate, text_transformer) | claude_cli (or --replay) | ✅ validated |
| `recipe_chain` | [`recipe_chain/recipe_chain.graph.yaml`](../cookbook/recipe_chain/recipe_chain.graph.yaml) | guardrail -> agent_notes -> supervisor as parts, none edited: the acceptance test of the part interface | claude_cli | ✅ validated (2026-11-03, haiku; plumbing only) |
| `release_approval` | [`release_approval/release_approval.graph.yaml`](../cookbook/release_approval/release_approval.graph.yaml) | a model drafts, a person decides (DECISION), a Cedar guard checks, then the file is written | claude_cli | ✅ validated (2026-11-04, haiku, with `--answer`) |
| `self_heal` | [`self_heal/self_heal.graph.yaml`](../cookbook/self_heal/self_heal.graph.yaml) | a rule checks a model's JSON; a failed check sends the model its own rejected answer to fix | claude_cli | ✅ validated (both paths, haiku) |
| `doc_it` | [`doc_it/doc_it.graph.yaml`](../cookbook/doc_it/doc_it.graph.yaml) | write a document about a codebase (slide deck, tutorial, user guide, or your own prompt): a program reads the code, a model plans and writes, a program assembles and checks, a model fixes once; run it with `graf docs` | claude_cli | ☑️ ran (one real run (sonnet-5-5, 2 calls) on this repository) |
| `self_refine` | [`self_refine/self_refine.graph.yaml`](../cookbook/self_refine/self_refine.graph.yaml) | three GENERATE nodes in a line, each node choosing its own LLM (ollama:gemma3 → haiku → sonnet) | claude_cli, a running Ollama with gemma3 | ✅ validated |
| `solver_check` | [`solver_check/solver_check.graph.yaml`](../cookbook/solver_check/solver_check.graph.yaml) | deterministic SOLVE (kernel and subprocess backends) and ASSERT routing | none: no model is called | ✅ validated |
| `stock_analysis` | [`stock_analysis/stock_analysis.graph.yaml`](../cookbook/stock_analysis/stock_analysis.graph.yaml) | BATCH over a list of tickers: Python (SOLVE kernel) fetches prices and computes metrics, the model comments on each and writes one outlook | claude_cli, kernel extra, network | 🆕 new |
| `stock_copy` | [`stock_copy/stock_copy.graph.yaml`](../cookbook/stock_copy/stock_copy.graph.yaml) |  | llm | 🆕 new |
| `supervisor` | [`supervisor/supervisor.graph.yaml`](../cookbook/supervisor/supervisor.graph.yaml) | a supervisor approves or rejects a worker's answer in a bounded loop, and the graph says when nothing was approved | claude_cli | ✅ validated (approve path; reject path by test) |
| `ts_verify` | [`ts_verify/ts_verify.graph.yaml`](../cookbook/ts_verify/ts_verify.graph.yaml) | an LLM writes TypeScript, real tools (tsc, Node) judge it, and their errors drive the retry | claude_cli, Node 22.18+ | ✅ validated |
| `your_book` | [`your_book/your_book.graph.yaml`](../cookbook/your_book/your_book.graph.yaml) | a book on any subject for a chosen audience (intro … research) and style: a LOOP that writes, reviews and revises one chapter per iteration | claude_cli or Ollama | ✅ validated |

### PocketFlow recipes (`cookbook_pocketflow/`): 42 graphs

☑️ 36 ran, 🔁 6 lifted

| Recipe | Graph | Shows | Needs | Status |
|---|---|---|---|---|
| `a2a` | [`a2a/a2a.graph.yaml`](../cookbook_pocketflow/a2a/a2a.graph.yaml) | Implements an agent that accepts requests in JSON-RPC 2.0 format and runs a ReAct (Reason + Act) loop to answer them. A `parse_jsonrpc_request` tool extracts the question from the incoming... | llm | ☑️ ran |
| `agent` | [`agent/web_search_agent.graph.yaml`](../cookbook_pocketflow/agent/web_search_agent.graph.yaml) | Implements a ReAct (Reason + Act) web-research agent that iterates decide → search → accumulate until it has enough context to answer a question. The LLM decides the next action via structured... | nothing external | ☑️ ran |
| `agent_skills` | [`agent_skills/agent_skills.graph.yaml`](../cookbook_pocketflow/agent_skills/agent_skills.graph.yaml) | A skill-routing agent that dynamically selects the most appropriate prompt template from a directory of Markdown skill files before answering a task. The workflow scans the skills directory,... | llm | ☑️ ran |
| `agentic_rag` | [`agentic_rag/agentic_rag.graph.yaml`](../cookbook_pocketflow/agentic_rag/agentic_rag.graph.yaml) | Implements adaptive retrieval: rather than fetching a fixed set of chunks upfront, the LLM decides at each step whether it has enough information to answer or should retrieve one more document. On... | llm | ☑️ ran |
| `async_basic` | [`async_basic/async_basic.graph.yaml`](../cookbook_pocketflow/async_basic/async_basic.graph.yaml) | A recipe recommender that demonstrates SPL's async-capable pipeline: it fetches candidate recipes from an external API, asks the LLM to select the best match for available ingredients, presents a... | nothing external | ☑️ ran |
| `batch` | [`batch/batch_translator.graph.yaml`](../cookbook_pocketflow/batch/batch_translator.graph.yaml) | Translates a Markdown document into multiple target languages in a batch, preserving all Markdown formatting (headings, code blocks, tables, lists, links) exactly. For each target language, the... | llm, spl | ☑️ ran |
| `batch_flow` | [`batch_flow/batch_text_transformer.graph.yaml`](../cookbook_pocketflow/batch_flow/batch_text_transformer.graph.yaml) | Applies a multi-step image transformation workflow to an entire batch of images, iterating over every combination of image and filter via nested WHILE loops. For each (image, filter) pair, a... | nothing external | ☑️ ran |
| `batch_node` | [`batch_node/batch_node.graph.yaml`](../cookbook_pocketflow/batch_node/batch_node.graph.yaml) | Processes arbitrarily large CSV files in fixed-size chunks, computing running totals and averages over a numeric column without loading the entire file into memory. The workflow reads one chunk at... | nothing external | ☑️ ran |
| `chat` | [`chat/chat.graph.yaml`](../cookbook_pocketflow/chat/chat.graph.yaml) | Implements a multi-turn conversational loop that reads user input at the CLI, maintains a sliding-window JSON message history, and generates a contextually aware reply with each turn. The workflow... | stdin | 🔁 lifted |
| `chat_guardrail` | [`chat_guardrail/chat_guardrail.graph.yaml`](../cookbook_pocketflow/chat_guardrail/chat_guardrail.graph.yaml) | Adds a two-tier safety classifier layer to a multi-turn chat loop: a fast deterministic keyword filter runs first, and only messages that pass it are forwarded to an LLM topic classifier before... | nothing external | ☑️ ran |
| `chat_memory` | [`chat_memory/chat_memory.graph.yaml`](../cookbook_pocketflow/chat_memory/chat_memory.graph.yaml) | Extends a multi-turn chat loop with a two-tier memory architecture: a sliding window holds the most recent messages for immediate context, and a semantic archive stores older messages indexed by a... | nothing external | ☑️ ran |
| `cli_hitl` | [`cli_hitl/cli_hitl.graph.yaml`](../cookbook_pocketflow/cli_hitl/cli_hitl.graph.yaml) | Demonstrates the human-in-the-loop pattern via CLI: the workflow prompts the user for a topic interactively, generates a joke about it, displays the joke and asks for approval at the terminal, and... | nothing external | 🔁 lifted |
| `code_generator` | [`code_generator/code_generator.graph.yaml`](../cookbook_pocketflow/code_generator/code_generator.graph.yaml) | A test-driven code generation agent: it first generates a test suite for the problem, then generates a solution, and runs a WHILE loop that executes the tests against the solution — analyzing... | llm | ☑️ ran |
| `coding_agent` | [`coding_agent/coding_web_search_agent.graph.yaml`](../cookbook_pocketflow/coding_agent/coding_web_search_agent.graph.yaml) | An autonomous coding agent that implements stub functions in a codebase until a failing test suite passes. The agent runs in a WHILE loop, selecting one action per iteration from a fixed... | llm | ☑️ ran |
| `communication` | [`communication/communication.graph.yaml`](../cookbook_pocketflow/communication/communication.graph.yaml) | Processes a delimited list of text inputs one at a time in a WHILE loop, computing running word-count statistics (count, total words, average words per text) and accumulating a formatted log entry... | nothing external | ☑️ ran |
| `debate` | [`debate/debate.graph.yaml`](../cookbook_pocketflow/debate/debate.graph.yaml) | Runs a structured two-agent debate: `CALL PARALLEL` dispatches a Proponent and an Opponent LLM simultaneously to generate their opening arguments, then a WHILE loop drives successive rounds where... | llm | ☑️ ran |
| `deep_research` | [`deep_research/deep_research.graph.yaml`](../cookbook_pocketflow/deep_research/deep_research.graph.yaml) | Runs a recursive multi-iteration research pipeline: a planner generates three search queries per cycle, `CALL PARALLEL` dispatches all three searches and fact extractions concurrently, a... | llm, stdin | ☑️ ran |
| `flow` | [`flow/text_transformer.graph.yaml`](../cookbook_pocketflow/flow/text_transformer.graph.yaml) | An interactive text transformation tool that processes a pipe-delimited list of `type:input` commands in a WHILE loop, applying the selected transformation (uppercase, lowercase, reverse, collapse... | nothing external | ☑️ ran |
| `heartbeat` | [`heartbeat/heartbeat.graph.yaml`](../cookbook_pocketflow/heartbeat/heartbeat.graph.yaml) | Implements a long-running polling agent that checks an IMAP inbox on a configurable interval, summarizes new emails, and suggests a prioritized action for each. A WHILE loop drives the monitoring... | nothing external | ☑️ ran |
| `invoice` | [`invoice/invoice.graph.yaml`](../cookbook_pocketflow/invoice/invoice.graph.yaml) | Extracts structured data from PDF invoices and validates the extracted math before committing the result. A deterministic PDF reader converts the invoice to text, the LLM extracts all fields... | llm | ☑️ ran |
| `judge` | [`judge/judge.graph.yaml`](../cookbook_pocketflow/judge/judge.graph.yaml) | Implements the evaluator-optimizer loop: an LLM generates a draft, a second LLM judge scores it against rubric criteria and returns a structured VERDICT, and the workflow retries with the judge's... | llm | ☑️ ran |
| `lead_generation` | [`lead_generation/lead_generation.graph.yaml`](../cookbook_pocketflow/lead_generation/lead_generation.graph.yaml) | Processes a CSV list of sales prospects through a three-stage enrichment and scoring pipeline: web-search-based company research, LLM-based lead qualification scoring, and conditional cold email... | nothing external | ☑️ ran |
| `majority_vote` | [`majority_vote/majority_vote.graph.yaml`](../cookbook_pocketflow/majority_vote/majority_vote.graph.yaml) | Generates three independent answers to a reasoning question in parallel via `CALL PARALLEL`, tallies the answers with a deterministic vote counter, and returns the majority answer — or the first... | llm | ☑️ ran |
| `map_reduce` | [`map_reduce/map_reduce.graph.yaml`](../cookbook_pocketflow/map_reduce/map_reduce.graph.yaml) | Screens a directory of resumes against a set of criteria by mapping an LLM scoring function over each resume in parallel batches of three, then reducing the scored results into a ranked, filtered... | llm, spl | ☑️ ran |
| `mcp` | [`mcp/mcp.graph.yaml`](../cookbook_pocketflow/mcp/mcp.graph.yaml) | Demonstrates dynamic tool discovery and invocation via the Model Context Protocol: the workflow first discovers available tools from an MCP server (or falls back to built-in math tools when no... | llm | ☑️ ran |
| `multi_agent` | [`multi_agent/multi_web_search_agent.graph.yaml`](../cookbook_pocketflow/multi_agent/multi_web_search_agent.graph.yaml) | Implements a two-agent Taboo word-guessing game where a Hinter and a Guesser are distinct LLM personas running inside a single WHILE loop. The Hinter must describe the target word without using it... | nothing external | ☑️ ran |
| `nodejs_upgrade_agent` | [`nodejs_upgrade_agent/nodejs_upgrade_web_search_agent.graph.yaml`](../cookbook_pocketflow/nodejs_upgrade_agent/nodejs_upgrade_web_search_agent.graph.yaml) | Fully automated Node.js major-version upgrade pipeline: | llm, spl | 🔁 lifted |
| `rag` | [`rag/rag.graph.yaml`](../cookbook_pocketflow/rag/rag.graph.yaml) | Implements a classic two-phase retrieval-augmented generation pipeline: an offline indexing phase (chunk → embed → FAISS index) followed by an online query phase (embed query → retrieve nearest... | llm | ☑️ ran |
| `self_healing` | [`self_healing/self_healing.graph.yaml`](../cookbook_pocketflow/self_healing/self_healing.graph.yaml) | Generates a syntactically valid Mermaid diagram from a natural language description, with automatic self-repair on syntax errors. The LLM first produces a Mermaid definition, a deterministic... | llm | ☑️ ran |
| `structured_output` | [`structured_output/structured_output.graph.yaml`](../cookbook_pocketflow/structured_output/structured_output.graph.yaml) | Parses an unstructured plain-text resume into a validated YAML candidate record containing contact info, work history, and matched skills. Three LLM extractions (candidate info, work experience,... | llm | ☑️ ran |
| `supervisor` | [`supervisor/supervisor.graph.yaml`](../cookbook_pocketflow/supervisor/supervisor.graph.yaml) | Implements a two-level agent architecture: an inner ReAct research agent iterates search → reason until it decides it has enough information, then generates a candidate answer; an outer supervisor... | nothing external | ☑️ ran |
| `tao` | [`tao/tao.graph.yaml`](../cookbook_pocketflow/tao/tao.graph.yaml) | A general-purpose ReAct (Reason + Act) agent with a multi-tool dispatch layer: the LLM selects a tool from `search_web`, `run_python`, `calculate`, or `none` at each step, generating a JSON... | llm | 🔁 lifted |
| `text2sql` | [`text2sql/text2sql.graph.yaml`](../cookbook_pocketflow/text2sql/text2sql.graph.yaml) | Converts natural language questions to SQLite queries with automatic self-repair: the LLM generates SQL from the database schema, a deterministic executor runs it against the live database, and if... | llm | ☑️ ran |
| `thinking` | [`thinking/chain_of_thought.graph.yaml`](../cookbook_pocketflow/thinking/chain_of_thought.graph.yaml) | Solves complex reasoning problems through multi-step chain-of-thought where each thought step is validated as YAML before being accepted. An outer loop continues as long as the LLM indicates more... | nothing external | 🔁 lifted |
| `tool_crawler` | [`tool_crawler/tool_crawler.graph.yaml`](../cookbook_pocketflow/tool_crawler/tool_crawler.graph.yaml) | A domain-scoped web crawler: starting from a seed URL, the workflow fetches pages, extracts text and same-domain links, filters out already-visited and already-queued URLs, and adds new links to... | llm | ☑️ ran |
| `tool_database` | [`tool_database/tool_database.graph.yaml`](../cookbook_pocketflow/tool_database/tool_database.graph.yaml) | Demonstrates LLM-driven database interaction: the workflow initializes a SQLite schema, has the LLM generate a batch of task records from a seed topic, inserts each generated task into the... | nothing external | ☑️ ran |
| `tool_embeddings` | [`tool_embeddings/tool_embeddings.graph.yaml`](../cookbook_pocketflow/tool_embeddings/tool_embeddings.graph.yaml) | Calls the OpenAI Embeddings API (`text-embedding-3-small`) from a deterministic tool to convert text into a float vector, handling the API response extraction and error routing cleanly. An... | nothing external | ☑️ ran |
| `tool_pdf_vision` | [`tool_pdf_vision/tool_pdf_vision.graph.yaml`](../cookbook_pocketflow/tool_pdf_vision/tool_pdf_vision.graph.yaml) | A vision-based PDF OCR pipeline: scans a directory for PDF files, converts each page to a 200-DPI PNG image using `pdf2image`, and then uses a multimodal LLM GENERATE call to extract and reformat... | nothing external | ☑️ ran |
| `tool_search` | [`tool_search/tool_search.graph.yaml`](../cookbook_pocketflow/tool_search/tool_search.graph.yaml) | Executes a Google search via the SerpAPI and synthesizes the results into a structured research briefing with a summary, key facts, and follow-up queries. A deterministic `call_serpapi` tool... | llm | ☑️ ran |
| `tracing` | [`tracing/tracing.graph.yaml`](../cookbook_pocketflow/tracing/tracing.graph.yaml) | Demonstrates structured observability for an SPL workflow using Langfuse: a trace decorator generates a distributed `trace_id`, and then a WHILE loop runs each node through three phases (prep →... | nothing external | ☑️ ran |
| `visualization` | [`visualization/visualization.graph.yaml`](../cookbook_pocketflow/visualization/visualization.graph.yaml) | Implements a multi-stage order fulfillment pipeline as three composable sub-workflows chained by `CALL`: payment validation and processing (with retry loop), inventory check and reservation, and... | llm, spl | ☑️ ran |
| `workflow` | [`workflow/article_writer.graph.yaml`](../cookbook_pocketflow/workflow/article_writer.graph.yaml) | Produces a polished, publication-ready article on any topic through a three-phase sequential pipeline: outline generation (YAML), section-by-section drafting (iterated with a WHILE loop), and... | llm | 🔁 lifted |

### Solver recipes (`cookbook_solvers/`): 55 graphs

🔁 55 lifted

| Recipe | Graph | Shows | Needs | Status |
|---|---|---|---|---|
| `auto_planning` | [`auto_planning/auto_planning.graph.yaml`](../cookbook_solvers/auto_planning/auto_planning.graph.yaml) |  | llm | 🔁 lifted |
| `bayesian_opt` | [`bayesian_opt/bayesian_opt.graph.yaml`](../cookbook_solvers/bayesian_opt/bayesian_opt.graph.yaml) |  | llm | 🔁 lifted |
| `code_pytest` | [`code_pytest/code_pytest.graph.yaml`](../cookbook_solvers/code_pytest/code_pytest.graph.yaml) |  | llm, spl | 🔁 lifted |
| `compsci_materials` | [`compsci_materials/materials_crystal.graph.yaml`](../cookbook_solvers/compsci_materials/materials_crystal.graph.yaml) |  | llm | 🔁 lifted |
| `compsci_physics` | [`compsci_physics/physics_conservation.graph.yaml`](../cookbook_solvers/compsci_physics/physics_conservation.graph.yaml) |  | llm | 🔁 lifted |
| `constraint_opt` | [`constraint_opt/constraint_opt.graph.yaml`](../cookbook_solvers/constraint_opt/constraint_opt.graph.yaml) |  | llm | 🔁 lifted |
| `constraint_opt.resource_allocation` | [`constraint_opt/resource_allocation.graph.yaml`](../cookbook_solvers/constraint_opt/resource_allocation.graph.yaml) |  | llm | 🔁 lifted |
| `constraint_opt.staff_scheduling` | [`constraint_opt/staff_scheduling.graph.yaml`](../cookbook_solvers/constraint_opt/staff_scheduling.graph.yaml) |  | llm | 🔁 lifted |
| `constraint_opt.supply_chain` | [`constraint_opt/supply_chain.graph.yaml`](../cookbook_solvers/constraint_opt/supply_chain.graph.yaml) |  | llm | 🔁 lifted |
| `data_eng_text2spl` | [`data_eng_text2spl/text2sql_quality.graph.yaml`](../cookbook_solvers/data_eng_text2spl/text2sql_quality.graph.yaml) |  | llm | 🔁 lifted |
| `data_quality` | [`data_quality/data_quality.graph.yaml`](../cookbook_solvers/data_quality/data_quality.graph.yaml) |  | llm | 🔁 lifted |
| `demand_forecast` | [`demand_forecast/demand_forecast.graph.yaml`](../cookbook_solvers/demand_forecast/demand_forecast.graph.yaml) |  | llm | 🔁 lifted |
| `financial_calc_verifier` | [`financial_calc_verifier/financial_calc_verifier.graph.yaml`](../cookbook_solvers/financial_calc_verifier/financial_calc_verifier.graph.yaml) |  | llm | 🔁 lifted |
| `gambit_3player` | [`gambit_3player/gambit_3player.graph.yaml`](../cookbook_solvers/gambit_3player/gambit_3player.graph.yaml) |  | llm | 🔁 lifted |
| `global_minlp` | [`global_minlp/global_minlp.graph.yaml`](../cookbook_solvers/global_minlp/global_minlp.graph.yaml) |  | llm | 🔁 lifted |
| `graph_reasoning` | [`graph_reasoning/graph_reasoning.graph.yaml`](../cookbook_solvers/graph_reasoning/graph_reasoning.graph.yaml) |  | llm | 🔁 lifted |
| `hard_milp_scip` | [`hard_milp_scip/hard_milp_scip.graph.yaml`](../cookbook_solvers/hard_milp_scip/hard_milp_scip.graph.yaml) |  | llm | 🔁 lifted |
| `insurance_policy_z3` | [`insurance_policy_z3/insurance_policy_z3.graph.yaml`](../cookbook_solvers/insurance_policy_z3/insurance_policy_z3.graph.yaml) |  | llm | 🔁 lifted |
| `job_shop` | [`job_shop/job_shop.graph.yaml`](../cookbook_solvers/job_shop/job_shop.graph.yaml) |  | llm | 🔁 lifted |
| `lean_proof` | [`lean_proof/lean_proof.graph.yaml`](../cookbook_solvers/lean_proof/lean_proof.graph.yaml) |  | llm | 🔁 lifted |
| `logic_puzzle_solver` | [`logic_puzzle_solver/logic_puzzle_solver.graph.yaml`](../cookbook_solvers/logic_puzzle_solver/logic_puzzle_solver.graph.yaml) |  | llm | 🔁 lifted |
| `minizinc_cp` | [`minizinc_cp/minizinc_cp.graph.yaml`](../cookbook_solvers/minizinc_cp/minizinc_cp.graph.yaml) |  | llm | 🔁 lifted |
| `nash_game_theory` | [`nash_game_theory/nash_game_theory.graph.yaml`](../cookbook_solvers/nash_game_theory/nash_game_theory.graph.yaml) |  | llm | 🔁 lifted |
| `neurosymbolic` | [`neurosymbolic/symbolic_math.graph.yaml`](../cookbook_solvers/neurosymbolic/symbolic_math.graph.yaml) |  | llm, spl | 🔁 lifted |
| `openspiel_cfr` | [`openspiel_cfr/openspiel_cfr.graph.yaml`](../cookbook_solvers/openspiel_cfr/openspiel_cfr.graph.yaml) |  | llm | 🔁 lifted |
| `optuna_blackbox` | [`optuna_blackbox/optuna_blackbox.graph.yaml`](../cookbook_solvers/optuna_blackbox/optuna_blackbox.graph.yaml) |  | llm | 🔁 lifted |
| `pandera_schema` | [`pandera_schema/pandera_schema.graph.yaml`](../cookbook_solvers/pandera_schema/pandera_schema.graph.yaml) |  | llm | 🔁 lifted |
| `pii_compliance.compliance_check` | [`pii_compliance/compliance_check.graph.yaml`](../cookbook_solvers/pii_compliance/compliance_check.graph.yaml) |  | nothing external | 🔁 lifted |
| `pii_compliance` | [`pii_compliance/pii_compliance.graph.yaml`](../cookbook_solvers/pii_compliance/pii_compliance.graph.yaml) |  | llm | 🔁 lifted |
| `platypus_moea` | [`platypus_moea/platypus_moea.graph.yaml`](../cookbook_solvers/platypus_moea/platypus_moea.graph.yaml) |  | llm | 🔁 lifted |
| `portfolio_opt.portfolio_comparison` | [`portfolio_opt/portfolio_comparison.graph.yaml`](../cookbook_solvers/portfolio_opt/portfolio_comparison.graph.yaml) |  | llm | 🔁 lifted |
| `portfolio_opt.portfolio_optimization` | [`portfolio_opt/portfolio_optimization.graph.yaml`](../cookbook_solvers/portfolio_opt/portfolio_optimization.graph.yaml) |  | llm | 🔁 lifted |
| `production_sustainability` | [`production_sustainability/production_sustainability.graph.yaml`](../cookbook_solvers/production_sustainability/production_sustainability.graph.yaml) |  | llm | 🔁 lifted |
| `progressive_hedging` | [`progressive_hedging/progressive_hedging.graph.yaml`](../cookbook_solvers/progressive_hedging/progressive_hedging.graph.yaml) |  | llm | 🔁 lifted |
| `prolog_inference` | [`prolog_inference/prolog_inference.graph.yaml`](../cookbook_solvers/prolog_inference/prolog_inference.graph.yaml) |  | llm | 🔁 lifted |
| `property_based_code_verify` | [`property_based_code_verify/property_based_code_verify.graph.yaml`](../cookbook_solvers/property_based_code_verify/property_based_code_verify.graph.yaml) |  | llm | 🔁 lifted |
| `pyomo_stochastic` | [`pyomo_stochastic/pyomo_stochastic.graph.yaml`](../cookbook_solvers/pyomo_stochastic/pyomo_stochastic.graph.yaml) |  | llm | 🔁 lifted |
| `robust_milp` | [`robust_milp/robust_milp.graph.yaml`](../cookbook_solvers/robust_milp/robust_milp.graph.yaml) |  | llm | 🔁 lifted |
| `route_optimization` | [`route_optimization/route_optimization.graph.yaml`](../cookbook_solvers/route_optimization/route_optimization.graph.yaml) |  | llm | 🔁 lifted |
| `sage_math` | [`sage_math/basic_sagemath.graph.yaml`](../cookbook_solvers/sage_math/basic_sagemath.graph.yaml) |  | llm, sagemath | 🔁 lifted |
| `scipy_nonlinear` | [`scipy_nonlinear/scipy_nonlinear.graph.yaml`](../cookbook_solvers/scipy_nonlinear/scipy_nonlinear.graph.yaml) |  | llm | 🔁 lifted |
| `shapely_geo` | [`shapely_geo/shapely_geo.graph.yaml`](../cookbook_solvers/shapely_geo/shapely_geo.graph.yaml) |  | llm | 🔁 lifted |
| `simpy_des` | [`simpy_des/simpy_des.graph.yaml`](../cookbook_solvers/simpy_des/simpy_des.graph.yaml) |  | llm | 🔁 lifted |
| `sql_verifier` | [`sql_verifier/sql_verifier.graph.yaml`](../cookbook_solvers/sql_verifier/sql_verifier.graph.yaml) |  | llm | 🔁 lifted |
| `stackelberg_game` | [`stackelberg_game/stackelberg_game.graph.yaml`](../cookbook_solvers/stackelberg_game/stackelberg_game.graph.yaml) |  | llm | 🔁 lifted |
| `supply_sourcing` | [`supply_sourcing/supply_sourcing.graph.yaml`](../cookbook_solvers/supply_sourcing/supply_sourcing.graph.yaml) |  | llm | 🔁 lifted |
| `symbolic_math.hello_symbolic_math` | [`symbolic_math/hello_symbolic_math.graph.yaml`](../cookbook_solvers/symbolic_math/hello_symbolic_math.graph.yaml) |  | llm | 🔁 lifted |
| `symbolic_math.sympy_llm` | [`symbolic_math/sympy_llm.graph.yaml`](../cookbook_solvers/symbolic_math/sympy_llm.graph.yaml) |  | llm, spl | 🔁 lifted |
| `symbolic_math.sympy_llm_v2` | [`symbolic_math/sympy_llm_v2.graph.yaml`](../cookbook_solvers/symbolic_math/sympy_llm_v2.graph.yaml) |  | llm, spl | 🔁 lifted |
| `symbolic_math.sympy_math_multi_step` | [`symbolic_math/sympy_math_multi_step.graph.yaml`](../cookbook_solvers/symbolic_math/sympy_math_multi_step.graph.yaml) |  | llm, spl | 🔁 lifted |
| `synthetic_problems` | [`synthetic_problems/synthetic_problem_gen.graph.yaml`](../cookbook_solvers/synthetic_problems/synthetic_problem_gen.graph.yaml) |  | llm | 🔁 lifted |
| `trading_rule_z3` | [`trading_rule_z3/trading_rule_z3.graph.yaml`](../cookbook_solvers/trading_rule_z3/trading_rule_z3.graph.yaml) |  | llm | 🔁 lifted |
| `unit_dimensional_check` | [`unit_dimensional_check/unit_dimensional_check.graph.yaml`](../cookbook_solvers/unit_dimensional_check/unit_dimensional_check.graph.yaml) |  | llm | 🔁 lifted |
| `workforce_3obj` | [`workforce_3obj/workforce_3obj.graph.yaml`](../cookbook_solvers/workforce_3obj/workforce_3obj.graph.yaml) |  | llm | 🔁 lifted |
| `z3_compliance` | [`z3_compliance/z3_compliance.graph.yaml`](../cookbook_solvers/z3_compliance/z3_compliance.graph.yaml) |  | llm | 🔁 lifted |

<!-- catalog:end -->
