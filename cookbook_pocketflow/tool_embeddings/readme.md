# 060 — Tool Embeddings  *(migrated from PocketFlow)*

> **GraphLang port.** Lifted from SPL.py's `cookbook-pocketflow/060_tool_embeddings` with `spl3 util spl2graph` (AST-direct, no model involved); source `tool_embeddings.spl` is kept beside the graph. Passes `graf validate` (`graf` conda env). **Not yet run with `graf run`.** Commands below use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`. Running needs SPL.py importable (`pip install 'graflang[spl]'`).

**Source:** [pocketflow-tool-embeddings](https://github.com/The-Pocket/PocketFlow/tree/main/cookbook/pocketflow-tool-embeddings)
**Difficulty:** —
**Category:** tool-use

## What it does

Calls the OpenAI Embeddings API (`text-embedding-3-small`) from a deterministic tool to convert text into a float vector, handling the API response extraction and error routing cleanly. An `EVALUATE` branch separates the success path (return the embedding JSON array) from the error path (propagate the error message). This is the canonical pattern for integrating any external embedding API into an SPL workflow as a tool call rather than a GENERATE call.

## Real-world use cases

- **Semantic search pipelines**: Embed query and document texts as the retrieval step in a RAG pipeline, then compute cosine similarity in a downstream tool
- **Recommendation systems**: Embed user profiles and item descriptions to compute similarity scores for personalized recommendations
- **Duplicate detection**: Embed pairs of documents and compute similarity to identify near-duplicate content in a corpus
- **Clustering and classification**: Pre-compute embeddings for a document set as input to a downstream clustering or classification tool

## Key SPL constructs

- `CREATE TOOL_API call_openai_embeddings(text, api_key)` — HTTP POST to OpenAI Embeddings API with `Authorization: Bearer` header; falls back to `OPENAI_API_KEY` env var if no key param is provided
- `CREATE TOOL_API extract_embedding(response_json)` — extracts the float array from `data[0].embedding` in the API response
- `EVALUATE @api_response WHEN contains("error:")` — routes error responses directly to output without attempting extraction
- Minimal sequential pipeline: fetch → check → extract

## Workflow I/O

**Inputs:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `@text` | TEXT | _(required)_ | Text to embed |
| `@api_key` | TEXT | `""` | OpenAI API key; uses `OPENAI_API_KEY` env var if empty |

**Output:** `@result TEXT` — JSON array of floats (the embedding vector) or an error string

## Run

```bash
conda activate graf
cd ~/projects/digital-duck/graflang

export OPENAI_API_KEY=sk-...
graf run cookbook_pocketflow/tool_embeddings/tool_embeddings.graph.yaml \
    --llm claude_cli:claude-sonnet-4-6
```

## Extend it

- Chain with `015_chat_memory` to replace the TF-IDF approximation with real OpenAI embeddings for higher-quality semantic archive search
- Replace `call_openai_embeddings` with an Ollama embedding tool to run fully locally without an API key
- Add a `cosine_similarity(vec_a, vec_b)` tool and feed this workflow's output into a pairwise similarity computation
- Build a batch embedder by wrapping this workflow in a WHILE loop and writing each vector to a JSONL file for later indexing
