"""Run the compliance audit over many different documents, with answer keys, and score it.

    python cookbook/compliance_audit/batch_test.py --variants recipe-z3,llm_only --llm claude_cli:claude-haiku-5-5              # makes the calls
    python cookbook/compliance_audit/batch_test.py --variants recipe-z3,llm_only --llm claude_cli:claude-haiku-5-5 --dry-run    # the plan only

The experiment is a grid: documents x variants x models.

  documents   input/batch-test/manifest.json (20 documents with answer keys; --docs picks some by id or tag, --limit takes the first N)
  variants    recipe-z3, recipe-stdlib, recipe-sympy (the recipe: a model reads, a rule engine decides) and llm_only (a model judges, no solver)
  models      --llm one or more `adapter:model`, comma separated, for example claude_cli:claude-haiku-5-5,claude_cli:claude-sonnet-5-5,ollama:gemma4

Other things to vary: --rules-file (demo rules or extended rules), --destination (external or internal), --docs (a kind of document).

Every run is a real `graf run` and is billed (or uses your subscription or a local model). The number of model calls in a run is read from the graph (the figure `graf validate` prints); each run is capped at that plus a
margin (--margin, default 50%) by a bindings file, so a retry loop cannot run away. The plan line gives the expected and the worst-case total
before anything is sent, and --max-calls (a budget for the whole batch) refuses a plan whose worst case is above it. Results are appended to
the SQLite database (--db) as they arrive, so a stopped batch can be continued with --resume (finished cells are skipped). The summary tables are
printed and stored in the batches table (`summary` column); batch_analyze.py reads the database.

Scoring, per run (the answer key says what is personal data; nothing is guessed):
  false release      the document was released and a `must_mask` string is still in the released text. The costly error.
  false escalation   the document was expected to be released and was escalated to a person.
  over-redaction     released, but a `must_keep` string is gone from the text.
  correct            released with no leak and nothing over-redacted (or escalated when the key expects that).
  error              the run failed to give a result (a missing package, a timeout, an unreadable reply).
`ambiguous` items (company contacts, ids a policy has to rule on) are recorded and never scored.
"""
import argparse
import json
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import batch_store as store  # noqa: E402  (SQLite storage, beside this file)
BATCH = HERE / "input" / "batch-test"
GRAPHS = {"recipe": "compliance_audit.graph.yaml", "llm_only": "compliance_audit_llm_only.graph.yaml"}
FIRST_VERDICT = {"recipe": "*-check.out_verdict.md", "llm_only": "*-judge.out_verdict.md"}
VARIANTS = ("recipe-z3", "recipe-stdlib", "recipe-sympy", "llm_only")
MARGIN = 0.5            # the per-run cap is the graph's model-call count plus this share (see calls_per_run)


def calls_per_run(variant: str, margin: float = MARGIN) -> tuple:
    """(calls, cap) for one run of `variant`: the static model-call count of its graph (what `graf validate` prints) and the
    `limits.max_llm_calls` set from it with the margin. Raises when the count is not exact (the cap would be a guess)."""
    from graphlang.grafr.runtime import load_graph
    from graphlang.grafr import partinfo
    caps = partinfo.capabilities(load_graph(HERE / GRAPHS[variant.partition("-")[0]]).get("nodes", []))
    if not caps["llm_exact"]:
        raise ValueError(f"{variant}: the graph's model-call count is not exact; set --cap-per-run")
    return caps["llm_calls"], partinfo.suggested_cap(caps["llm_calls"], margin)


# ---- the answer key and the scoring (pure functions; tests/test_batch_test.py covers them) -------------------------------
def norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).lower())


def load_manifest(path: Path) -> List[Dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    docs = data["documents"]
    ids = [d["id"] for d in docs]
    if len(set(ids)) != len(ids):
        raise ValueError("manifest: document ids must be unique")
    return docs


def select(docs: List[Dict[str, Any]], names: Optional[List[str]], limit: Optional[int]) -> List[Dict[str, Any]]:
    """Documents whose id or one of whose tags is in `names` (all when none given), the first `limit` of them."""
    if names:
        wanted = set(names)
        chosen = [d for d in docs if d["id"] in wanted or wanted & set(d.get("tags", []))]
        unknown = wanted - {d["id"] for d in docs} - {t for d in docs for t in d.get("tags", [])}
        if unknown:
            raise ValueError(f"no document or tag named {sorted(unknown)}")
    else:
        chosen = list(docs)
    return chosen[:limit] if limit else chosen


def score(doc: Dict[str, Any], released: bool, safe_text: str) -> Dict[str, Any]:
    """Score one run against its answer key. `safe_text` is the released text ('' when escalated)."""
    expect = doc.get("expect", "released")
    text = norm(safe_text)
    leaks = [s for s in doc.get("must_mask", []) if released and norm(s) in text]
    lost = [s for s in doc.get("must_keep", []) if released and norm(s) not in text]
    seen_ambiguous = [s for s in doc.get("ambiguous", []) if released and norm(s) in text]
    false_escalation = (expect == "released") and not released
    if expect == "escalated":
        correct = not released
    else:
        correct = released and not leaks and not lost
    return {"released": released, "false_release": bool(leaks), "leaks": leaks, "false_escalation": false_escalation,
            "over_redaction": bool(lost), "lost": lost, "ambiguous_left": seen_ambiguous, "correct": correct}


def summarize(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """One line per (variant, model): counts of each outcome, model calls, tokens and time."""
    out = []
    keys = sorted({(r["variant"], r["llm"]) for r in rows})
    for variant, llm in keys:
        mine = [r for r in rows if r["variant"] == variant and r["llm"] == llm]
        ok = [r for r in mine if not r.get("error")]
        out.append({"variant": variant, "llm": llm, "runs": len(mine), "errors": len(mine) - len(ok),
                    "correct": sum(bool(r["correct"]) for r in ok), "false_release": sum(bool(r["false_release"]) for r in ok),
                    "false_escalation": sum(bool(r["false_escalation"]) for r in ok), "over_redaction": sum(bool(r["over_redaction"]) for r in ok),
                    "released": sum(bool(r["released"]) for r in ok),
                    "calls": sum(r.get("calls", 0) for r in ok), "tokens": sum(r.get("tokens_in", 0) + r.get("tokens_out", 0) for r in ok),
                    "seconds": round(sum(r.get("seconds", 0) for r in mine), 1)})
    return out


def markdown(rows: List[Dict[str, Any]]) -> str:
    lines = ["## By variant and model", "",
             "| variant | model | runs | correct | **false release** | false escalation | over-redaction | errors | calls | tokens (est.) | seconds |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for s in summarize(rows):
        lines.append(f"| {s['variant']} | {s['llm']} | {s['runs']} | {s['correct']} | **{s['false_release']}** | {s['false_escalation']} | "
                     f"{s['over_redaction']} | {s['errors']} | {s['calls']} | {s['tokens']} | {s['seconds']} |")
    docs = sorted({r["doc"] for r in rows})
    cells = sorted({(r["variant"], r["llm"]) for r in rows})
    lines += ["", "## By document", "", "R = released, E = escalated; ! = leak (false release), x = false escalation, o = over-redaction, ? = error", "",
              "| document | " + " | ".join(f"{v} / {m.split(':')[-1]}" for v, m in cells) + " |", "|---|" + "---|" * len(cells)]
    for d in docs:
        row = []
        for v, m in cells:
            r = next((x for x in rows if x["doc"] == d and x["variant"] == v and x["llm"] == m), None)
            if r is None:
                row.append("")
            elif r.get("error"):
                row.append("?")
            else:
                row.append(("R" if r["released"] else "E") + ("!" if r["false_release"] else "") + ("x" if r["false_escalation"] else "")
                           + ("o" if r["over_redaction"] else ""))
        lines.append(f"| {d} | " + " | ".join(row) + " |")
    return "\n".join(lines) + "\n"


# ---- running ------------------------------------------------------------------------------------------------------------
def read_json(text: str):
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    try:
        return json.loads(fenced.group(1) if fenced else text)
    except ValueError:
        return None


def one_run(doc: Dict[str, Any], variant: str, llm: str, args, folder: Path, bind: Path) -> Dict[str, Any]:
    which, _, engine = variant.partition("-")
    destination = args.destination or doc.get("destination", "external_api")
    path = (BATCH / doc["file"]).resolve()
    cmd = [sys.executable, "-m", "graphlang", "run", str(HERE / GRAPHS[which]), "--llm", llm, "--bind", str(bind), "--output-dir", str(folder),
           "--no-log", "--param", f"document={path}", "--param", f"destination={destination}"]
    if which == "recipe":
        cmd += ["--param", f"engine={engine}", "--param", f"rules_file={args.rules_file}"]
    started = time.time()
    row: Dict[str, Any] = {"doc": doc["id"], "variant": variant, "llm": llm, "destination": destination}
    try:
        done = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True, timeout=args.timeout)
    except subprocess.TimeoutExpired:
        return {**row, "seconds": round(time.time() - started, 1), "error": f"timed out after {args.timeout}s"}
    row["seconds"] = round(time.time() - started, 1)
    runs = sorted(folder.glob("*/summary.json"))
    if not (done.returncode == 0 and runs):
        return {**row, "error": ((done.stderr or done.stdout).strip().splitlines() or ["no result"])[-1][:300]}
    result_dir = runs[-1].parent
    summary = json.loads(runs[-1].read_text())
    result = json.loads((result_dir / "result.json").read_text())
    audit = str(result.get("audit", ""))
    released = audit.startswith("released")
    first = next(iter(sorted((result_dir / "nodes").glob(FIRST_VERDICT[which]))), None)
    verdict = read_json(first.read_text()) if first else None
    row.update(score(doc, released, str(result.get("safe_document", "")) if released else ""))
    nodes = summary.get("nodes", {})
    row.update(llm_seconds=round(summary["llm"].get("ms", 0) / 1000, 2),                   # time inside model calls
               other_seconds=round(sum(n.get("ms", 0) for n in nodes.values() if n.get("type") != "GENERATE") / 1000, 2),   # rules, guard, loading
               audit=audit[:160], calls=summary["llm"]["calls"], tokens_in=summary["llm"]["input_tokens"], tokens_out=summary["llm"]["output_tokens"],
               first_compliant=(verdict or {}).get("compliant"), first_violated=(verdict or {}).get("violated"), result_dir=str(result_dir))
    return row


def rescore(args) -> int:
    """Score every stored result of --db again against the manifest (the run folders keep the released text); no model is called."""
    docs = {d["id"]: d for d in load_manifest(Path(args.manifest))}
    conn = store.connect(args.db)
    changed = total = 0
    for r in conn.execute("SELECT * FROM results WHERE error IS NULL AND result_dir IS NOT NULL").fetchall():
        doc, folder = docs.get(r["doc"]), Path(r["result_dir"])
        if doc is None or not (folder / "result.json").is_file():
            continue
        total += 1
        result = json.loads((folder / "result.json").read_text(encoding="utf-8"))
        released = str(result.get("audit", "")).startswith("released")
        new = score(doc, released, str(result.get("safe_document", "")) if released else "")
        old = (r["correct"], r["false_release"], r["false_escalation"], r["over_redaction"])
        if old != tuple(int(bool(new[k])) for k in ("correct", "false_release", "false_escalation", "over_redaction")):
            changed += 1
            store.write_result(conn, r["batch_id"], {**dict(r), **new})
    print(f"rescored {total} stored result(s) in {args.db}: {changed} changed")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--variants", default="recipe-z3,llm_only", help=f"comma separated, from {', '.join(VARIANTS)} (default recipe-z3,llm_only)")
    ap.add_argument("--llm", default="", help="one or more adapter:model, comma separated (not needed with --rescore)")
    ap.add_argument("--manifest", default=str(BATCH / "manifest.json"))
    ap.add_argument("--docs", default="", help="document ids or tags, comma separated (default all)")
    ap.add_argument("--limit", type=int, default=None, help="only the first N of the chosen documents")
    ap.add_argument("--rules-file", default="./procedures/rules_extended.json", help="the recipe's rules (relative paths start in the recipe folder)")
    ap.add_argument("--destination", default=None, help="override every document's destination (default: the manifest's, external_api)")
    ap.add_argument("--margin", type=float, default=MARGIN, help="safety margin on each run's model-call cap: cap = ceil(calls x (1 + margin)); default 0.5")
    ap.add_argument("--cap-per-run", type=int, default=None, help="set every run's model-call cap yourself (needed when the graph's count is not exact)")
    ap.add_argument("--max-calls", type=int, default=None, help="budget for the whole batch: refuse a plan whose worst case (every run at its cap) is above this")
    ap.add_argument("--timeout", type=int, default=600, help="seconds allowed for one run")
    ap.add_argument("--jobs", type=int, default=1, help="runs at the same time (keep 1 for a local model)")
    ap.add_argument("--repeat", type=int, default=1, help="repeat every cell this many times (a model can vary from run to run)")
    ap.add_argument("--db", default=str(HERE / "output" / "experiments.db"), help="SQLite database that receives every result (default output/experiments.db)")
    ap.add_argument("--out", default=None, help="results folder (default output/batch_test-<time>)")
    ap.add_argument("--resume", action="store_true", help="skip the cells that already have a result without error: in the database (errors are tried again)")
    ap.add_argument("--rescore", action="store_true", help="no model calls: score the stored results of --db again against the current manifest (after you change an answer key)")
    ap.add_argument("--dry-run", action="store_true", help="print the plan (runs and the upper bound of model calls) and make no calls")
    args = ap.parse_args(argv)

    if args.rescore:
        return rescore(args)
    variants = [v.strip() for v in args.variants.split(",") if v.strip()]
    bad = [v for v in variants if v not in VARIANTS]
    models = [m.strip() for m in args.llm.split(",") if m.strip()]
    if bad or not models:
        ap.error(f"variants must be from {', '.join(VARIANTS)}; got {bad}" if bad else "give at least one --llm")
    docs = select(load_manifest(Path(args.manifest)), [x.strip() for x in args.docs.split(",") if x.strip()], args.limit)
    if args.repeat < 1:
        ap.error("--repeat must be at least 1")
    cells = [(d, v, m, r) for m in models for v in variants for d in docs for r in range(args.repeat)]
    per = {}
    for v in variants:
        try:
            calls, cap = calls_per_run(v, args.margin)
        except ValueError as e:
            if args.cap_per_run is None:
                ap.error(str(e))
            calls, cap = args.cap_per_run, args.cap_per_run
        per[v] = (calls, args.cap_per_run or cap)
    upper = sum(per[c[1]][1] for c in cells)          # what the runs may use at most: each run stops at its cap
    expected = sum(per[c[1]][0] for c in cells)
    print("plan")
    print(f"  documents    {len(docs)}")
    print(f"  variants     {', '.join(variants)}")
    print(f"  models       {', '.join(models)}")
    print(f"  repeat       {args.repeat}")
    print(f"  runs         {len(cells)}  ({len(docs)} x {len(variants)} x {len(models)} x {args.repeat})")
    print(f"  model calls  about {expected}, at most {upper}")
    for v in variants:
        print(f"  cap per run  {v}: {per[v][1]}  (graph makes {per[v][0]})")
    if args.max_calls is not None and upper > args.max_calls:
        print(f"refused: the upper bound {upper} is above --max-calls {args.max_calls}")
        return 2
    if args.dry_run:
        print("dry run: nothing was run")
        return 0

    out = Path(args.out) if args.out else HERE / "output" / f"batch_test-{time.strftime('%Y%m%d-%H%M%S')}"
    out.mkdir(parents=True, exist_ok=True)
    binds = {}
    for v, (_, cap) in per.items():
        binds[v] = out / f"limits-{v}.bind.yaml"
        binds[v].write_text(f"limits:\n  max_llm_calls: {cap}\n  max_steps: 80\n  wall_time_s: {args.timeout}\n")
    conn = store.connect(args.db)
    finished = store.done_keys(conn) if args.resume else set()
    rows: List[Dict[str, Any]] = []
    todo = [c for c in cells if (c[0]["id"], c[1], c[3], c[2]) not in finished]
    if len(todo) < len(cells):
        print(f"resuming: {len(cells) - len(todo)} run(s) already have a result")
    batch_id = store.start_batch(conn, models=models, variants=variants, n_docs=len(docs), reps=args.repeat, args=vars(args))

    def work(cell):
        d, v, m, rep = cell
        label = f"{v}-{m.replace(':', '_').replace('/', '_')}-{d['id']}" + (f"-r{rep}" if args.repeat > 1 else "")
        return {**one_run(d, v, m, args, out / "runs" / label, binds[v]), "rep": rep}

    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        for row in pool.map(work, todo):
            rows.append(row)
            store.write_result(conn, batch_id, row)
            flag = row.get("error") and f"ERROR {row['error']}" or (("released" if row["released"] else "escalated")
                   + (" LEAK " + str(row["leaks"]) if row["false_release"] else "") + (" FALSE-ESCALATION" if row["false_escalation"] else "")
                   + (" over-redacted " + str(row["lost"]) if row["over_redaction"] else ""))
            print(f"{row['variant']:13} {row['llm'].split(':')[-1]:20} {row['doc']:24} {flag}")

    report = markdown(rows)
    store.finish_batch(conn, batch_id, report)
    print("\n" + report)
    print(f"run folders: {out / 'runs'}\ndatabase: {args.db}  (batch {batch_id}; python {HERE / 'batch_analyze.py'} --db {args.db})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
