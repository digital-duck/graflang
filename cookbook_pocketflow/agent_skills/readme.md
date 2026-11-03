# 041 — Agent Skills (Skill Dispatcher)  *(migrated from PocketFlow)*

> **GraphLang port.** Lifted from SPL.py's `cookbook-pocketflow/041_agent_skills` with `spl3 util spl2graph` (AST-direct, no model involved); source `agent_skills.spl` is kept beside the graph. Passes `graf validate` (`graf` conda env). **Not yet run with `graf run`.** Commands below use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`. Running needs SPL.py importable (`pip install 'graflang[spl]'`).

**Source:** [pocketflow-agent-skills](https://github.com/The-Pocket/PocketFlow/tree/main/cookbook/pocketflow-agent-skills)
**Difficulty:** ★★★
**Category:** agent

## What it does

A skill-routing agent that dynamically selects the most appropriate prompt template from a directory of Markdown skill files before answering a task. The workflow scans the skills directory, extracts keywords from each skill file, asks the LLM whether any skill matches the task (with a NO_MATCH fallback to a default skill), selects the single best-matching skill file, and then applies the skill template as the final generation prompt. This separates capability discovery from capability execution.

## Real-world use cases

- **Multi-persona assistants**: Maintain a library of role-specific prompt templates (analyst, lawyer, doctor, teacher) and route incoming tasks to the right persona automatically
- **Enterprise knowledge bases**: Build a skills directory from internal SOPs, policy documents, or brand guidelines, then dispatch tasks to the right template without hardcoding routing rules
- **Dynamic agent customization**: Allow teams to add new capabilities by dropping a Markdown skill file into a directory — no code changes required
- **Domain-specific chatbots**: Route customer questions to specialist prompt templates (billing, technical support, returns) based on keyword and semantic matching

## Key SPL constructs

- `CREATE TOOL_API scan_skills_dir(skills_dir)` — globs all `*.md` files in the skills directory
- `CREATE TOOL_API read_skill_files(file_list)` — reads all skill files and returns their contents with filename headers
- `CREATE FUNCTION extract_keywords(skill_files_content)` — produces a `filename: keyword1, keyword2, ...` keyword map per skill file
- `CREATE FUNCTION match_task_to_skills(task, keywords_map)` — returns "MATCH" or "NO_MATCH"
- `CREATE FUNCTION select_best_skill(task, skill_files_content)` — returns the filename of the best-matching skill
- `EVALUATE @match_result WHEN contains("NO_MATCH")` — routes to default skill vs. LLM skill selection
- `CALL replace(@skill_template, "{task}", @task)` — injects the user task into the skill template before generation

## Workflow I/O

**Inputs:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `@task` | TEXT | _(required)_ | The task or question to route and answer |
| `@skills_dir` | TEXT | `"./skills"` | Directory containing Markdown skill files |
| `@default_skill` | TEXT | `"default.md"` | Fallback skill file when no skill matches the task |

**Output:** `@response TEXT` — the LLM's response generated using the selected skill template

## Run

```bash
conda activate graf
cd ~/projects/digital-duck/graflang

graf run cookbook_pocketflow/agent_skills/agent_skills.graph.yaml \
    --llm claude_cli:claude-sonnet-4-6
```

## Extend it

- Replace keyword matching with embedding-based semantic search over skill files for higher-quality routing on diverse tasks
- Add a `WHILE` retry loop that tries the second-best skill if the first generates an unsatisfactory response (judged by `017_judge`)
- Use the skill dispatcher as a routing layer in front of `032_deep_research`, `033_text2sql`, or `040_coding_agent` — each as a skill file
- Add a skill registration step that auto-generates a skill Markdown file from a natural language capability description using `spl3 text2spl`
