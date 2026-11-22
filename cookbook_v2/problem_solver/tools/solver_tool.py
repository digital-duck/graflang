"""The deterministic part of the problem solver: the catalogue text, the interface of one solver, and the check of the inputs a model proposed
(a SOLVE node with backend: subprocess; `solvers.json` is the one place that lists the solvers and their inputs).

stdin   {"mode": "catalogue"}                                 -> {"text": the catalogue as the prompt shows it}
        {"mode": "interface", "solver": name}                 -> {"text": what the solver takes and gives}
        {"mode": "choice", "reply": the model's reply}        -> {"solver": name or "none", "reason": text}
        {"mode": "report", "answer", "solver", "reason", "why", "values"}  -> {"text": the final report}
        {"mode": "check", "solver": name, "reply": the model's reply with the inputs as JSON}
                                                              -> {"ok": true, "solver": name, "delta": the add_part delta (JSON text), "values": the inputs (JSON text)}
                                                              or {"ok": false, "error": what is wrong, in words a model can act on}
stdout  one line of JSON.

The delta wires each supplied input from `fields__<input>.out_value` (the `fields` composite holds one node per input name) and feeds the solver's
output to `report.in_answer`, after `pick.applied` and before `report.trigger`. The model never writes wiring: it names a solver and gives values.
"""
import json
import re
import sys
from pathlib import Path

SOLVERS = json.loads((Path(__file__).parent / "solvers.json").read_text())
FENCE = re.compile(r"\A\s*```[\w+-]*\n([\s\S]*?)\n?```\s*\Z")


def read_json(reply):
    """The first JSON object in a model's reply (fences and chatter around it are ignored); None when there is none."""
    text = str(reply).strip()
    m = FENCE.match(text)
    text = m.group(1) if m else text
    start = text.find("{")
    while start != -1:
        try:
            value, _ = json.JSONDecoder().raw_decode(text[start:])
            if isinstance(value, dict):
                return value
        except ValueError:
            pass
        start = text.find("{", start + 1)
    return None


def catalogue():
    lines = []
    for name, s in SOLVERS.items():
        takes = ", ".join(s["inputs"])
        lines.append(f"- {name}: {s['summary']} Use it for: {s['use_for']}. Takes: {takes}. Gives: {s['output']}.")
    return "\n".join(lines)


def interface(name):
    if name not in SOLVERS:
        return f"unknown solver {name!r}; the solvers are {', '.join(SOLVERS)}"
    s = SOLVERS[name]
    rows = [f"- {k} ({'required' if v['required'] else 'optional: leave it out unless the problem says it'}): {v['description']}" for k, v in s["inputs"].items()]
    return f"{name}: {s['summary']}\nInputs:\n" + "\n".join(rows)


def choice(reply):
    value = read_json(reply) or {}
    solver = str(value.get("solver", "none")).strip()
    if solver not in SOLVERS:
        solver = "none"
    return {"solver": solver, "reason": str(value.get("reason", "")).strip() or "(no reason given)"}


def check(name, reply):
    if name not in SOLVERS:
        return {"ok": False, "error": f"unknown solver {name!r}; the solvers are {', '.join(SOLVERS)}"}
    spec = SOLVERS[name]
    value = read_json(reply)
    if value is None:
        return {"ok": False, "error": "the reply has no JSON object; answer with one JSON object {\"input_name\": \"value\", ...} and nothing else"}
    inner = value.get("inputs")
    if isinstance(inner, dict):                          # {"inputs": {...}} is accepted as well
        value = inner
    extra = sorted(k for k in value if k not in spec["inputs"])
    if extra:
        return {"ok": False, "error": f"{', '.join(extra)}: not an input of {name}; its inputs are {', '.join(spec['inputs'])}"}
    values = {}
    for k, v in value.items():
        if isinstance(v, (dict, list)) or v is None:
            return {"ok": False, "error": f"{k}: give a plain value (text or a number), not {type(v).__name__}"}
        text = str(v).strip()
        if text != "":
            values[k] = text
    missing = [k for k, v in spec["inputs"].items() if v["required"] and k not in values]
    if missing:
        return {"ok": False, "error": f"{', '.join(missing)}: required by {name} and missing or empty; copy it from the problem"}
    delta = {"action": "add_part", "payload": {"id": "solver", "part": name, "after": "pick.applied", "before": "report.trigger",
                                               "binds": {k: f"fields__{k}.out_value" for k in values},
                                               "feeds": {spec["output"]: ["report.in_answer"]}}}
    return {"ok": True, "solver": name, "delta": json.dumps(delta), "values": json.dumps(values)}


def report(job):
    """The final text: the answer, headed by how it was made (a catalogue solver, or the model alone) and why."""
    answer, solver, why = str(job.get("answer", "")).strip(), str(job.get("solver", "")), str(job.get("why", "")).strip()
    if why:
        head = f"UNVERIFIED: answered by the model alone, no catalogue solver ran. {why}"
    else:
        reason = str(job.get("reason", "")).strip()
        given = job.get("values")
        if isinstance(given, str):
            try:
                given = json.loads(given)
            except ValueError:
                given = None
        given = ", ".join(f"{k}={str(v)[:60]!r}" for k, v in given.items()) if isinstance(given, dict) else ""
        head = f"SOLVED BY THE CATALOGUE SOLVER {solver}. Why: {reason}" + (f"\nInputs given to it: {given}" if given else "")
    return {"text": f"{head}\n\n{answer}"}


def main():
    job = json.loads(sys.stdin.read() or "{}")
    mode = job.get("mode")
    if mode == "catalogue":
        out = {"text": catalogue()}
    elif mode == "interface":
        out = {"text": interface(str(job.get("solver", "")))}
    elif mode == "choice":
        out = choice(job.get("reply", ""))
    elif mode == "check":
        out = check(str(job.get("solver", "")), job.get("reply", ""))
    elif mode == "report":
        out = report(job)
    else:
        out = {"error": f"unknown mode {mode!r}"}
    print(json.dumps(out))


if __name__ == "__main__":
    main()
