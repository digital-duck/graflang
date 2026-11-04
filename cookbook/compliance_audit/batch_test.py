"""Run the compliance audit over many different documents, with answer keys, and score it.

    python cookbook/compliance_audit/batch_test.py --variants recipe-z3,baseline --llm claude_cli:claude-haiku-5-5            # the plan only
    python cookbook/compliance_audit/batch_test.py --variants recipe-z3,baseline --llm claude_cli:claude-haiku-5-5 --yes      # makes the calls

The experiment is a grid: documents x variants x models.

  documents   input/batch-test/manifest.json (18 documents with answer keys; --docs picks some by id or tag, --limit takes the first N)
  variants    recipe-z3, recipe-stdlib, recipe-sympy (the recipe: a model reads, a rule engine decides) and baseline (a model judges, no solver)
  models      --llm one or more `adapter:model`, comma separated, for example claude_cli:claude-haiku-5-5,claude_cli:claude-sonnet-5-5,ollama:gemma4

Other things to vary: --rules-file (demo rules or extended rules), --destination (external or internal), --docs (a kind of document).

Every run is a real `graf run` and is billed (or uses your subscription or a local model). A run makes at most 3 model calls and is capped at 4 by a
bindings file; the plan line gives the upper bound before anything is sent, and --max-calls refuses a plan above it. Results are appended to
results.jsonl as they arrive, so a stopped batch can be continued with --resume (finished cells are skipped).

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
BATCH = HERE / "input" / "batch-test"
GRAPHS = {"recipe": "compliance_audit.graph.yaml", "baseline": "compliance_audit_llm_only.graph.yaml"}
FIRST_VERDICT = {"recipe": "*-check.out_verdict.md", "baseline": "*-judge.out_verdict.md"}
VARIANTS = ("recipe-z3", "recipe-stdlib", "recipe-sympy", "baseline")
CALLS_PER_RUN, CAP_PER_RUN = 3, 4


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
    row.update(audit=audit[:160], calls=summary["llm"]["calls"], tokens_in=summary["llm"]["input_tokens"], tokens_out=summary["llm"]["output_tokens"],
               first_compliant=(verdict or {}).get("compliant"), first_violated=(verdict or {}).get("violated"), result_dir=str(result_dir))
    return row


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--variants", default="recipe-z3,baseline", help=f"comma separated, from {', '.join(VARIANTS)} (default recipe-z3,baseline)")
    ap.add_argument("--llm", required=True, help="one or more adapter:model, comma separated")
    ap.add_argument("--manifest", default=str(BATCH / "manifest.json"))
    ap.add_argument("--docs", default="", help="document ids or tags, comma separated (default all)")
    ap.add_argument("--limit", type=int, default=None, help="only the first N of the chosen documents")
    ap.add_argument("--rules-file", default="./procedures/rules_extended.json", help="the recipe's rules (relative paths start in the recipe folder)")
    ap.add_argument("--destination", default=None, help="override every document's destination (default: the manifest's, external_api)")
    ap.add_argument("--max-calls", type=int, default=None, help="refuse a plan whose upper bound of model calls is above this")
    ap.add_argument("--timeout", type=int, default=600, help="seconds allowed for one run")
    ap.add_argument("--jobs", type=int, default=1, help="runs at the same time (keep 1 for a local model)")
    ap.add_argument("--out", default=None, help="results folder (default output/batch_test-<time>)")
    ap.add_argument("--resume", action="store_true", help="continue a batch in --out: skip the cells already in its results.jsonl")
    ap.add_argument("--yes", action="store_true", help="make the calls; without it only the plan is printed")
    args = ap.parse_args(argv)

    variants = [v.strip() for v in args.variants.split(",") if v.strip()]
    bad = [v for v in variants if v not in VARIANTS]
    models = [m.strip() for m in args.llm.split(",") if m.strip()]
    if bad or not models:
        ap.error(f"variants must be from {', '.join(VARIANTS)}; got {bad}" if bad else "give at least one --llm")
    docs = select(load_manifest(Path(args.manifest)), [x.strip() for x in args.docs.split(",") if x.strip()], args.limit)
    cells = [(d, v, m) for m in models for v in variants for d in docs]
    upper = len(cells) * CALLS_PER_RUN
    print(f"plan: {len(docs)} document(s) x {len(variants)} variant(s) ({', '.join(variants)}) x {len(models)} model(s) ({', '.join(models)}) "
          f"= {len(cells)} runs, at most {upper} model calls")
    if args.max_calls is not None and upper > args.max_calls:
        print(f"refused: the upper bound {upper} is above --max-calls {args.max_calls}")
        return 2
    if not args.yes:
        print("nothing was run; add --yes to make the calls")
        return 0

    out = Path(args.out) if args.out else HERE / "output" / f"batch_test-{time.strftime('%Y%m%d-%H%M%S')}"
    out.mkdir(parents=True, exist_ok=True)
    bind = out / "limits.bind.yaml"
    bind.write_text(f"limits:\n  max_llm_calls: {CAP_PER_RUN}\n  max_steps: 80\n  wall_time_s: {args.timeout}\n")
    results = out / "results.jsonl"
    rows: List[Dict[str, Any]] = [json.loads(line) for line in results.read_text().splitlines() if line.strip()] if (args.resume and results.exists()) else []
    done = {(r["doc"], r["variant"], r["llm"]) for r in rows}
    todo = [c for c in cells if (c[0]["id"], c[1], c[2]) not in done]
    if len(todo) < len(cells):
        print(f"resuming: {len(cells) - len(todo)} run(s) already have a result")

    def work(cell):
        d, v, m = cell
        label = f"{v}-{m.replace(':', '_').replace('/', '_')}-{d['id']}"
        return one_run(d, v, m, args, out / "runs" / label, bind)

    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        for row in pool.map(work, todo):
            rows.append(row)
            with results.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            flag = row.get("error") and f"ERROR {row['error']}" or (("released" if row["released"] else "escalated")
                   + (" LEAK " + str(row["leaks"]) if row["false_release"] else "") + (" FALSE-ESCALATION" if row["false_escalation"] else "")
                   + (" over-redacted " + str(row["lost"]) if row["over_redaction"] else ""))
            print(f"{row['variant']:13} {row['llm'].split(':')[-1]:20} {row['doc']:24} {flag}")

    report = markdown(rows)
    (out / "summary.md").write_text(report, encoding="utf-8")
    print("\n" + report)
    print(f"results: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
