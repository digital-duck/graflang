"""HumanEval tasks (164 hand-written Python problems with hidden unit tests), downloaded once into data/ (git-ignored)."""
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
    """The text every arm receives as its spec: the HumanEval prompt (signature and docstring) and one instruction."""
    return INSTRUCTION + task["prompt"]
