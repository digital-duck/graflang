"""Summarize results/*.jsonl: pass rate per arm with 95% intervals, paired differences, how often the pipeline's own
LLM "test" agrees with the hidden tests, cost in time, and orchestration size.

    python analyze.py results/run.jsonl [more.jsonl ...]
"""
from __future__ import annotations

import json
import math
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def loc(path: Path) -> int:
    """Executable lines: not blank, not a comment (# or --)."""
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines()
               if line.strip() and not line.strip().startswith(("#", "--")))


def main(paths: list[str]) -> None:
    rows = [json.loads(line) for p in paths for line in Path(p).read_text().splitlines() if line.strip()]
    arms = sorted({r["arm"] for r in rows}, key=["single", "spl", "graflang", "langgraph"].index)
    per = {a: defaultdict(list) for a in arms}                       # arm -> task -> [passed per rep]
    for r in rows:
        per[r["arm"]][r["task"]].append(r["passed"])
    print(f"{len(rows)} runs, {len({r['task'] for r in rows})} tasks, models {sorted({r['model'] for r in rows})}\n")
    print(f"{'arm':10} {'runs':>5} {'pass':>6} {'95% CI (Wilson)':>18} {'median s':>9}  failures")
    for a in arms:
        rs = [r for r in rows if r["arm"] == a]
        k = sum(r["passed"] for r in rs)
        lo, hi = wilson(k, len(rs))
        secs = sorted(r["seconds"] for r in rs)
        why = Counter("tests" if r["status"] == "ok" and r["reason"] not in ("no_code",) else r["status"].split(":")[0]
                      for r in rs if not r["passed"])
        print(f"{a:10} {len(rs):5} {k / len(rs):6.1%} {f'[{lo:.1%}, {hi:.1%}]':>18} {secs[len(secs) // 2]:9.1f}  {dict(why) or '-'}")

    print("\nPaired difference in pass rate, per task (bootstrap 95% over tasks; tasks where the arms differ):")
    rng = random.Random(0)
    for i, a in enumerate(arms):
        for b in arms[i + 1:]:
            common = sorted(set(per[a]) & set(per[b]))
            if not common:
                continue
            diff = [sum(per[a][t]) / len(per[a][t]) - sum(per[b][t]) / len(per[b][t]) for t in common]
            boots = sorted(sum(rng.choice(diff) for _ in diff) / len(diff) for _ in range(2000))
            print(f"  {a:9} - {b:9} {sum(diff) / len(diff):+.3f}  [{boots[50]:+.3f}, {boots[1949]:+.3f}]  "
                  f"differ on {sum(d != 0 for d in diff)}/{len(diff)} tasks")

    print("\nThe pipeline's own LLM tester vs the hidden tests (pipeline arms only):")
    for a in arms:
        rs = [r for r in rows if r["arm"] == a and r["pipeline_verdict"]]
        if not rs:
            continue
        fp = sum(r["pipeline_verdict"] == "PASSED" and not r["passed"] for r in rs)
        fn = sum(r["pipeline_verdict"] == "FAILED" and r["passed"] for r in rs)
        say = sum(r["pipeline_verdict"] == "PASSED" for r in rs)
        print(f"  {a:9} says PASSED on {say}/{len(rs)}; of those, wrong (hidden tests fail): {fp};"
              f" says FAILED but code is correct: {fn}")

    print("\nOrchestration size (executable lines; prompts are shared and counted once):")
    cp = ROOT / "cookbook" / "code_pipeline"
    spl = Path("/home/papagame/projects/digital-duck/SPL.py/cookbook/050_code_pipeline/code_pipeline.spl")
    prompts = sum(loc(p) for p in sorted(cp.glob("0[0-7]_*.spl")))
    print(f"  graflang   {loc(cp / 'code_pipeline.graph.yaml')} lines of graph YAML")
    if spl.exists():
        print(f"  spl        {loc(spl)} lines of orchestrator .spl")
    print(f"  langgraph  {loc(Path(__file__).parent / 'lg_pipeline.py')} lines of Python (plus a pipeline-agnostic run harness)")
    print(f"  shared     {prompts} lines in the eight step .spl files (prompts, wrappers and file writes)")


if __name__ == "__main__":
    main(sys.argv[1:])
