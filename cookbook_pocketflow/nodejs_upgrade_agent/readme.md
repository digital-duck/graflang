# 042 — Node.js Upgrade Agent  *(original SPL recipe)*

> **GraphLang port.** Lifted from SPL.py's `cookbook-pocketflow/042_nodejs_upgrade_agent` with `spl3 util spl2graph` (AST-direct, no model involved); source `nodejs_upgrade_web_search_agent.spl` is kept beside the graph. Passes `graf validate` (`graf` conda env). **Not yet run with `graf run`.** Commands below use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`. Running needs SPL.py importable (`pip install 'graflang[spl]'`).
> Caveats: `tools.spl` sits next to the graph; the SPL procedures it holds are needed at run time.

**Difficulty:** ★★★ Advanced
**SPL patterns:** pre-analysis → sequential file transforms → nested self-healing WHILE loop → report

Inspired by a production upgrade agent built on PocketFlow + Claude Code CLI.

## What it does

Fully automated Node.js major-version upgrade pipeline:

```
Phase 1 — Pre-upgrade analysis (deterministic)
    scan_source_files  →  list_outdated  →  analyze_breaking_changes (LLM)

Phase 2 — File transforms  (sequential; Momagrid-distributable)
    for each .js/.ts file:
        read → transform_file (LLM) → backup → write

Phase 3 — npm self-healing loop  (WHILE + EVALUATE + fix LLM, max 5 attempts)
    npm install → npm run build → npm test
        on error: fix_npm_error (LLM) → apply fix → retry

Phase 4 — Report
    generate_report (LLM) → write upgrade_report.md
```

## Key design decisions

- **Deterministic scope first** — `scan_source_files` + `list_outdated` pin the exact
  file list and package delta before any LLM call. No hallucinated scope.
- **Backup before write** — every modified file gets a `.bak` copy via `backup_file`.
- **Capped npm output** — `run_npm` trims stdout/stderr to 4000/2000 chars to
  prevent token explosion in the self-healing loop.
- **PROCEDURE decomposition** — `upgrade_file` and `npm_validate_and_heal` are
  reusable sub-procedures, not inlined in the main workflow.

## Run

```bash
conda activate graf
cd ~/projects/digital-duck/graflang

graf run cookbook_pocketflow/nodejs_upgrade_agent/nodejs_upgrade_web_search_agent.graph.yaml \
    --llm claude_cli:claude-sonnet-4-6 \
    --param project_dir=/path/to/your/node/project \
    --param target_node=20 \
    --param report_path=upgrade_report.md
```

## Tools (tools.spl)

| Tool | Purpose |
|------|---------|
| `scan_source_files` | Walk project tree, return JSON list of .js/.ts/.jsx/.tsx files |
| `read_package_json` | Read and return package.json content |
| `list_outdated` | Run `npm outdated --json`, return structured JSON |
| `run_npm` | Run any `npm <cmd>`, return `{exit_code, stdout, stderr, ok}` |
| `backup_file` | Copy file to `.bak` before modification |
| `get_item` | Index into a JSON list |
| `list_count` | Length of a JSON list |
| `npm_result_ok` | Extract `ok` boolean from run_npm result |
| `npm_errors` | Extract error text from run_npm result |
