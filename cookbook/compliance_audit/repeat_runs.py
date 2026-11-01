"""Run the recipe and its LLM-only baseline several times on one document and compare the outcomes.

    python cookbook/compliance_audit/repeat_runs.py --runs 3 --llm claude_cli:claude-haiku-5-5            # prints the plan only
    python cookbook/compliance_audit/repeat_runs.py --runs 3 --llm claude_cli:claude-haiku-5-5 --yes      # makes the calls

Every run is a real `graf run` and is billed (or uses your subscription / local model). Each run makes at most 3 LLM calls and is capped at
4 by a bindings file, so `--runs 3` on both graphs makes at most 18 calls; the plan line says the number before anything is sent.
For each run it reads the *first* verdict (before any redaction): the same text judged several times should get the same verdict.
"""
import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
GRAPHS = {"recipe": "compliance_audit.graph.yaml", "baseline": "compliance_audit_llm_only.graph.yaml"}
FIRST_VERDICT = {"recipe": "*-check.out_verdict.md", "baseline": "*-judge.out_verdict.md"}
CALLS_PER_RUN, CAP_PER_RUN = 3, 4


def read_json(text: str):
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    try:
        return json.loads(fenced.group(1) if fenced else text)
    except ValueError:
        return None


def one_run(which: str, args, folder: Path, bind: Path) -> dict:
    cmd = [sys.executable, "-m", "graphlang", "run", str(HERE / GRAPHS[which]), "--llm", args.llm, "--bind", str(bind), "--output-dir", str(folder),
           "--no-log", "--param", f"document={args.document}", "--param", f"destination={args.destination}"]
    if which == "recipe":
        cmd += ["--param", f"engine={args.engine}", "--param", f"rules_file={args.rules_file}"]
    started = time.time()
    done = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True)
    row = {"graph": which, "seconds": round(time.time() - started, 1), "ok": done.returncode == 0}
    runs = sorted(folder.glob("*/summary.json"))
    if not (done.returncode == 0 and runs):
        row["error"] = (done.stderr or done.stdout).strip().splitlines()[-1:] or ["no result"]
        return row
    result_dir = runs[-1].parent
    summary = json.loads(runs[-1].read_text())
    audit = json.loads((result_dir / "result.json").read_text()).get("audit", "")
    first = next(iter(sorted((result_dir / "nodes").glob(FIRST_VERDICT[which]))), None)
    verdict = read_json(first.read_text()) if first else None
    row.update(released=audit.startswith("released"), calls=summary["llm"]["calls"], tokens_in=summary["llm"]["input_tokens"],
               tokens_out=summary["llm"]["output_tokens"],
               first_compliant=(verdict or {}).get("compliant"), first_violated=(verdict or {}).get("violated"))
    return row


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--runs", type=int, default=3, help="runs per graph (default 3)")
    ap.add_argument("--graphs", choices=["both", "recipe", "baseline"], default="both")
    ap.add_argument("--llm", required=True, help="adapter[:model], like graf run --llm")
    ap.add_argument("--document", default="./input/hard_case_file.txt", help="a text or a file path (relative paths start in the recipe folder)")
    ap.add_argument("--destination", default="external_api")
    ap.add_argument("--engine", default="z3", help="the recipe's rule engine: stdlib, sympy or z3")
    ap.add_argument("--rules-file", default="./procedures/rules_extended.json")
    ap.add_argument("--out", default=None, help="folder for the run results (default output/repeat_runs-<time>)")
    ap.add_argument("--yes", action="store_true", help="make the calls; without it only the plan is printed")
    args = ap.parse_args()

    which = ["recipe", "baseline"] if args.graphs == "both" else [args.graphs]
    total = args.runs * len(which) * CALLS_PER_RUN
    print(f"plan: {args.runs} run(s) of {', '.join(which)} on {args.document} -> {args.destination} with {args.llm}: at most {total} LLM calls")
    if not args.yes:
        print("nothing was run; add --yes to make the calls")
        return 0

    out = Path(args.out) if args.out else HERE / "output" / f"repeat_runs-{time.strftime('%Y%m%d-%H%M%S')}"
    out.mkdir(parents=True, exist_ok=True)
    bind = out / "limits.bind.yaml"
    bind.write_text(f"limits:\n  max_llm_calls: {CAP_PER_RUN}\n  max_steps: 60\n  wall_time_s: 600\n")
    rows = []
    for graph in which:
        for i in range(1, args.runs + 1):
            row = one_run(graph, args, out / f"{graph}-{i}", bind)
            rows.append(row)
            print(f"{graph:8} run {i}: " + (", ".join(f"{k}={v}" for k, v in row.items() if k not in ("graph",)) if row["ok"] else f"FAILED {row.get('error')}"))

    print("\nsummary (the first verdict is the judgment of the unredacted text)")
    for graph in which:
        mine = [r for r in rows if r["graph"] == graph and r["ok"]]
        if not mine:
            continue
        lists = sorted({json.dumps(r.get("first_violated")) for r in mine})
        print(f"{graph:8} runs ok {len(mine)}/{args.runs}; released {sum(bool(r['released']) for r in mine)}; first said compliant "
              f"{sum(bool(r['first_compliant']) for r in mine)}; distinct first 'violated' lists: {len(lists)} {lists}; "
              f"tokens in+out per run {[r['tokens_in'] + r['tokens_out'] for r in mine]}")
    (out / "repeat_runs.json").write_text(json.dumps(rows, indent=2))
    print(f"results: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
