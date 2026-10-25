"""HumanEval tasks (164 hand-written Python problems with hidden unit tests), read from data/ (source and license in data/README.md)."""
from __future__ import annotations

import gzip
import json
import random
import urllib.request
from pathlib import Path

URL = "https://raw.githubusercontent.com/openai/human-eval/master/data/HumanEval.jsonl.gz"
DATA = Path(__file__).parent / "data" / "HumanEval.jsonl.gz"

INSTRUCTION = ("Implement the following Python function. Return the complete function, including its signature and any "
               "imports it needs.\n\n")


def load_all() -> list[dict]:
    if not DATA.exists():
        DATA.parent.mkdir(parents=True, exist_ok=True)
        DATA.write_bytes(urllib.request.urlopen(URL, timeout=30).read())
    with gzip.open(DATA, "rt", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def sample(n: int | None, seed: int = 0) -> list[dict]:
    """A fixed random sample (the same for every arm and every run), or all tasks when n is None."""
    tasks = load_all()
    if n is None or n >= len(tasks):
        return tasks
    return sorted(random.Random(seed).sample(tasks, n), key=lambda t: int(t["task_id"].split("/")[1]))


def spec_for(task: dict) -> str:
    """The text every arm receives as its spec: the HumanEval prompt (signature and docstring) and one instruction.
    Trailing whitespace is removed: SPL.py strips a parameter's value and GraphLang does not, so without this the two
    arms were given different inputs (one extra blank line in every prompt that carries the spec)."""
    return (INSTRUCTION + task["prompt"]).rstrip()


def select(n: int | None, seed: int = 0, ids: str | None = None) -> list[dict]:
    """The tasks to run: exactly the listed ones (`98,107` or `HumanEval/98`), else the fixed sample of n, else all."""
    if not ids:
        return sample(n, seed)
    by_id = {t["task_id"]: t for t in load_all()}
    chosen = []
    for raw in (x.strip() for x in ids.split(",") if x.strip()):
        key = raw if "/" in raw else f"HumanEval/{raw}"
        if key not in by_id:
            raise ValueError(f"no such task {raw!r} (HumanEval/0 to HumanEval/{len(by_id) - 1})")
        chosen.append(by_id[key])
    return chosen


# ---- complexity groups -------------------------------------------------------------------------------------------------
# HumanEval has no difficulty labels, so complexity is a proxy computed from the reference solution: the number of branch
# and loop constructs (if, for, while, conditional expressions, try, boolean operators, comprehensions) in the prompt plus
# the canonical solution, plus one. Ties are common (the median is 3), so the split is by rank, not by value: sort on
# (branches, lines, task number) and cut into thirds. The cut points are reported with the results, not assumed.

import ast

_BRANCHES = (ast.If, ast.For, ast.While, ast.IfExp, ast.Try, ast.BoolOp, ast.comprehension)


def complexity(task: dict) -> dict:
    """{'branches': int, 'lines': int} for one task (lines = non-blank lines of the canonical solution)."""
    try:
        tree = ast.parse(task["prompt"] + task["canonical_solution"])
        branches = sum(isinstance(n, _BRANCHES) for n in ast.walk(tree)) + 1
    except SyntaxError:
        branches = 0
    lines = sum(1 for line in task["canonical_solution"].splitlines() if line.strip())
    return {"branches": branches, "lines": lines}


def complexity_groups() -> dict:
    """{task_id: 'low' | 'medium' | 'high'}, split into thirds by rank over all 164 tasks (deterministic)."""
    tasks_sorted = sorted(load_all(), key=lambda t: (complexity(t)["branches"], complexity(t)["lines"],
                                                    int(t["task_id"].split("/")[1])))
    n = len(tasks_sorted)
    return {t["task_id"]: ("low", "medium", "high")[min(2, 3 * i // n)] for i, t in enumerate(tasks_sorted)}


def cut_points() -> dict:
    """The branch counts at which each group starts, for reporting: {'medium_from': x, 'high_from': y}."""
    groups = complexity_groups()
    by_id = {t["task_id"]: t for t in load_all()}
    branches = {g: sorted(complexity(by_id[tid])["branches"] for tid, gg in groups.items() if gg == g)
                for g in ("low", "medium", "high")}
    return {"low_max": branches["low"][-1], "medium_from": branches["medium"][0], "medium_max": branches["medium"][-1],
            "high_from": branches["high"][0]}


def stratified_sample(per_group: int, seed: int = 0) -> list[dict]:
    """A fixed random sample of `per_group` tasks from each complexity group (the same for every arm and run)."""
    groups = complexity_groups()
    by_id = {t["task_id"]: t for t in load_all()}
    chosen = []
    for g in ("low", "medium", "high"):
        ids = sorted((tid for tid, gg in groups.items() if gg == g), key=lambda x: int(x.split("/")[1]))
        picked = random.Random(f"{seed}/{g}").sample(ids, min(per_group, len(ids)))
        chosen += [by_id[tid] for tid in picked]
    return sorted(chosen, key=lambda t: int(t["task_id"].split("/")[1]))
