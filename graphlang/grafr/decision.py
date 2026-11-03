"""DECISION: a step whose `exec` is a decision made by a person (design: docs/DEV/DESIGN/graflang-hitl.md).

    - id: approve
      type: DECISION
      config:
        question: "Send this digest to the whole team?"     # or an in_question port; in_context is shown under it
        answers: [yes, no]                                  # allowed answers; omit for free text
        default: no                                         # taken when nobody answers in time (one of `answers`)
        safe_default: true                                  # says the default is the safe answer: silences the validate warning
        timeout_s: 3600                                     # how long to wait at the terminal; omit to wait
        max_asks: 3                                         # asks again after an answer that is not allowed, then fails
      ports: [trigger, answered, timeout, in_question, in_context, out_answer, out_note, out_by]

How the answer arrives, in order: `graf run --answer approve=yes` (repeatable; for scripts, tests and CI), the terminal when there is one
(`answer` or `answer | a note`), the `default`. With none of them the run stops with a message saying so. The token leaves by `answered`
with `out_answer`, `out_note` and `out_by` (who answered: `--by`, else the user name; `default` when nobody did), or by `timeout` when
the wait ran out and the node has that port (then `out_answer` carries the default, if any). A timeout never approves by itself unless
the graph says so with `default`, and `graf validate` warns when a defaulted DECISION can reach a risky node. The answer is data: it is
never run, and a MUTATE can neither add, remove nor change a DECISION node. Only the interactive mode exists; a parked run (a pending
file, `graf answer`, resume) is designed but not built.
"""
from __future__ import annotations

import getpass
import select
import sys
from typing import Any, Callable, Dict, List, Optional, Tuple

DECIDERS = ("human",)
MODES = ("interactive",)
KEYS = {"question", "answers", "default", "safe_default", "timeout_s", "max_asks", "decider", "mode", "phases", "risky"}


class DecisionError(RuntimeError):
    pass


def check_decision(node: Dict) -> Tuple[List[str], List[str]]:
    cfg, ports = node.get("config") or {}, list(node["ports"]) if not isinstance(node["ports"], dict) else list(node["ports"])
    errors: List[str] = []
    for k in cfg:
        if k not in KEYS:
            errors.append(f"unknown key {k!r} (a DECISION takes {sorted(KEYS - {'phases', 'risky'})})")
    if cfg.get("decider", "human") not in DECIDERS:
        errors.append(f"decider {cfg.get('decider')!r}: only {list(DECIDERS)} exists")
    if cfg.get("mode", "interactive") not in MODES:
        errors.append(f"mode {cfg.get('mode')!r}: only {list(MODES)} is built (a parked run is designed, not built)")
    answers = cfg.get("answers")
    if answers is not None and (not isinstance(answers, list) or not answers or not all(isinstance(a, str) and a for a in answers)):
        errors.append("answers must be a non-empty list of strings (omit it for a free-text answer)")
    elif answers and cfg.get("default") is not None and str(cfg["default"]) not in answers:
        errors.append(f"default {cfg['default']!r} is not one of the answers {answers}")
    for key in ("timeout_s", "max_asks"):
        if key in cfg and (isinstance(cfg[key], bool) or not isinstance(cfg[key], (int, float)) or cfg[key] <= 0):
            errors.append(f"{key} must be a positive number")
    if "question" not in cfg and "in_question" not in ports:
        errors.append("needs a question: config.question or an in_question port")
    for p in ("answered",):
        if p not in ports:
            errors.append(f"needs the port {p!r}")
    if "timeout_s" in cfg and "timeout" not in ports and cfg.get("default") is None:
        errors.append("timeout_s without a default needs a 'timeout' port to route to (or give a default)")
    return errors, []


def _tty() -> bool:
    try:
        return sys.stdin.isatty()
    except (AttributeError, ValueError):
        return False


def _read(prompt: str, timeout_s: Optional[float]) -> Optional[str]:
    """One line from the terminal, or None when `timeout_s` passes first."""
    sys.stdout.write(prompt)
    sys.stdout.flush()
    if timeout_s is not None:
        ready, _, _ = select.select([sys.stdin], [], [], float(timeout_s))
        if not ready:
            sys.stdout.write("\n")
            return None
    line = sys.stdin.readline()
    if line == "":
        raise DecisionError("end of input while waiting for an answer")
    return line.rstrip("\n")


def _allowed(text: str, answers: Optional[List[str]]) -> Optional[str]:
    if not answers:
        return text.strip() or None
    low = {a.lower(): a for a in answers}
    return low.get(text.strip().lower())


def run_decision(node: Dict, in_data: Dict[str, Any], supplied: Dict[str, str], ask: Optional[Callable[[str, Optional[float]], Optional[str]]] = None,
                 by: Optional[str] = None) -> Dict[str, Any]:
    cfg = node.get("config") or {}
    nid, ports = node["id"], list(node["ports"])
    answers = [str(a) for a in cfg["answers"]] if cfg.get("answers") else None
    default = str(cfg["default"]) if cfg.get("default") is not None else None
    question = str(in_data.get("in_question") or cfg.get("question") or "")
    context = in_data.get("in_context")
    who = by or getpass.getuser()

    def done(answer: str, note: str, route: str, who_: str) -> Dict[str, Any]:
        res: Dict[str, Any] = {"_route": route}
        for port, value in (("out_answer", answer), ("out_note", note), ("out_by", who_)):
            if port in ports:
                res[port] = value
        return res

    if nid in supplied:
        got = _allowed(supplied[nid].partition("|")[0], answers)
        if got is None:
            raise DecisionError(f"DECISION {nid!r}: the supplied answer {supplied[nid]!r} is not one of {answers}")
        return done(got, supplied[nid].partition("|")[2].strip(), "answered", who)

    reader = ask or (_read if _tty() else None)
    if reader is None:
        if default is not None:
            return done(default, "", "answered", "default")
        raise DecisionError(f"DECISION {nid!r} needs a person: run it in a terminal, or give the answer with --answer {nid}=<answer>"
                            + (f" (one of {answers})" if answers else ""))

    text = question + (f"\n\n{context}\n" if context not in (None, "") else "")
    label = f" [{'/'.join(answers)}]" if answers else ""
    for _ in range(int(cfg.get("max_asks", 3))):
        line = reader(f"\n{text}\n{nid}{label}{' (add a note after |)' if True else ''}: ", cfg.get("timeout_s"))
        if line is None:                                           # nobody answered in time
            if "timeout" in ports and default is None:
                return {"_route": "timeout", **({"out_answer": ""} if "out_answer" in ports else {})}
            if default is not None:
                return done(default, "", "timeout" if "timeout" in ports else "answered", "default")
            raise DecisionError(f"DECISION {nid!r}: no answer within {cfg.get('timeout_s')}s and no default")
        got = _allowed(line.partition("|")[0], answers)
        if got is not None:
            return done(got, line.partition("|")[2].strip(), "answered", who)
        sys.stdout.write(f"  not an allowed answer; choose one of {answers}\n" if answers else "  an answer is needed\n")
    raise DecisionError(f"DECISION {nid!r}: no allowed answer after {cfg.get('max_asks', 3)} tries")


def default_warnings(nodes: List[Dict], edges: List[Dict], risky: Callable[[Dict], bool]) -> List[str]:
    """A DECISION with a `default` that can reach a risky node: the default is what happens when nobody answers."""
    by_id = {n["id"]: n for n in nodes}
    nxt: Dict[str, List[str]] = {}
    for e in edges:
        if e["type"] == "triggers":
            nxt.setdefault(e["source"].partition(".")[0], []).append(e["target"].partition(".")[0])
    out = []
    for n in nodes:
        if n["type"] != "DECISION" or (n.get("config") or {}).get("default") is None or (n.get("config") or {}).get("safe_default"):
            continue
        seen, stack = set(), list(nxt.get(n["id"], []))
        while stack:
            cur = stack.pop()
            if cur in seen or cur not in by_id:
                continue
            seen.add(cur)
            stack += nxt.get(cur, [])
        hit = sorted(i for i in seen if risky(by_id[i]))
        if hit:
            out.append(f"DECISION {n['id']!r} has a default and can reach the risky node(s) {hit}: if nobody answers, the default decides; "
                       "make sure it is the safe answer")
    return out
