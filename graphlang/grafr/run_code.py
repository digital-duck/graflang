"""RUN_CODE: run the program text a step produced, and report what it printed.

    - id: run
      type: RUN_CODE
      config: {languages: [python, javascript], timeout: 10}      # which languages may run; seconds allowed
      ports: [trigger, complete, in_language, in_text, out_program, out_output, out_ran]

`in_text` is a model's reply or source code; `in_language` names the language. The code is the first fenced block of the text, or the whole
text when there is no block, and a text with no block is run only if it parses as a program (so prose, or the mock adapter's placeholder,
is not run as code). The program runs in a throwaway folder with an empty environment (only PATH), no input and a time limit. Python and
JavaScript (node) are supported; `languages` narrows that, and any other language is returned, not run. The node never fails the run: no
code, a language that is not allowed, a missing interpreter, a crash, a timeout all come back as a note on `out_output` with `out_ran` false.

It runs code a model wrote, so it is risky: `graf validate` requires a GUARD in front of it, its keys (`languages`, `timeout`) are code keys a
MUTATE can never set, and a delta cannot add it. No sandbox beyond that: a program can still read what the user can read. For stronger
isolation use a `subprocess` SOLVE with `container:`.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Tuple

FENCE = re.compile(r"```[ \t]*[\w+-]*[ \t]*\n(.*?)```", re.S)
RUNNERS = {"python": [sys.executable, "-I", "-c"], "javascript": ["node", "-e"]}
ALIASES = {"py": "python", "python3": "python", "js": "javascript", "node": "javascript"}
LIMIT, DEFAULT_TIMEOUT = 4000, 10


def code_of(text: str) -> Tuple[str, bool]:
    """(code, fenced): the first code block of a model reply, or the whole text when there is none."""
    m = FENCE.search(text)
    return ((m.group(1) if m else text).strip("\n") + "\n" if (m or text.strip()) else ""), bool(m)


def _parses(language: str, program: str, tmp: str, timeout: float) -> bool:
    if language == "python":
        try:
            compile(program, "<reply>", "exec")
            return True
        except (SyntaxError, ValueError):
            return False
    path = os.path.join(tmp, "check.js")
    with open(path, "w", encoding="utf-8") as f:
        f.write(program)
    try:
        return subprocess.run(["node", "--check", path], capture_output=True, timeout=timeout).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def run_code(language: str, text: str, allowed: List[str], timeout: float = DEFAULT_TIMEOUT) -> Dict[str, Any]:
    language = str(language).strip().lower()
    language = ALIASES.get(language, language)
    program, fenced = code_of(str(text))

    def say(output: str, ran: bool) -> Dict[str, Any]:
        return {"out_program": program, "out_output": output, "out_ran": ran, "_route": "complete"}

    if not program.strip():
        return say("(not run: no code to run)", False)
    if language not in RUNNERS or language not in allowed:
        return say(f"(not run: only {', '.join(sorted(set(allowed) & set(RUNNERS)))} are run, not {language or 'an unknown language'})", False)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            if not fenced and not _parses(language, program, tmp, timeout):
                return say(f"(not run: the reply has no code block and is not valid {language})", False)
            done = subprocess.run(RUNNERS[language] + [program], cwd=tmp, env={"PATH": os.environ.get("PATH", "")}, capture_output=True,
                                  text=True, timeout=timeout, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return say(f"(stopped: it ran longer than {timeout:g} seconds)", False)
    except OSError as e:
        return say(f"(not run: {e})", False)
    out = done.stdout[:LIMIT]
    if done.returncode != 0:
        return say((f"(it failed with exit code {done.returncode})\n" + out + done.stderr[:LIMIT]).strip(), False)
    return say(out.rstrip("\n"), True)


def run_code_node(node: Dict, in_data: Dict[str, Any]) -> Dict[str, Any]:
    cfg = node.get("config") or {}
    allowed = [ALIASES.get(str(x).lower(), str(x).lower()) for x in cfg.get("languages", sorted(RUNNERS))]
    res = run_code(in_data.get("in_language", ""), in_data.get("in_text", ""), allowed, float(cfg.get("timeout", DEFAULT_TIMEOUT)))
    return {k: v for k, v in res.items() if k == "_route" or k in node["ports"]}


def check_run_code(node: Dict) -> Tuple[List[str], List[str]]:
    cfg = node.get("config") or {}
    errors: List[str] = []
    ports = list(node["ports"])
    for k in cfg:
        if k not in ("languages", "timeout", "phases", "risky", "label"):
            errors.append(f"unknown key {k!r} (a RUN_CODE takes languages and timeout)")
    langs = cfg.get("languages")
    if langs is not None:
        if not isinstance(langs, list) or not langs or not all(isinstance(x, str) for x in langs):
            errors.append("languages must be a non-empty list of names")
        else:
            bad = [x for x in langs if ALIASES.get(x.lower(), x.lower()) not in RUNNERS]
            if bad:
                errors.append(f"languages {bad} cannot be run here (python and javascript can)")
    if "timeout" in cfg and (isinstance(cfg["timeout"], bool) or not isinstance(cfg["timeout"], (int, float)) or cfg["timeout"] <= 0):
        errors.append("timeout must be a positive number of seconds")
    for p in ("in_language", "in_text"):
        if p not in ports:
            errors.append(f"needs the port {p!r}")
    return errors, []
