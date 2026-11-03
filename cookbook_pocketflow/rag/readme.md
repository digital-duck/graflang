# 005 — RAG  *(migrated from PocketFlow)*

> **GraphLang port.** Lifted from SPL.py's `cookbook-pocketflow/005_rag` with `spl3 util spl2graph` (AST-direct, no model involved); source `rag.spl` is kept beside the graph. Passes `graf validate` (`graf` conda env). Ran with `graf run --llm claude_cli:claude-sonnet-5-5` on 2026-11-03 (after the fixes listed in `cookbook/cookbook_catalog.yaml`); output not reviewed. Commands below use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`. Running needs SPL.py importable (`pip install 'graflang[spl]'`).

**Source:** [pocketflow-rag](https://github.com/The-Pocket/PocketFlow/tree/main/cookbook/pocketflow-rag)
**Difficulty:** ☆☆☆
**Category:** retrieval

## What it does

Implements a classic two-phase retrieval-augmented generation pipeline: an offline indexing phase (chunk → embed → FAISS index) followed by an online query phase (embed query → retrieve nearest chunk → generate answer). The entire pipeline is expressed as a single linear SPL workflow — a straight `CALL` chain with one `GENERATE` at the end — demonstrating how tool-heavy pipelines with no branching map cleanly to SPL's DODA model.

## Real-world use cases

- **Enterprise knowledge bases**: Index internal documentation, policies, and runbooks so employees can ask natural-language questions and receive grounded answers
- **Legal document review**: Index case files and contracts, then retrieve and summarize relevant passages in response to attorney queries
- **Customer support automation**: Index product documentation and FAQs, retrieve the most relevant content, and generate a grounded support response
- **Research assistants**: Index academic papers and technical reports, then generate synthesis answers over retrieved context

## Key SPL constructs

- `CALL chunk_documents(@documents)` — splits documents into indexable text chunks
- `CALL embed_documents(@texts)` — generates vector embeddings for each chunk
- `CALL create_faiss_index(@embeddings)` — builds an in-memory FAISS similarity index
- `CALL embed_query(@query)` — embeds the query for vector search
- `CALL retrieve_document(@index, @query_embedding, @texts)` — top-1 retrieval
- `GENERATE generate_answer(@query, @retrieved_document)` — augmented generation grounded in retrieved context
- `EVALUATE @output_path WHEN contains(".")` — optional file write if output path is specified

## Workflow I/O

**Inputs:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `@documents` | LIST | _(required)_ | List of document file paths to index |
| `@query` | TEXT | _(required)_ | Natural-language question to answer |
| `@output_path` | TEXT | `""` | Optional path to write the answer; skipped if blank |

**Output:** `@generated_answer TEXT` — LLM-generated answer grounded in the retrieved document chunk

## Run

```bash
conda activate graf
cd ~/projects/digital-duck/graflang

graf run cookbook_pocketflow/rag/rag.graph.yaml \
    --llm claude_cli:claude-sonnet-4-6 \
    --param 'documents=["cookbook_pocketflow/rag/data/doc1.txt"]' \
    --param "query=What is FAISS for?"
```

## Extend it

- Replace FAISS with a persistent vector store tool to support a pre-built offline index
- Add `CALL PARALLEL` to retrieve top-k chunks and generate multiple candidate answers, then synthesize
- Wrap the query phase in a `WHILE` loop with an agentic sufficiency check (see `019_agentic_rag`) to handle multi-hop questions
- Swap `--llm` to compare answer quality across models on the same retrieved context
