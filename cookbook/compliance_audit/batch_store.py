"""SQLite storage for the batch experiment (laid out like experiments/code_pipeline/store.py): one row per cell.

    sqlite3 output/experiments.db "SELECT * FROM variant_summary"

Tables
    batches   one row per `batch_test.py` invocation (models, variants, documents, arguments, host, start and end time)
    results   one row per (doc, variant, rep, model): the score against the answer key, calls, tokens, time, the first verdict
Views
    variant_summary   per model and variant: runs, correct, false releases, false escalations, over-redactions, errors, mean cost
"""
from __future__ import annotations

import json
import socket
import sqlite3
from datetime import datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS batches (
    batch_id    TEXT PRIMARY KEY,
    hostname    TEXT,
    models      TEXT,
    variants    TEXT,
    n_docs      INTEGER,
    reps        INTEGER,
    args        TEXT,
    started_at  TIMESTAMP,
    finished_at TIMESTAMP,
    runs_done   INTEGER DEFAULT 0,
    summary     TEXT
);
CREATE TABLE IF NOT EXISTS results (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id         TEXT,
    hostname         TEXT,
    doc              TEXT    NOT NULL,
    variant          TEXT    NOT NULL,
    rep              INTEGER NOT NULL DEFAULT 0,
    llm              TEXT    NOT NULL,
    destination      TEXT,
    released         INTEGER,
    correct          INTEGER,
    false_release    INTEGER,
    false_escalation INTEGER,
    over_redaction   INTEGER,
    leaks            TEXT,
    lost             TEXT,
    ambiguous_left   TEXT,
    audit            TEXT,
    first_compliant  INTEGER,
    first_violated   TEXT,
    calls            INTEGER,
    tokens_in        INTEGER,
    tokens_out       INTEGER,
    seconds          REAL,
    llm_seconds      REAL,
    other_seconds    REAL,
    result_dir       TEXT,
    error            TEXT,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(doc, variant, rep, llm)
);
CREATE VIEW IF NOT EXISTS variant_summary AS
    SELECT llm, variant, COUNT(*) AS runs, SUM(error IS NOT NULL) AS errors,
           SUM(correct) AS correct, SUM(false_release) AS false_releases, SUM(false_escalation) AS false_escalations,
           SUM(over_redaction) AS over_redactions, ROUND(AVG(calls), 2) AS mean_calls,
           ROUND(AVG(tokens_in + tokens_out), 0) AS mean_tokens, ROUND(AVG(seconds), 1) AS mean_seconds,
           ROUND(AVG(llm_seconds), 1) AS mean_llm_seconds, ROUND(AVG(other_seconds), 2) AS mean_other_seconds
    FROM results GROUP BY llm, variant ORDER BY llm, variant;
"""

COLUMNS = ("batch_id", "hostname", "doc", "variant", "rep", "llm", "destination", "released", "correct", "false_release", "false_escalation",
           "over_redaction", "leaks", "lost", "ambiguous_left", "audit", "first_compliant", "first_violated", "calls", "tokens_in",
           "tokens_out", "seconds", "llm_seconds", "other_seconds", "result_dir", "error")
JSON_COLUMNS = ("leaks", "lost", "ambiguous_left", "first_violated")
BOOL_COLUMNS = ("released", "correct", "false_release", "false_escalation", "over_redaction", "first_compliant")


def connect(path) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=60)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def start_batch(conn, *, models, variants, n_docs: int, reps: int, args: dict) -> str:
    host, now = socket.gethostname(), datetime.now()
    base = batch_id = f"{now:%Y%m%d-%H%M%S}-{host}"
    n = 1
    while conn.execute("SELECT 1 FROM batches WHERE batch_id = ?", (batch_id,)).fetchone():
        n += 1
        batch_id = f"{base}-{n}"
    conn.execute("INSERT INTO batches (batch_id, hostname, models, variants, n_docs, reps, args, started_at) VALUES (?,?,?,?,?,?,?,?)",
                 (batch_id, host, ",".join(models), ",".join(variants), n_docs, reps, json.dumps(args), now.isoformat(timespec="seconds")))
    conn.commit()
    return batch_id


def finish_batch(conn, batch_id: str, summary: str | None = None) -> None:
    """Close a batch: end time, run count, and the markdown summary tables of this batch's rows (shown by `analyze.py --batch`)."""
    conn.execute("UPDATE batches SET finished_at = ?, runs_done = (SELECT COUNT(*) FROM results WHERE batch_id = ?), summary = ? WHERE batch_id = ?",
                 (datetime.now().isoformat(timespec="seconds"), batch_id, summary, batch_id))
    conn.commit()


def done_keys(conn) -> set:
    """(doc, variant, rep, llm) of every run that finished without an error: a rerun skips these and retries the errors."""
    return {(r["doc"], r["variant"], r["rep"], r["llm"]) for r in conn.execute("SELECT doc, variant, rep, llm FROM results WHERE error IS NULL")}


def write_result(conn, batch_id: str, row: dict) -> None:
    """Store one `batch_test.one_run` row (plus `rep`); an earlier row of the same cell is replaced."""
    v = {"batch_id": batch_id, "hostname": socket.gethostname(), "rep": 0, **row}
    for c in JSON_COLUMNS:
        if c in v and v[c] is not None and not isinstance(v[c], str):
            v[c] = json.dumps(v[c], ensure_ascii=False)
    for c in BOOL_COLUMNS:
        if v.get(c) is not None:
            v[c] = int(bool(v[c]))
    conn.execute(f"INSERT OR REPLACE INTO results ({', '.join(COLUMNS)}) VALUES ({', '.join('?' for _ in COLUMNS)})", [v.get(c) for c in COLUMNS])
    conn.commit()


def load_rows(path, batch: str | None = None) -> list[dict]:
    """All results as dicts (booleans back to bool, JSON columns decoded), from a .db file."""
    conn = connect(path)
    rows = [dict(r) for r in conn.execute("SELECT * FROM results ORDER BY id")]
    for r in rows:
        for c in BOOL_COLUMNS:
            if r[c] is not None:
                r[c] = bool(r[c])
        for c in ("leaks", "lost", "ambiguous_left"):
            r[c] = json.loads(r[c]) if r[c] else []
    return [r for r in rows if batch is None or r["batch_id"] == batch]
