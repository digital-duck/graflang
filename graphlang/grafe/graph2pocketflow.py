"""graph2pocketflow (`graf compile --lang pocketflow`): write a PocketFlow program from a GraphLang graph (``*.graph.yaml``), with no model.

A template compile of the part of GraphLang that PocketFlow can say: a line, a branch and a loop made of retry wires. The result is one Python file
that needs only `pocketflow` and `openai` (not graflang) and calls the model through the OpenAI client, so `OPENAI_BASE_URL`, `OPENAI_API_KEY` and
`LAB_MODEL` (the model name; default gpt-4o-mini) choose the endpoint.

How the graph maps:

  every node                   a PocketFlow `Node` class named after the node id; `prep` reads the node's `in_*` values, `exec` computes, `post` stores the
                               `out_*` value and returns the control port that fired (`complete`, `pass`, `fail`)
  data (`binds` edges)         keys of the shared store, `<node>.<out port>`; several writers to one input: the last one written wins, as in the runtime
  control (`triggers` edges)   `a - "port" >> b`; the workflow's entry edge names the `Flow(start=...)` node
  GENERATE                     the prompt text (a `prompt_ref` file or `prompt_inline`) with `{{in_x}}` filled in, sent to the model; the reply goes on the
                               first `out_*` port
  SOLVE (expression)           the expression, checked by GraphLang's own evaluator and written out as Python; only the whitelisted helper functions that
                               it names are copied into the file
  EVALUATE, ASSERT             the condition; the node returns `pass` or `fail`
  INPUT, OUTPUT                the values a run starts with and the values it returns (`run(inputs)` returns the OUTPUT nodes' `in_*` values by name);
                               an OUTPUT node becomes a class marked `boundary = True` so that tools reading the flow can leave it out

What it refuses, with the node ids in the message, because PocketFlow has no word for it here: FORK, JOIN, LOOP, BATCH (use retry wires), GUARD (Cedar),
MUTATE, DECISION, RUN_CODE, RUN, QUERY, EMIT, OBSERVE, CONTEXT, RECOVER, a SOLVE with a backend or a procedure, a GENERATE with a procedure, and a control
port that triggers more than one node. What it drops and lists as warnings: lifecycle phases, typed ports, a node's own `llm` choice, labels.
"""
from __future__ import annotations

import ast
import inspect
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

SUPPORTED = {"INPUT", "OUTPUT", "GENERATE", "SOLVE", "EVALUATE", "ASSERT"}
ENTRY = "wf_entry"

# the whitelisted functions of the expression language that can be written out as plain Python (json_get is copied from graflang's source)
_HELPERS = {
    "contains": "def contains(a, b):\n    if a is None:\n        return False\n    if isinstance(a, (list, tuple, set, dict)):\n        return b in a\n    return str(b) in str(a)",
    "startswith": "def startswith(a, b):\n    return str(a).startswith(str(b))",
    "endswith": "def endswith(a, b):\n    return str(a).endswith(str(b))",
    "lower": "def lower(a):\n    return str(a).lower()",
    "upper": "def upper(a):\n    return str(a).upper()",
    "strip": "def strip(a):\n    return str(a).strip()",
    "is_empty": "def is_empty(a):\n    return a is None or (hasattr(a, '__len__') and len(a) == 0)",
}
_BUILTINS = {"len", "abs", "min", "max", "int", "float", "str", "bool"}


class GraphToPocketFlowError(ValueError):
    """The graph cannot be written as a PocketFlow program."""


def _ident(s: str) -> str:
    return re.sub(r"\W", "_", s)


def _cls(node_id: str) -> str:
    return "".join(p[:1].upper() + p[1:] for p in re.split(r"[\W_]+", node_id) if p) or "Node"


def _json_get_source() -> str:
    from ..grafr import expr
    return inspect.getsource(expr._json_get).replace("def _json_get(", "def json_get(", 1)


def _python_expr(expr_text: str, where: str) -> Tuple[str, set]:
    """The expression as Python source over `_v_in_x` names, and the helper functions it calls."""
    from ..grafr import expr
    try:
        tree = expr.parse(expr_text)
    except expr.ExpressionError as e:
        raise GraphToPocketFlowError(f"{where}: {e}") from None
    funcs = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call)}
    unsupported = sorted(f for f in funcs if f not in _HELPERS and f not in _BUILTINS and f != "json_get")
    if unsupported:
        raise GraphToPocketFlowError(f"{where}: the function(s) {', '.join(unsupported)} have no PocketFlow form (f-strings, has_pii and latest are not compiled)")
    return ast.unparse(tree), funcs


def graph_to_pocketflow(graph: dict) -> Tuple[str, List[str]]:
    nodes = {n["id"]: n for n in graph["nodes"]}
    problems = [f"{i} ({n['type']})" for i, n in nodes.items() if n["type"] not in SUPPORTED]
    for i, n in nodes.items():
        cfg = n.get("config") or {}
        if n["type"] == "SOLVE" and "expression" not in cfg:
            problems.append(f"{i} (SOLVE with a backend or a procedure)")
        if n["type"] == "GENERATE" and "procedure_ref" in cfg:
            problems.append(f"{i} (GENERATE with a procedure)")
    if problems:
        raise GraphToPocketFlowError("PocketFlow has no form for: " + ", ".join(problems))

    warnings: List[str] = []
    sources: Dict[str, List[str]] = defaultdict(list)                    # "node.in_x" -> ["node.out_y", ...] in edge order
    wiring: Dict[Tuple[str, str], List[str]] = defaultdict(list)         # (node, control port) -> [target nodes]
    for e in graph["edges"]:
        if e.get("type") == "binds":
            sources[e["target"]].append(e["source"])
        elif e.get("type") == "triggers":
            (s, sp), (t, _) = str(e["source"]).split(".", 1), str(e["target"]).split(".", 1)
            wiring[(s, sp)].append(t)
    for (s, sp), targets in wiring.items():
        if len(targets) > 1:
            raise GraphToPocketFlowError(f"{s}.{sp} triggers {len(targets)} nodes ({', '.join(targets)}): PocketFlow has one successor per action")
    entry = wiring.get((ENTRY, "entry"))
    if not entry:
        raise GraphToPocketFlowError(f"no entry edge from {ENTRY}.entry")

    resources = graph.get("resources") or {}
    src_dir = Path(graph.get("_source_dir", "."))

    def prompt_of(nid, cfg) -> str:
        if "prompt_inline" in cfg:
            return cfg["prompt_inline"]
        kind, _, name = str(cfg.get("prompt_ref", "")).partition(".")
        rel = (resources.get(kind) or {}).get(name)
        if rel is None:
            raise GraphToPocketFlowError(f"{nid}: prompt {cfg.get('prompt_ref')!r} is not listed under resources")
        return (src_dir / rel).read_text(encoding="utf-8")

    helpers: set = set()
    classes: List[str] = []
    constants: List[str] = []
    for nid, n in nodes.items():
        cfg, ports = n.get("config") or {}, n.get("ports", [])
        if cfg.get("phases"):
            warnings.append(f"{nid}: lifecycle phases are dropped")
        if cfg.get("llm"):
            warnings.append(f"{nid}: the node's own llm choice ({cfg['llm']}) is dropped; every call uses LAB_MODEL")
        if n["type"] == "INPUT":
            continue
        in_ports = [p for p in ports if p.startswith("in_")]
        out_ports = [p for p in ports if p.startswith("out_")]
        gets = ",\n            ".join(f'"{p}": latest(shared, {sources.get(f"{nid}.{p}", [])!r})' for p in in_ports)
        prep = f"    def prep(self, shared):\n        return {{{gets}}}\n" if in_ports else "    def prep(self, shared):\n        return {}\n"
        key = f"{nid}.{out_ports[0]}" if out_ports else None
        c = _cls(nid)
        if n["type"] == "GENERATE":
            constants.append(f"PROMPT_{_ident(nid)} = {prompt_of(nid, cfg)!r}")
            body = (f"    def exec(self, v):\n        prompt = PROMPT_{_ident(nid)}\n        for k, val in v.items():\n"
                    f"            prompt = prompt.replace('{{{{' + k + '}}}}', prompt_text(val))\n        return call_llm(prompt)\n"
                    f"    def post(self, shared, prep_res, exec_res):\n"
                    + (f"        put(shared, {key!r}, exec_res)\n" if key else "") + "        return 'complete'\n")
        elif n["type"] == "SOLVE":
            text, used = _python_expr(cfg["expression"], f"{nid} expression")
            helpers |= used
            constants.append(f"EXPR_{_ident(nid)} = {text!r}")
            body = (f"    def exec(self, v):\n        return evaluate(EXPR_{_ident(nid)}, v)\n    def post(self, shared, prep_res, exec_res):\n"
                    + (f"        put(shared, {key!r}, exec_res)\n" if key else "") + "        return 'complete'\n")
        elif n["type"] in ("EVALUATE", "ASSERT"):
            if not cfg.get("condition"):
                raise GraphToPocketFlowError(f"{nid}: no condition")
            text, used = _python_expr(cfg["condition"], f"{nid} condition")
            helpers |= used
            constants.append(f"EXPR_{_ident(nid)} = {text!r}")
            body = (f"    def exec(self, v):\n        return bool(evaluate(EXPR_{_ident(nid)}, v))\n    def post(self, shared, prep_res, exec_res):\n"
                    f"        return 'pass' if exec_res else 'fail'\n")
        else:                                                              # OUTPUT
            body = ("    def exec(self, v):\n        return v\n    def post(self, shared, prep_res, exec_res):\n"
                    "        shared.setdefault('__outputs', {}).update({k[3:]: val for k, val in exec_res.items()})\n        return 'exit'\n")
        marker = "    boundary = True    # collects the workflow's outputs; not a step of the workflow itself\n" if n["type"] == "OUTPUT" else ""
        classes.append(f"class {c}(Node):\n{marker}{prep}{body}")

    inputs = [p for p in nodes.get(ENTRY, {}).get("ports", []) if p.startswith("out_")]
    wires = [f"    n_{_ident(s)} - {sp!r} >> n_{_ident(t)}" for (s, sp), (t,) in sorted(wiring.items()) if s != ENTRY]
    nodes_made = "\n".join(f"    n_{_ident(i)} = {_cls(i)}()" for i, n in nodes.items() if n["type"] != "INPUT")
    start = f"n_{_ident(entry[0])}"
    helper_src = "\n\n".join(([_json_get_source()] if "json_get" in helpers else []) + [_HELPERS[h] for h in sorted(helpers) if h in _HELPERS])
    funcs = ", ".join(f'"{f}": {f}' for f in sorted(helpers))
    name = graph.get("workflow", {}).get("name", "workflow")
    src = f'''"""PocketFlow program for the GraphLang workflow `{name}`, written by `graf compile --lang pocketflow`. Do not edit: change the graph and compile again.

Needs `pocketflow` and `openai`. The model is reached through the OpenAI client: set OPENAI_BASE_URL, OPENAI_API_KEY and LAB_MODEL.
    python {name}_pocketflow.py --param name=value ...
"""
import json
import os
import re
import sys

from openai import OpenAI
from pocketflow import Flow, Node

{chr(10).join(constants)}

{helper_src}

FUNCS = {{{funcs}}}


def call_llm(prompt):
    r = OpenAI().chat.completions.create(model=os.environ.get("LAB_MODEL", "gpt-4o-mini"), messages=[{{"role": "user", "content": prompt}}])
    return r.choices[0].message.content


def prompt_text(value):
    if value is None:
        return ""
    if isinstance(value, (list, tuple)) and all(isinstance(x, str) for x in value):
        return "\\n\\n".join(value)
    if isinstance(value, (list, tuple, dict)):
        return json.dumps(value, ensure_ascii=False, indent=2, default=str)
    return str(value)


def evaluate(expression, values):
    scope = {{"_v_" + k: v for k, v in values.items()}}
    return eval(expression, {{"__builtins__": {{}}}}, {{**FUNCS, **scope}})


def put(shared, key, value):
    shared[key] = value
    seq = shared.setdefault("__seq", {{}})
    shared["__n"] = shared.get("__n", 0) + 1
    seq[key] = shared["__n"]


def latest(shared, keys):
    """The value most recently written to any of `keys` (several writers to one input: the last one wins), or None."""
    seq = shared.get("__seq", {{}})
    present = [k for k in keys if k in seq]
    return shared[max(present, key=lambda k: seq[k])] if present else None


{chr(10).join(classes)}

def create_flow():
{nodes_made}
{chr(10).join(wires)}
    return Flow(start={start})


def run(inputs):
    shared = {{}}
    for k, v in inputs.items():
        put(shared, "{ENTRY}.out_" + k, v)
    create_flow().run(shared)
    return shared.get("__outputs", {{}})


if __name__ == "__main__":
    params = dict(a.split("=", 1) for a in sys.argv[1:] if "=" in a)
    print(json.dumps(run(params), ensure_ascii=False, indent=2, default=str))
'''
    ast.parse(src)                                                         # what is written must at least be Python
    return src, warnings
