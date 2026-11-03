# 051 — Async Basic (Recipe Recommender)  *(migrated from PocketFlow)*

> **GraphLang port.** Lifted from SPL.py's `cookbook-pocketflow/051_async_basic` with `spl3 util spl2graph` (AST-direct, no model involved); source `async_basic.spl` is kept beside the graph. Passes `graf validate` (`graf` conda env). **Not yet run with `graf run`.** Commands below use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`. Running needs SPL.py importable (`pip install 'graflang[spl]'`).

**Source:** [pocketflow-async-basic](https://github.com/The-Pocket/PocketFlow/tree/main/cookbook/pocketflow-async-basic)
**Difficulty:** —
**Category:** basics

## What it does

A recipe recommender that demonstrates SPL's async-capable pipeline: it fetches candidate recipes from an external API, asks the LLM to select the best match for available ingredients, presents a formatted suggestion, runs an LLM quality-approval gate, and either confirms the recommendation or signals rejection. The workflow models async I/O (external API call) followed by a chain of sequential LLM steps that produce a final user-facing recommendation.

## Real-world use cases

- **Meal planning assistants**: Given a pantry inventory, recommend the recipe that maximizes ingredient use and explain why it's a good fit
- **Product recommendation engines**: Fetch candidate products from a catalog API, have an LLM select the best match for a stated need, and present a personalized recommendation
- **Content curation**: Pull candidate articles, videos, or courses from an external API and select the one best suited to a learner's stated goal
- **Shopping assistants**: Fetch matching items from a retailer API based on a user's description and recommend the most suitable option with rationale

## Key SPL constructs

- `CREATE TOOL_API fetch_candidate_recipes(ingredients, api_base)` — HTTP GET to a recipe search API, returns top-N candidates as JSON
- `CREATE FUNCTION select_best_recipe(ingredients, candidates)` — LLM selects the single best recipe and summarizes it
- `CREATE FUNCTION present_suggestion(ingredients, recipe)` — writes a friendly, formatted recommendation message
- `CREATE FUNCTION evaluate_user_approval(ingredients, suggestion)` — LLM quality gate: returns "approved" or "rejected"
- `CREATE FUNCTION confirm_recipe_recommendation(suggestion)` — writes a warm confirmation message for approved suggestions
- Sequential GENERATE chain — no branching loop; demonstrates the async-to-sequential handoff pattern

## Workflow I/O

**Inputs:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `@ingredients` | TEXT | `"chicken, garlic, lemon, fresh herbs"` | Comma-separated list of available ingredients |
| `@api_base` | TEXT | _(required)_ | Base URL of the recipe search API endpoint |

**Output:** `@confirmation TEXT` — the final confirmed recommendation message, or a rejection notice

## Run

```bash
conda activate graf
cd ~/projects/digital-duck/graflang

graf run cookbook_pocketflow/async_basic/async_basic.graph.yaml \
    --llm claude_cli:claude-sonnet-4-6
```

## Extend it

- Wrap the fetch + select + approve chain in a WHILE loop so the workflow retries with different API parameters if the first suggestion is rejected
- Use `CALL PARALLEL` to query multiple recipe APIs simultaneously and merge candidates before selection
- Replace `fetch_candidate_recipes` with a vector similarity search over a local recipe embedding store for offline use
- Add `--adapter momagrid` to run the fetch and LLM selection steps on separate Momagrid workers
