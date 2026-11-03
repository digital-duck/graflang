# 020 — Heartbeat (Email Monitor)  *(migrated from PocketFlow)*

> **GraphLang port.** Lifted from SPL.py's `cookbook-pocketflow/020_heartbeat` with `spl3 util spl2graph` (AST-direct, no model involved); source `heartbeat.spl` is kept beside the graph. Passes `graf validate` (`graf` conda env). Ran with `graf run --llm claude_cli:claude-sonnet-5-5` on 2026-11-03 (after the fixes listed in `cookbook/cookbook_catalog.yaml`); output not reviewed. Commands below use `graf run`; `--llm ADAPTER[:MODEL]` and `--param key=value` work as in `spl3 run`. Running needs SPL.py importable (`pip install 'graflang[spl]'`).

**Source:** [pocketflow-heartbeat](https://github.com/The-Pocket/PocketFlow/tree/main/cookbook/pocketflow-heartbeat)
**Difficulty:** ★☆☆
**Category:** automation

## What it does

Implements a long-running polling agent that checks an IMAP inbox on a configurable interval, summarizes new emails, and suggests a prioritized action for each. A WHILE loop drives the monitoring cycle: connect to IMAP, fetch unseen messages, run an LLM summarization and action-recommendation pass, log the results, then sleep for the configured interval before the next cycle. The loop exits after a maximum number of cycles or when interrupted.

## Real-world use cases

- **Executive inbox triage**: Continuously scan a high-volume inbox, surfacing action items and flagging urgent messages without human attention on every poll
- **On-call alerting**: Monitor a shared ops or support inbox for critical keywords and suggest escalation actions when specific SLA triggers are detected
- **Business intelligence automation**: Watch for emails from key vendors, clients, or partners and extract structured information (order updates, contract changes) on arrival
- **Compliance monitoring**: Scan regulatory notification inboxes and log summarized alerts with recommended responses for compliance officer review

## Key SPL constructs

- `CREATE TOOL_API fetch_emails(imap_host, imap_user, imap_pass)` — authenticates via IMAP and returns unseen messages as JSON
- `CREATE TOOL_API sleep_interval(seconds)` — deterministic sleep between polling cycles
- `CREATE TOOL_API log_results(log_file, cycle, results)` — appends cycle results to a persistent log file
- `WHILE @cycle < @max_cycles DO` — bounded polling loop
- `GENERATE summarize_and_act(@emails_json)` — produces a summary and suggested action for each new email

## Workflow I/O

**Inputs:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `@imap_host` | TEXT | _(required)_ | IMAP server hostname |
| `@imap_user` | TEXT | _(required)_ | IMAP account username |
| `@imap_pass` | TEXT | _(required)_ | IMAP account password |
| `@interval_seconds` | TEXT | `"60"` | Seconds between polling cycles |
| `@max_cycles` | INTEGER | 10 | Maximum number of polling cycles before exiting |
| `@log_file` | TEXT | _(required)_ | Path to the persistent log file |

**Output:** `@summary TEXT` — summary of the final cycle's processed emails

## Run

```bash
conda activate graf
cd ~/projects/digital-duck/graflang

graf run cookbook_pocketflow/heartbeat/heartbeat.graph.yaml \
    --llm claude_cli:claude-sonnet-4-6
```

## Extend it

- Add an `EVALUATE` branch to send a reply or forward specific emails automatically when the LLM detects high urgency
- Replace the fixed `sleep_interval` with an adaptive poll rate that speeds up when messages arrive frequently
- Use `CALL PARALLEL` to run the LLM summarization over multiple emails simultaneously on busy cycles
- Connect to a notification API (e.g., Slack webhook) via a `CREATE TOOL_API` to forward high-priority summaries in real time
