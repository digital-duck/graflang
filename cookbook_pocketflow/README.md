# PocketFlow recipes

SPL.py's `cookbook-pocketflow` recipes lifted to GraphLang with `spl3 util spl2graph` (AST-direct, no model involved). Run one with `graf run cookbook_pocketflow/NAME/GRAPH.graph.yaml --param key=value`. Each recipe folder keeps its source `.spl` (including `tools.spl` helpers that graphs import or call via `procedure_ref`, so SPL.py must be importable: `pip install 'graflang[spl]'`), its readme (`readme.md`: the original text, with the header and Run section rewritten for `graf run`; the "Key SPL constructs" lists still describe the SPL source) and any `data/` it reads.

All 42 graphs pass `graf validate` in the `graf` conda env. On 2026-11-03 they were run with `graf run --llm claude_cli:claude-sonnet-5-5` (via `cookbook/run_all.py`): 36 complete (outputs not reviewed; 9 of them after fixes), 6 do not. The per-recipe state and notes are in `../cookbook/cookbook_catalog.yaml`.

Not completed: `chat` and `cli_hitl` wait for keyboard input and are not run in batch; `nodejs_upgrade_agent` needs `--param project_dir=<a Node project>`; `tao` and `thinking` stop because the model's safeguards flag their reasoning-extraction prompts.

Fixed this session: tool code that did not compile (SQL-style `''` quoting in the SPL source, re-lifted: `agentic_rag`, `batch_node`, `lead_generation`, `self_healing`); `str()` around int operands in string expressions (`communication`, `heartbeat`); `deep_research`'s unfed EVALUATE input; `rag` now reads the files it is given; `batch_node`'s defaults now match its data.

| Recipe | From | Graphs |
|---|---|---|
| [`chat`](chat) | `001_chat` | `chat` |
| [`structured_output`](structured_output) | `002_structured_output` | `structured_output` |
| [`workflow`](workflow) | `003_workflow` | `article_writer` |
| [`agent`](agent) | `004_agent` | `web_search_agent` |
| [`rag`](rag) | `005_rag` | `rag` |
| [`map_reduce`](map_reduce) | `006_map_reduce` | `map_reduce` |
| [`chat_guardrail`](chat_guardrail) | `008_chat_guardrail` | `chat_guardrail` |
| [`multi_agent`](multi_agent) | `010_multi_agent` | `multi_web_search_agent` |
| [`supervisor`](supervisor) | `011_supervisor` | `supervisor` |
| [`batch_node`](batch_node) | `012_batch_node` | `batch_node` |
| [`batch_flow`](batch_flow) | `013_batch_flow` | `batch_text_transformer` |
| [`thinking`](thinking) | `014_thinking` | `chain_of_thought` |
| [`chat_memory`](chat_memory) | `015_chat_memory` | `chat_memory` |
| [`mcp`](mcp) | `016_mcp` | `mcp` |
| [`judge`](judge) | `017_judge` | `judge` |
| [`debate`](debate) | `018_debate` | `debate` |
| [`agentic_rag`](agentic_rag) | `019_agentic_rag` | `agentic_rag` |
| [`heartbeat`](heartbeat) | `020_heartbeat` | `heartbeat` |
| [`self_healing`](self_healing) | `021_self_healing` | `self_healing` |
| [`lead_generation`](lead_generation) | `030_lead_generation` | `lead_generation` |
| [`invoice`](invoice) | `031_invoice` | `invoice` |
| [`deep_research`](deep_research) | `032_deep_research` | `deep_research` |
| [`text2sql`](text2sql) | `033_text2sql` | `text2sql` |
| [`communication`](communication) | `034_communication` | `communication` |
| [`coding_agent`](coding_agent) | `040_coding_agent` | `coding_web_search_agent` |
| [`agent_skills`](agent_skills) | `041_agent_skills` | `agent_skills` |
| [`nodejs_upgrade_agent`](nodejs_upgrade_agent) | `042_nodejs_upgrade_agent` | `nodejs_upgrade_web_search_agent` |
| [`a2a`](a2a) | `050_a2a` | `a2a` |
| [`async_basic`](async_basic) | `051_async_basic` | `async_basic` |
| [`batch`](batch) | `052_batch` | `batch_translator` |
| [`cli_hitl`](cli_hitl) | `053_cli_hitl` | `cli_hitl` |
| [`code_generator`](code_generator) | `054_code_generator` | `code_generator` |
| [`flow`](flow) | `055_flow` | `text_transformer` |
| [`majority_vote`](majority_vote) | `056_majority_vote` | `majority_vote` |
| [`tao`](tao) | `057_tao` | `tao` |
| [`tool_crawler`](tool_crawler) | `058_tool_crawler` | `tool_crawler` |
| [`tool_database`](tool_database) | `059_tool_database` | `tool_database` |
| [`tool_embeddings`](tool_embeddings) | `060_tool_embeddings` | `tool_embeddings` |
| [`tool_pdf_vision`](tool_pdf_vision) | `061_tool_pdf_vision` | `tool_pdf_vision` |
| [`tool_search`](tool_search) | `062_tool_search` | `tool_search` |
| [`tracing`](tracing) | `063_tracing` | `tracing` |
| [`visualization`](visualization) | `064_visualization` | `visualization` |
