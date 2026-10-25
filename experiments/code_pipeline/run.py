"""Run the experiment: for each task, arm and repetition, produce code, score it with the hidden tests, append one JSON line.

    python run.py --verify-oracle                                  # every canonical solution must pass (no LLM)
    python run.py --n 2 --arms single,spl,graflang,langgraph --reps 1 --model claude-haiku-5-5 --out results/smoke.jsonl

Runs are sequential (the SPL and GraphLang arms write their artifacts to one folder each) and resumable: a (task, arm, rep)
already in the output file is skipped. The order of arms is shuffled per task and repetition so drift in the model's
behaviour over the session does not favour one arm.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import oracle  # noqa: E402
import tasks as T  # noqa: E402
from arms import ARMS, NEEDS_WORK_DIR  # noqa: E402


def verify_oracle() -> int:
    bad = [t["task_id"] for t in T.load_all() if not oracle.check(t, t["prompt"] + t["canonical_solution"]).passed]
    wrong = [t["task_id"] for t in T.load_all() if oracle.check(t, "def " + t["entry_point"] + "(*a, **k):\n    return None\n").passed]
    print(f"canonical solutions failing the oracle: {bad or 'none'}; trivial stub passing it: {wrong or 'none'}")
    return 1 if bad or wrong else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify-oracle", action="store_true")
    ap.add_argument("--n", type=int, default=None, help="size of the fixed random task sample (default: all 164)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--arms", default="single,spl,graflang,langgraph")
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--model", default="claude-haiku-5-5")
    ap.add_argument("--out", default="results/run.jsonl")
    args = ap.parse_args()
    if args.verify_oracle:
        return verify_oracle()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if out.exists():
        done = {(r["task"], r["arm"], r["rep"]) for r in map(json.loads, out.read_text().splitlines()) if r}
    arms = args.arms.split(",")
    for rep in range(args.reps):
        for task in T.sample(args.n, args.seed):
            order = arms[:]
            random.Random(f"{task['task_id']}/{rep}/{args.seed}").shuffle(order)
            for arm in order:
                if (task["task_id"], arm, rep) in done:
                    continue
                with tempfile.TemporaryDirectory() as tmp:
                    fn = ARMS[arm]
                    res = fn(T.spec_for(task), args.model, Path(tmp)) if arm in NEEDS_WORK_DIR else fn(T.spec_for(task), args.model)
                verdict = oracle.check(task, res.code)
                row = {"task": task["task_id"], "arm": arm, "rep": rep, "model": args.model, "passed": verdict.passed,
                       "reason": verdict.reason, "status": res.status, "pipeline_verdict": res.pipeline_verdict,
                       "cycles": res.cycles, "seconds": round(res.seconds, 1), "code": res.code}
                with out.open("a") as f:
                    f.write(json.dumps(row) + "\n")
                print(f"{task['task_id']:14} {arm:10} rep{rep} {'PASS' if verdict.passed else 'fail'} "
                      f"{res.seconds:6.1f}s cycles={res.cycles} pipeline={res.pipeline_verdict or '-'} {res.status if res.status != 'ok' else ''}",
                      flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
