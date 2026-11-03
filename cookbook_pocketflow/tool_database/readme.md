# 059 — Tool Database (SQLite Task Manager)  *(migrated from PocketFlow)*

> **GraphLang port.** Lifted from SPL.py's `cookbook-pocketflow/059_tool_database` with `spl3 util spl2graph` (AST-direct, no model involved); source `tool_database.spl` is kept beside the graph. Passes `graf validate` (`graf` conda env). **Not yet run with `graf run`.** Commands below use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`. Running needs SPL.py importable (`pip install 'graflang[spl]'`).

**Source:** [pocketflow-tool-database](https://github.com/The-Pocket/PocketFlow/tree/main/cookbook/pocketflow-tool-database)
**Difficulty:** —
**Category:** tool-use

## What it does

Demonstrates LLM-driven database interaction: the workflow initializes a SQLite schema, has the LLM generate a batch of task records from a seed topic, inserts each generated task into the database, then reads back and presents all stored tasks. This pattern separates the LLM's creative generation (what tasks to create) from the deterministic persistence layer (SQLite), keeping data integrity in the tool layer while using the LLM for content.

## Real-world use cases

- **AI task planners**: Have an LLM decompose a project into tasks, persist them to SQLite, and retrieve them for scheduling or assignment
- **Automated backlog generators**: Generate a sprint backlog from a feature description and store it in a database for team review and prioritization
- **Knowledge base population**: Use an LLM to generate structured records (FAQs, concepts, definitions) and insert them into a queryable database
- **Test data generation**: Generate realistic sample records for a database schema using an LLM, enabling realistic integration testing without manual data entry

## Key SPL constructs

- `CREATE TOOL_API init_db_schema(db_path)` — creates the `tasks` table with `id`, `title`, `description`, `created_at` columns via SQLite `IF NOT EXISTS`
- `CREATE TOOL_API insert_task(db_path, title, description)` — parameterized INSERT returning the new row ID
- `CREATE TOOL_API retrieve_all_tasks(db_path)` — SELECT all tasks ordered by ID, returns JSON array
- LLM GENERATE step — produces a structured list of task titles and descriptions for insertion
- Iteration over generated tasks to call `insert_task` for each record

## Workflow I/O

**Inputs:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `@db_path` | TEXT | `"tasks.db"` | Path to the SQLite database file |
| `@topic` | TEXT | _(required)_ | Topic or project description for task generation |
| `@num_tasks` | INTEGER | 5 | Number of tasks to generate and insert |

**Output:** `@tasks_json TEXT` — JSON array of all tasks retrieved from the database after insertion

## Run

```bash
conda activate graf
cd ~/projects/digital-duck/graflang

graf run cookbook_pocketflow/tool_database/tool_database.graph.yaml \
    --llm claude_cli:claude-sonnet-4-6
```

## Extend it

- Chain with `033_text2sql` to allow natural language queries over the populated task database
- Add a `GENERATE prioritize_tasks(@tasks_json)` step to have the LLM rank tasks by importance before displaying them
- Add `update_task` and `delete_task` tools to build a full CRUD task manager driven by LLM commands
- Replace SQLite with PostgreSQL tools to scale the pattern to a production database
