"""SQLite storage for the experiment, laid out like SPL.py's cookbook/077_neurosymbolic (a `results` table with one row per
cell, an invocation table beside it), so a run can be queried with plain SQL.

    sqlite3 results/experiment.db "SELECT * FROM arm_summary"

Tables
    batches   one row per `run.py` invocation (adapter, model, arguments, host, start and end time)
    results   one row per (task, arm, rep, adapter, model), with the verdict of the hidden tests and the code that was scored
Views
    arm_summary   runs, passes and pass rate per adapter, model and arm

A database made by an older version (no adapter column) is migrated on first open: its rows get adapter `claude_cli`.
"""
from __future__ import annotations

import json
import socket
import sqlite3
from datetime import datetime
from pathlib import Path

RESULTS_TABLE = """
CREATE TABLE IF NOT EXISTS results (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id         TEXT,
    hostname         TEXT,
    task             TEXT    NOT NULL,
    arm              TEXT    NOT NULL,
    rep              INTEGER NOT NULL,
    adapter          TEXT    NOT NULL DEFAULT 'claude_cli',
    model            TEXT    NOT NULL,
    passed           INTEGER NOT NULL,
    reason           TEXT,
    status           TEXT,
    pipeline_verdict TEXT,
    cycles           INTEGER,
    seconds          REAL,
    code             TEXT,
    assert_passed    INTEGER,
    assert_total     INTEGER,
    llm_calls        INTEGER,
    prompt_tokens    INTEGER,
    output_tokens    INTEGER,
    cycles_detail    TEXT,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(task, arm, rep, adapter, model)
)
"""

# columns added after the first release of the table; a database made before them gets them on open
NEW_COLUMNS = {"assert_passed": "INTEGER", "assert_total": "INTEGER", "llm_calls": "INTEGER", "prompt_tokens": "INTEGER",
               "output_tokens": "INTEGER", "cycles_detail": "TEXT"}

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS batches (
    batch_id    TEXT PRIMARY KEY,
    hostname    TEXT,
    adapter     TEXT,
    model       TEXT,
    arms        TEXT,
    n_tasks     INTEGER,
    seed        INTEGER,
    reps        INTEGER,
    args        TEXT,
    started_at  TIMESTAMP,
    finished_at TIMESTAMP,
    runs_done   INTEGER DEFAULT 0
);
{RESULTS_TABLE};
CREATE VIEW IF NOT EXISTS arm_summary AS
    SELECT adapter, model, arm, COUNT(*) AS runs, SUM(passed) AS passes, ROUND(1.0 * SUM(passed) / COUNT(*), 3) AS pass_rate,
           ROUND(AVG(seconds), 1) AS mean_seconds
    FROM results GROUP BY adapter, model, arm ORDER BY adapter, model, arm;
"""

COLUMNS = ("batch_id", "hostname", "task", "arm", "rep", "adapter", "model", "passed", "reason", "status", "pipeline_verdict",
           "cycles", "seconds", "code", "assert_passed", "assert_total", "llm_calls", "prompt_tokens", "output_tokens",
           "cycles_detail")


def connect(path) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=60)     # wait for another writer instead of failing after the default 5 seconds
    conn.row_factory = sqlite3.Row
    _migrate(conn)
    conn.executescript(SCHEMA)
    return conn


def _migrate(conn) -> None:
    """Bring a database from before the adapter column up to date. SQLite cannot change a UNIQUE constraint in place,
    so the results table is rebuilt; the view is dropped first and recreated by SCHEMA."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(results)")}
    if cols and "adapter" not in cols:
        conn.execute("DROP VIEW IF EXISTS arm_summary")
        conn.execute("ALTER TABLE results RENAME TO results_old")
        conn.execute(RESULTS_TABLE)
        names = [r[1] for r in conn.execute("PRAGMA table_info(results_old)")]
        keep = [c for c in names if c != "id"]
        conn.execute(f"INSERT INTO results (id, {', '.join(c for c in keep)}, adapter) "
                     f"SELECT id, {', '.join(keep)}, 'claude_cli' FROM results_old")
        conn.execute("DROP TABLE results_old")
    cols = {r[1] for r in conn.execute("PRAGMA table_info(results)")}      # after the rebuild above, if there was one
    if cols:
        for name, kind in NEW_COLUMNS.items():
            if name not in cols:
                conn.execute(f"ALTER TABLE results ADD COLUMN {name} {kind}")
    batch_cols = {r[1] for r in conn.execute("PRAGMA table_info(batches)")}
    if batch_cols and "adapter" not in batch_cols:
        conn.execute("ALTER TABLE batches ADD COLUMN adapter TEXT")
    conn.commit()


def start_batch(conn, *, adapter: str, model: str, arms: list[str], n_tasks: int | None, seed: int, reps: int, args: dict) -> str:
    host = socket.gethostname()
    now = datetime.now()
    base = batch_id = f"{now:%Y%m%d-%H%M%S}-{host}"
    taken = 1
    while conn.execute("SELECT 1 FROM batches WHERE batch_id = ?", (batch_id,)).fetchone():
        taken += 1                                    # two invocations in the same second
        batch_id = f"{base}-{taken}"
    conn.execute("INSERT INTO batches (batch_id, hostname, adapter, model, arms, n_tasks, seed, reps, args, started_at) "
                 "VALUES (?,?,?,?,?,?,?,?,?,?)",
                 (batch_id, host, adapter, model, ",".join(arms), n_tasks, seed, reps, json.dumps(args),
                  now.isoformat(timespec="seconds")))
    conn.commit()
    return batch_id


def finish_batch(conn, batch_id: str) -> None:
    conn.execute("UPDATE batches SET finished_at = ?, runs_done = (SELECT COUNT(*) FROM results WHERE batch_id = ?) "
                 "WHERE batch_id = ?", (datetime.now().isoformat(timespec="seconds"), batch_id, batch_id))
    conn.commit()


def done_keys(conn) -> set:
    """(task, arm, rep, adapter, model) of every run already stored: the runner skips these. A run that ended in an error
    (the arm crashed, timed out or the model call failed: status `error:...`) is not done, so a rerun tries it again."""
    return {(r["task"], r["arm"], r["rep"], r["adapter"], r["model"])
            for r in conn.execute("SELECT task, arm, rep, adapter, model FROM results WHERE status NOT LIKE 'error%'")}


def write_result(conn, batch_id: str, row: dict) -> None:
    values = {"batch_id": batch_id, "hostname": socket.gethostname(), **row}
    conn.execute(f"INSERT OR REPLACE INTO results ({', '.join(COLUMNS)}) VALUES ({', '.join('?' for _ in COLUMNS)})",
                 [int(values[c]) if c == "passed" else values.get(c) for c in COLUMNS])
    conn.commit()


def load_rows(path, model: str | None = None, batch: str | None = None, adapter: str | None = None) -> list[dict]:
    """All results as dicts (`passed` is a bool), from a .db file, or from a .jsonl file written by an older run.py
    (which has no adapter: those rows are `claude_cli`)."""
    path = Path(path)
    if path.suffix == ".jsonl":
        rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    else:
        conn = connect(path)
        rows = [dict(r) for r in conn.execute("SELECT * FROM results ORDER BY id")]
        for r in rows:
            r["passed"] = bool(r["passed"])
    for r in rows:
        r.setdefault("adapter", "claude_cli")
    return [r for r in rows if (model is None or r["model"] == model) and (batch is None or r.get("batch_id") == batch)
            and (adapter is None or r["adapter"] == adapter)]


def import_jsonl(conn, path) -> int:
    """Load rows from a .jsonl file written by an older run.py into the database (existing runs are kept)."""
    batch_id = f"import-{Path(path).stem}"
    conn.execute("INSERT OR IGNORE INTO batches (batch_id, hostname, started_at, args) VALUES (?,?,?,?)",
                 (batch_id, socket.gethostname(), datetime.now().isoformat(timespec="seconds"), json.dumps({"imported": str(path)})))
    added = 0
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        r.setdefault("adapter", "claude_cli")
        if (r["task"], r["arm"], r["rep"], r["adapter"], r["model"]) in done_keys(conn):
            continue
        write_result(conn, batch_id, r)
        added += 1
    finish_batch(conn, batch_id)
    return added


def rescore(conn, verdict_for) -> int:
    """Score every stored row again with `verdict_for(task_id, code)`: updates passed, reason, the assertion counts and the
    hidden-test verdict of every cycle. Returns how many rows changed."""
    changed = 0
    for r in conn.execute("SELECT * FROM results").fetchall():
        v = verdict_for(r["task"], r["code"] or "")
        detail = json.loads(r["cycles_detail"]) if r["cycles_detail"] else None
        if detail:
            for c in detail:
                cv = verdict_for(r["task"], c.get("code") or "")
                c.update(hidden_passed=cv.passed, assert_passed=cv.assert_passed, assert_total=cv.assert_total)
        new = (int(v.passed), v.reason, v.assert_passed, v.assert_total, json.dumps(detail) if detail is not None else None)
        old = (r["passed"], r["reason"], r["assert_passed"], r["assert_total"], r["cycles_detail"])
        if new != old:
            conn.execute("UPDATE results SET passed = ?, reason = ?, assert_passed = ?, assert_total = ?, cycles_detail = ? "
                         "WHERE id = ?", (*new, r["id"]))
            changed += 1
    conn.commit()
    return changed
