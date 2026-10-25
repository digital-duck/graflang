"""Summarize the results: pass rate per arm with 95% intervals, paired differences, how often the pipeline's own
LLM "test" agrees with the hidden tests, cost in time, and orchestration size.

    python analyze.py results/experiment.db [--adapter A] [--model M] [--batch ID]
    python analyze.py results/old.jsonl            # rows written by an older run.py also work
    python analyze.py results/pilot.db results/pilot-gemma4.db   # two models: adds a side-by-side comparison

For ad hoc questions the database can be queried directly: sqlite3 results/experiment.db "SELECT * FROM arm_summary".
"""
from __future__ import annotations

import argparse
import ast
import difflib
import json
import math
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import store  # noqa: E402
import tasks as tasks_module  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def failure_kind(row: dict, entry_points: dict) -> str:
    """Why a run failed, in terms a reader can act on. `renamed` is the pipeline changing the function name the spec asked for."""
    if row["passed"]:
        return "pass"
    if row["status"] != "ok" and row["reason"] != "no_code":
        return "error"                      # the arm itself crashed or timed out before producing code
    reason = row["reason"]
    if reason == "no_code":
        return "no_code"
    if reason == "timeout":
        return "timeout"
    entry = entry_points.get(row["task"], "")
    if reason.startswith("NameError") and f"'{entry}'" in reason:
        return "renamed"
    if reason.startswith("AssertionError") or "failures=" in reason:
        return "wrong_answer"
    return "code_error"                     # a syntax error or an exception other than the above


def loc(path: Path) -> int:
    """Executable lines: not blank, not a comment (# or --)."""
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines()
               if line.strip() and not line.strip().startswith(("#", "--")))


def prompts_by_task() -> dict:
    return {t["task_id"]: t["prompt"] for t in tasks_module.load_all()}


def report(rows: list[dict]) -> None:
    """The summary for the rows of one adapter and model."""
    entry_points = {t["task_id"]: t["entry_point"] for t in tasks_module.load_all()}
    arms = sorted({r["arm"] for r in rows}, key=["single", "spl", "graflang", "langgraph"].index)
    per = {a: defaultdict(list) for a in arms}                       # arm -> task -> [passed per rep]
    for r in rows:
        per[r["arm"]][r["task"]].append(r["passed"])
    print(f"{len(rows)} runs, {len({r['task'] for r in rows})} tasks\n")
    print(f"{'arm':10} {'runs':>5} {'pass':>6} {'95% CI (Wilson)':>18} {'median s':>9}  failures")
    for a in arms:
        rs = [r for r in rows if r["arm"] == a]
        k = sum(r["passed"] for r in rs)
        lo, hi = wilson(k, len(rs))
        secs = sorted(r["seconds"] for r in rs)
        why = Counter(failure_kind(r, entry_points) for r in rs if not r["passed"])
        print(f"{a:10} {len(rs):5} {k / len(rs):6.1%} {f'[{lo:.1%}, {hi:.1%}]':>18} {secs[len(secs) // 2]:9.1f}  {dict(why) or '-'}")
    print("  failure kinds: renamed = the function name from the spec is missing; wrong_answer = a hidden test failed;"
          " code_error = syntax error or crash;\n  no_code, timeout, error = nothing to score")

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

    print("\nCycles used by the pipeline (generate, review, improve, test; the limit is 3):")
    for a in arms:
        cyc = [r["cycles"] for r in rows if r["arm"] == a and r["cycles"]]
        if a == "single" or not cyc:
            continue
        print(f"  {a:9} mean {sum(cyc) / len(cyc):.2f} over {len(cyc)} runs; "
              f"{'  '.join(f'{c} cycle(s): {cyc.count(c)}' for c in sorted(set(cyc)))}")

    report_extras(rows, arms, entry_points, prompts_by_task())

    print("\nThe pipeline's own LLM tester vs the hidden tests, cycle by cycle (pipeline arms only):")
    for a in arms:
        if a == "single":
            continue
        cycles = [c for r in rows if r["arm"] == a and r.get("cycles_detail") for c in json.loads(r["cycles_detail"])
                  if c["verdict"]]
        if not cycles:
            continue
        say_pass = [c for c in cycles if c["verdict"] == "PASSED"]
        say_fail = [c for c in cycles if c["verdict"] == "FAILED"]
        false_pass = sum(not c["hidden_passed"] for c in say_pass)
        false_fail = sum(c["hidden_passed"] for c in say_fail)
        print(f"  {a:9} {len(cycles)} cycles: says PASSED {len(say_pass)} (hidden tests fail on {false_pass});"
              f" says FAILED {len(say_fail)} (hidden tests pass on {false_fail})")



EQUIVALENCE_MARGIN = 0.10      # pre-specified: two arms are equivalent if their pass rates differ by less than 10 points
EQUIVALENCE_ALPHA = 0.05


def _phi(z: float) -> float:
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def tost_paired(b: int, c: int, n: int, margin: float = EQUIVALENCE_MARGIN) -> tuple[float, float]:
    """Paired equivalence test (two one-sided tests) for a difference in pass rates.

    b = tasks only the first arm passed, c = only the second, n = tasks compared. The difference d = (b - c) / n, with the
    variance of a paired difference of proportions (Newcombe). H0: |d| >= margin; H1: |d| < margin. Returns (d, p) where p
    is the larger of the two one-sided p-values; equivalence is claimed when p < EQUIVALENCE_ALPHA."""
    if n == 0:
        return 0.0, 1.0
    d = (b - c) / n
    var = (b + c) / n ** 2 - (b - c) ** 2 / n ** 3
    if var <= 0:
        return d, 0.0 if abs(d) < margin else 1.0
    se = math.sqrt(var)
    p_lower = 1 - _phi((d + margin) / se)           # tests d > -margin
    p_upper = _phi((d - margin) / se)               # tests d < +margin
    return d, max(p_lower, p_upper)


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar test on the discordant pairs: b tasks only the first arm passed, c only the second."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def code_hygiene(code: str, prompt: str, entry: str) -> dict | None:
    """Objective properties of the code an arm returned, judged without the hidden tests."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None
    want = [a.arg for f in ast.parse(prompt).body if isinstance(f, ast.FunctionDef) and f.name == entry for a in f.args.args]
    got_fn = [f for f in tree.body if isinstance(f, ast.FunctionDef) and f.name == entry]
    main = other = 0
    unittest_use = False
    for node in tree.body:
        if isinstance(node, ast.If) and "__name__" in ast.dump(node.test):
            main += 1
            continue
        if isinstance(node, (ast.Import, ast.ImportFrom)) and any(a.name.split(".")[0] == "unittest" for a in getattr(node, "names", [])):
            unittest_use = True
        if isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            unittest_use = True
        if not isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.ClassDef, ast.Assign, ast.AnnAssign)):
            other += 1
    prints = sum(isinstance(n, ast.Call) and getattr(n.func, "id", "") == "print" for n in ast.walk(tree))
    self_tests = any(isinstance(node, ast.If) and "__name__" in ast.dump(node.test) and
                     any(isinstance(n, ast.Assert) or (isinstance(n, ast.Call) and "test" in ast.dump(n.func).lower())
                         for n in ast.walk(node))
                     for node in tree.body)
    return {"name_ok": bool(got_fn), "args_ok": bool(got_fn) and [a.arg for a in got_fn[0].args.args] == want,
            "main_block": bool(main), "self_tests": self_tests, "unittest": unittest_use, "other_top_level": other, "prints": prints,
            "loc": sum(1 for line in code.splitlines() if line.strip() and not line.strip().startswith("#"))}


def report_extras(rows: list[dict], arms: list[str], entry_points: dict, prompts: dict) -> None:
    """The analyses that go beyond pass/fail: partial correctness, trajectories, cost, code hygiene, paired tests, consistency,
    similarity of the code, and reliability. Each one says what it measures in its heading."""
    by_arm = {a: [r for r in rows if r["arm"] == a] for a in arms}

    print("\n1. Partial correctness: share of the hidden assertions that held (a near miss has most of them)")
    for a in arms:
        rs = [r for r in by_arm[a] if r.get("assert_total")]
        if not rs:
            print(f"  {a:9} no assertion counts (runs made before the scorer counted them)")
            continue
        frac = [r["assert_passed"] / r["assert_total"] for r in rs]
        near = sum(1 for r, f in zip(rs, frac) if not r["passed"] and f >= 0.8)
        nothing = sum(1 for r in by_arm[a] if not r.get("assert_total"))
        print(f"  {a:9} mean {sum(frac) / len(frac):6.1%} over {len(rs)} runs; failed runs with >= 80% of assertions: {near};"
              f" runs where no assertion ran (missing function, crash): {nothing}")

    print("\n2. Trajectory across cycles (hidden tests, scored on each cycle's code; pipeline arms only)")
    for a in arms:
        if a == "single":
            continue
        traj = [(r, json.loads(r["cycles_detail"])) for r in by_arm[a] if r.get("cycles_detail")]
        traj = [(r, d) for r, d in traj if d]
        if not traj:
            print(f"  {a:9} no per-cycle data")
            continue
        first = sum(d[0]["hidden_passed"] for _, d in traj)
        fixed = sum(1 for _, d in traj if not d[0]["hidden_passed"] and any(c["hidden_passed"] for c in d[1:]))
        never = sum(1 for _, d in traj if not any(c["hidden_passed"] for c in d))
        broke = sum(1 for _, d in traj if any(c["hidden_passed"] for c in d[:-1]) and not d[-1]["hidden_passed"])
        depth = Counter(len(d) for _, d in traj)
        per_cycle = defaultdict(lambda: [0, 0])
        for _, d in traj:
            for c in d:
                per_cycle[c["cycle"]][0] += c["hidden_passed"]
                per_cycle[c["cycle"]][1] += 1
        cyc_txt = "  ".join(f"cycle {k}: {v[0]}/{v[1]} pass" for k, v in sorted(per_cycle.items()))
        print(f"  {a:9} of {len(traj)} runs: passes on cycle 1 {first}; fixed by a retry {fixed}; never passes {never};"
              f" passed then ended failing {broke}; runs by depth {dict(sorted(depth.items()))}")
        print(f"            {cyc_txt}")
        wasted = sum(1 for _, d in traj for c in d[:-1] if c["hidden_passed"] and c["verdict"] == "FAILED")
        print(f"            retries after a cycle the hidden tests accept: {wasted} (the tester said FAILED on correct code)")

    print("\n3. Cost: LLM calls and tokens (estimated as characters / 4, the same for every arm)")
    for a in arms:
        rs = [r for r in by_arm[a] if r.get("llm_calls") is not None]
        if not rs:
            print(f"  {a:9} no call counts")
            continue
        passes = sum(r["passed"] for r in rs)
        tokens = sum((r["prompt_tokens"] or 0) + (r["output_tokens"] or 0) for r in rs)
        calls = sum(r["llm_calls"] for r in rs) / len(rs)
        per_pass = f"{tokens / passes:,.0f}" if passes else "n/a"
        print(f"  {a:9} mean {calls:5.1f} calls and {tokens / len(rs):8,.0f} tokens per run; tokens per passing run: {per_pass};"
              f" run seconds per LLM call {sum(r['seconds'] for r in rs) / max(1, sum(r['llm_calls'] for r in rs)):.1f}")

    print("\n4. Code hygiene of the final code (judged without the hidden tests; each figure is the share of runs)")
    for a in arms:
        checks = [code_hygiene(r["code"] or "", prompts[r["task"]], entry_points[r["task"]]) for r in by_arm[a]]
        checks = [c for c in checks if c]
        if not checks:
            print(f"  {a:9} no code that parses")
            continue
        n = len(checks)
        share = lambda key: sum(bool(c[key]) for c in checks) / n
        print(f"  {a:9} function name from the spec present {share('name_ok'):.0%}; argument names match {share('args_ok'):.0%}; self-tests under __main__ {share('self_tests'):.0%};"
              f" unittest code {share('unittest'):.0%}; other top-level statements {sum(c['other_top_level'] > 0 for c in checks) / n:.0%};"
              f" prints {sum(c['prints'] > 0 for c in checks) / n:.0%}; mean LOC {sum(c['loc'] for c in checks) / n:.0f}")

    print("\n5. Paired exact McNemar test on the same tasks (b = only the first arm passed, c = only the second)")
    for i, a in enumerate(arms):
        for b_arm in arms[i + 1:]:
            pa = {r["task"]: r["passed"] for r in by_arm[a]}
            pb = {r["task"]: r["passed"] for r in by_arm[b_arm]}
            common = set(pa) & set(pb)
            b = sum(pa[t] and not pb[t] for t in common)
            c = sum(pb[t] and not pa[t] for t in common)
            if not common:
                continue
            print(f"  {a:9} vs {b_arm:9} b={b} c={c} p={mcnemar_exact(b, c):.3f} (n={len(common)} tasks)")

    print("\n6. Consistency across repetitions (tasks with two or more runs for an arm)")
    any_reps = False
    for a in arms:
        groups = defaultdict(list)
        for r in by_arm[a]:
            groups[r["task"]].append(r["passed"])
        multi = {t: v for t, v in groups.items() if len(v) >= 2}
        if not multi:
            continue
        any_reps = True
        same = sum(len(set(v)) == 1 for v in multi.values())
        print(f"  {a:9} {same}/{len(multi)} tasks gave the same verdict every time")
    if not any_reps:
        print("  not measurable yet: every (task, arm) has one run (use --reps 2 or more)")

    print("\n7. Similarity of the final code between arms (difflib ratio, 1 = identical; mean over tasks)")
    for i, a in enumerate(arms):
        for b_arm in arms[i + 1:]:
            ca = {r["task"]: r["code"] or "" for r in by_arm[a]}
            cb = {r["task"]: r["code"] or "" for r in by_arm[b_arm]}
            common = [t for t in ca if t in cb and ca[t] and cb[t]]
            if not common:
                continue
            ratios = [difflib.SequenceMatcher(None, ca[t], cb[t]).ratio() for t in common]
            print(f"  {a:9} vs {b_arm:9} {sum(ratios) / len(ratios):.2f}  over {len(common)} tasks")

    print("\n8. Reliability (runs that did not finish cleanly)")
    for a in arms:
        rs = by_arm[a]
        bad = [r for r in rs if (r["status"] or "").startswith("error")]
        none = [r for r in rs if r["status"] == "no_code"]
        timeouts = [r for r in rs if r["reason"] == "timeout"]
        print(f"  {a:9} errors {len(bad)}; no code {len(none)}; timeouts {len(timeouts)}; of {len(rs)} runs")

    print("\n9. Pass rate by complexity group (tercile of the reference solution's branch count; the pre-specified breakdown)")
    groups = tasks_module.complexity_groups()
    cuts = tasks_module.cut_points()
    print(f"  groups by branch count: low <= {cuts['low_max']}, medium {cuts['medium_from']}-{cuts['medium_max']}, high >= {cuts['high_from']}"
          " (ties split by line count; see tasks.py)")
    tasks_seen = {r["task"] for r in rows}
    for g in ("low", "medium", "high"):
        in_group = {t for t in tasks_seen if groups.get(t) == g}
        if not in_group:
            continue
        cells = []
        for a in arms:
            rs = [r for r in by_arm[a] if groups.get(r["task"]) == g]
            if rs:
                cells.append(f"{a} {sum(r['passed'] for r in rs)}/{len(rs)}")
        print(f"  {g:7} ({len(in_group)} tasks): " + "; ".join(cells))

    print(f"\n10. Equivalence (paired TOST, margin ±{EQUIVALENCE_MARGIN:.0%}, alpha {EQUIVALENCE_ALPHA}): an arm pair is"
          " equivalent when p < alpha; 'not shown' is not evidence of a difference")
    for i, a in enumerate(arms):
        for b_arm in arms[i + 1:]:
            pa = {r["task"]: r["passed"] for r in by_arm[a]}
            pb = {r["task"]: r["passed"] for r in by_arm[b_arm]}
            common = set(pa) & set(pb)
            if not common:
                continue
            b = sum(pa[t] and not pb[t] for t in common)
            c = sum(pb[t] and not pa[t] for t in common)
            d, p = tost_paired(b, c, len(common))
            verdict = "EQUIVALENT" if p < EQUIVALENCE_ALPHA else "not shown equivalent"
            print(f"  {a:9} vs {b_arm:9} difference {d:+.1%} (n={len(common)}): TOST p={p:.3f}  -> {verdict}")


def compare_models(rows: list[dict]) -> None:
    """Side by side: one line per arm and model, then the tasks on which two models disagree for the same arm."""
    labels = sorted({f"{r['adapter']}/{r['model']}" for r in rows})
    arms = sorted({r["arm"] for r in rows}, key=["single", "spl", "graflang", "langgraph"].index)
    tasks = sorted({r["task"] for r in rows}, key=lambda t: int(t.split("/")[1]))
    print(f"\n{'=' * 20} comparison: {' vs '.join(labels)} {'=' * 20}")
    print(f"{'arm':10} {'model':34} {'runs':>4} {'pass':>5} {'partial':>8} {'cycles':>6} {'calls':>6} {'tokens/run':>11} {'sec/run':>8}")
    for a in arms:
        for label in labels:
            rs = [r for r in rows if r["arm"] == a and f"{r['adapter']}/{r['model']}" == label]
            if not rs:
                continue
            passed = sum(r["passed"] for r in rs) / len(rs)
            fracs = [r["assert_passed"] / r["assert_total"] for r in rs if r.get("assert_total")]
            partial = f"{sum(fracs) / len(fracs):.0%}" if fracs else "n/a"
            cyc = sum(r["cycles"] or 0 for r in rs) / len(rs)
            calls = [r["llm_calls"] for r in rs if r.get("llm_calls") is not None]
            tok = [(r["prompt_tokens"] or 0) + (r["output_tokens"] or 0) for r in rs if r.get("llm_calls") is not None]
            print(f"{a:10} {label:34} {len(rs):4} {passed:5.0%} {partial:>8} {cyc:6.1f} "
                  f"{(f'{sum(calls) / len(calls):.1f}' if calls else 'n/a'):>6} "
                  f"{(f'{sum(tok) / len(tok):,.0f}' if tok else 'n/a'):>11} {sum(r['seconds'] for r in rs) / len(rs):8.1f}")
    print("\nTasks where the two models disagree on pass/fail, same arm:")
    for a in arms:
        for i, la in enumerate(labels):
            for lb in labels[i + 1:]:
                pa = {r["task"]: r["passed"] for r in rows if r["arm"] == a and f"{r['adapter']}/{r['model']}" == la}
                pb = {r["task"]: r["passed"] for r in rows if r["arm"] == a and f"{r['adapter']}/{r['model']}" == lb}
                common = sorted(set(pa) & set(pb), key=lambda t: int(t.split("/")[1]))
                if not common:
                    continue
                diff = [t.split("/")[1] for t in common if pa[t] != pb[t]]
                print(f"  {a:10} {la} vs {lb}: {len(diff)}/{len(common)} differ"
                      + (f" (tasks {', '.join(diff)})" if diff else ""))
    print("\nThe pilot sampled the same tasks for every model; a difference on one task says little, check the code.")


def main(paths: list[str], model: str | None = None, batch: str | None = None, adapter: str | None = None) -> None:
    rows = [r for p in paths for r in store.load_rows(p, model, batch, adapter)]
    for adapter_name, model_name in sorted({(r["adapter"], r["model"]) for r in rows}):
        print(f"{'=' * 20} adapter: {adapter_name}  model: {model_name} {'=' * 20}")
        report([r for r in rows if (r["adapter"], r["model"]) == (adapter_name, model_name)])
        print()
    if len({(r["adapter"], r["model"]) for r in rows}) > 1:
        compare_models(rows)
    sizes()


def sizes() -> None:
    print("Orchestration size (executable lines; prompts are shared and counted once):")
    cp = ROOT / "cookbook" / "code_pipeline"
    spl = Path("/home/papagame/projects/digital-duck/SPL.py/cookbook/050_code_pipeline/code_pipeline.spl")
    prompts = sum(loc(p) for p in sorted(cp.glob("0[0-7]_*.spl")))
    print(f"  graflang   {loc(cp / 'code_pipeline.graph.yaml')} lines of graph YAML")
    if spl.exists():
        print(f"  spl        {loc(spl)} lines of orchestrator .spl")
    print(f"  langgraph  {loc(Path(__file__).parent / 'lg_pipeline.py')} lines of Python (plus a pipeline-agnostic run harness)")
    print(f"  shared     {prompts} lines in the eight step .spl files (prompts, wrappers and file writes)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+", help="a .db file (or an older .jsonl)")
    ap.add_argument("--adapter", help="only this adapter (claude_cli, ollama, ...)")
    ap.add_argument("--model", help="only this model")
    ap.add_argument("--batch", help="only this batch id (a row of the `batches` table)")
    ns = ap.parse_args()
    main(ns.paths, ns.model, ns.batch, ns.adapter)
