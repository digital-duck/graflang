# 019 — Agentic RAG  *(migrated from PocketFlow)*

> **GraphLang port.** Lifted from SPL.py's `cookbook-pocketflow/019_agentic_rag` with `spl3 util spl2graph` (AST-direct, no model involved); source `agentic_rag.spl` is kept beside the graph. Passes `graf validate` (`graf` conda env). Ran with `graf run --llm claude_cli:claude-sonnet-5-5` on 2026-11-03 (after the fixes listed in `cookbook/cookbook_catalog.yaml`); output not reviewed. Commands below use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`. Running needs SPL.py importable (`pip install 'graflang[spl]'`).

**Source:** [pocketflow-agentic-rag](https://github.com/The-Pocket/PocketFlow/tree/main/cookbook/pocketflow-agentic-rag)
**Difficulty:** ★☆☆
**Category:** retrieval

## What it does

Implements adaptive retrieval: rather than fetching a fixed set of chunks upfront, the LLM decides at each step whether it has enough information to answer or should retrieve one more document. On each iteration, it selects the next document to retrieve, fetches and integrates it, then re-evaluates sufficiency. The loop exits when either the LLM determines the context is sufficient or the document budget is exhausted.

## Real-world use cases

- **Legal and compliance research**: Retrieve only the statutes and precedents relevant to a specific question, stopping when the answer is unambiguous rather than dumping all potentially related documents
- **Medical literature Q&A**: Progressively retrieve clinical papers until the evidence base is sufficient to answer a specific therapeutic question — avoiding irrelevant or contradictory sources
- **Technical troubleshooting agents**: Fetch diagnostic documents one at a time in order of relevance until the root cause is identified
- **Financial research**: Adaptively retrieve earnings reports, analyst notes, and regulatory filings until the model has enough context to make a well-supported assessment

## Key SPL constructs

- `CREATE TOOL_API retrieve_document(store_path, doc_id)` — fetches a document from a JSON document store by ID
- `CREATE TOOL_API list_documents(store_path)` — returns the full document index for the LLM to select from
- `WHILE @sufficient = "false" AND @i < @max_iterations DO` — adaptive retrieval loop
- `GENERATE assess_sufficiency(@question, @context)` — LLM decides "true"/"false" on whether current context is enough
- `GENERATE select_next_document(@question, @context, @docs_list)` — LLM selects the most relevant uncollected document

## Workflow I/O

**Inputs:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `@question` | TEXT | _(required)_ | The question to answer from the document store |
| `@store_path` | TEXT | `"documents.json"` | Path to the JSON document store |
| `@max_iterations` | INTEGER | 10 | Maximum number of retrieval steps |

**Output:** `@answer TEXT` — the LLM's final answer grounded in the retrieved documents

## Run

```bash
conda activate graf
cd ~/projects/digital-duck/graflang

graf run cookbook_pocketflow/agentic_rag/agentic_rag.graph.yaml \
    --llm claude_cli:claude-sonnet-4-6
```

## Extend it

- Replace the JSON document store with a vector database by implementing `retrieve_document` as a semantic similarity search
- Add `CALL write_file` to log which documents were selected at each step for retrieval quality auditing
- Combine with `032_deep_research` for multi-source research: use agentic RAG over a local corpus alongside web search
- Use `--adapter momagrid` to distribute multiple parallel `agentic_rag` calls across different topic branches
