"""Compact authoring form (design E3): `steps:` desugars to the `nodes:` / `edges:` the runtime runs.

    steps:
      - draft:    {generate: prompts.draft,    in: {topic: $in.topic}}
      - critique: {generate: prompts.critique, in: {essay: draft}}
      - refine:   {generate: prompts.refine,   in: {essay: draft, feedback: critique}, out: essay}
      - done:     {output: refine}

A step is a one-key mapping: the step id, then a mapping whose first key names the kind and gives its main argument.

  kind      argument                                  control ports (the one a following step hangs on is first)
  generate  prompts.<name> | prompt text              trigger  complete
  solve     expression                                trigger  complete
  assert    condition                                 trigger  pass  fail
  evaluate  condition                                 trigger  pass  fail
  guard     policies.<name>                           trigger  allow  deny
  fork      [branch names]                            trigger  <one port per branch>
  join      [step or step.port, ...] it waits for     trigger  complete
  output    a reference, or {workflow output: ref}    trigger  exit
  node      a node type (LOOP, MUTATE, ...)           trigger  complete   (plus any `ports:` given)
  use       parts.<name>, a part file (see parts.py)  trigger  complete   (`out:` must list the part's outputs you read)

Other keys of a step: `in` maps input names to values; `out` names the result port(s) (default `result`; a node's
first one is what a bare reference means); `on` says what triggers the step; every other key goes into the node's
`config` (model, phases, temperature, context_mapping, ...).

A value in `in` is a reference when it is `$in.<workflow input>`, a step id, or `<step id>.<out name>`; anything else is
a literal, which becomes the input's default (`phases.pre.defaults`). Wrap a literal that looks like a reference in
`{value: ...}`.

Control is inferred: the first step hangs on the workflow's entry, each next step on the default control port of the one
listed before it. A step with `on: step.port` (or a list of them) hangs there instead, which is how branches of
assert / evaluate / guard / fork are written. A step after a fork or after a step with `on` needs its own `on`
only if it should not follow the previous one. `nodes:` and `edges:` may sit beside `steps:` for anything the compact
form cannot say; they are added unchanged, and the steps may refer to those nodes as `node.out_name`.
`graf expand FILE` prints the long form.
"""
from __future__ import annotations

import copy
import re
from typing import Any, Dict, List, Optional, Tuple

ENTRY = "wf_entry"
KINDS = {
    "generate": ("trigger", "complete"), "solve": ("trigger", "complete"), "assert": ("trigger", "pass", "fail"),
    "evaluate": ("trigger", "pass", "fail"), "guard": ("trigger", "allow", "deny"), "join": ("trigger", "complete"),
    "output": ("trigger", "exit"), "fork": ("trigger",), "node": ("trigger", "complete"), "use": ("trigger", "complete"),
}
TYPES = {"generate": "GENERATE", "solve": "SOLVE", "assert": "ASSERT", "evaluate": "EVALUATE", "guard": "GUARD",
         "join": "JOIN", "output": "OUTPUT", "fork": "FORK", "use": "SUBGRAPH"}
RESERVED = {"in", "out", "on", "ports", "config"}
ID = re.compile(r"^[a-zA-Z0-9_]+$")


class CompactError(ValueError):
    pass


def is_compact(data: Any) -> bool:
    return isinstance(data, dict) and "steps" in data


def _kind(step_id: str, body: Dict) -> str:
    kinds = [k for k in body if k in KINDS]
    if len(kinds) != 1:
        raise CompactError(f"step {step_id!r}: needs exactly one of {sorted(KINDS)}, found {kinds or 'none'}")
    return kinds[0]


def expand(data: Dict) -> Dict:
    """The long form of a compact graph (a new dict; `data` is not changed)."""
    data = copy.deepcopy(data)
    steps = data.pop("steps")
    if not isinstance(steps, list) or not steps:
        raise CompactError("steps must be a non-empty list")
    wf = data.get("workflow")
    if not isinstance(wf, dict):
        raise CompactError("a compact graph still needs a `workflow:` block (name, inputs, outputs)")
    inputs = [i["name"] for i in wf.get("inputs", [])]
    outputs = [o["name"] for o in wf.get("outputs", [])]

    parsed: List[Tuple[str, str, Dict]] = []
    for item in steps:
        if not isinstance(item, dict) or len(item) != 1:
            raise CompactError(f"each step is a one-key mapping {{id: {{kind: ...}}}}, got {item!r}")
        (sid, body), = item.items()
        sid = str(sid)
        if not ID.match(sid):
            raise CompactError(f"step id {sid!r}: use letters, digits and underscores")
        if not isinstance(body, dict):
            raise CompactError(f"step {sid!r}: expected a mapping, got {body!r}")
        parsed.append((sid, _kind(sid, body), body))
    ids = [s for s, _, _ in parsed]
    if len(set(ids)) != len(ids) or ENTRY in ids:
        raise CompactError(f"step ids must be unique and not {ENTRY!r}: {ids}")

    outs: Dict[str, List[str]] = {}
    for sid, kind, body in parsed:
        o = body.get("out", ["result"])
        outs[sid] = [o] if isinstance(o, str) else list(o)

    nodes: List[Dict] = [{"id": ENTRY, "type": "INPUT", "ports": ["entry", *[f"out_{i}" for i in inputs]]}]
    edges: List[Dict] = []
    ctrl: Dict[str, List[str]] = {}                       # step -> its control ports, the default one first

    def ref(sid: str, value: Any) -> Optional[Tuple[str, str]]:
        """('node.out_port') a string refers to, or None if it is a literal."""
        if not isinstance(value, str):
            return None
        if value.startswith("$in."):
            name = value[4:]
            if name not in inputs:
                raise CompactError(f"step {sid!r}: {value} is not a workflow input (have {inputs})")
            return ENTRY, f"out_{name}"
        head, _, port = value.partition(".")
        if head in outs:
            if not port:
                return head, f"out_{outs[head][0]}"
            if port not in outs[head]:
                raise CompactError(f"step {sid!r}: {head!r} has no result {port!r} (it has {outs[head]}; name them with `out:`)")
            return head, f"out_{port}"
        return None

    def control(sid: str, value: str) -> str:
        head, _, port = str(value).partition(".")
        if head == "$in" or head == ENTRY:
            return f"{ENTRY}.entry"
        if head not in ctrl:
            raise CompactError(f"step {sid!r}: `on: {value}` names no earlier step")
        if port and port not in ctrl[head]:
            raise CompactError(f"step {sid!r}: {head!r} has no control port {port!r} (it has {ctrl[head][1:]})")
        return f"{head}.{port or ctrl[head][1]}"

    previous: Optional[str] = None
    for sid, kind, body in parsed:
        arg = body[kind]
        cfg: Dict[str, Any] = dict(body.get("config", {}))
        cfg.update({k: v for k, v in body.items() if k not in RESERVED and k != kind})
        node_type = str(arg).upper() if kind == "node" else TYPES[kind]
        ports = list(KINDS[kind])
        if kind == "generate":
            cfg["prompt_ref" if isinstance(arg, str) and re.fullmatch(r"prompts\.\w+", arg) else "prompt_inline"] = arg
        elif kind == "use":
            cfg["part"] = arg
            if "out" not in body:
                raise CompactError(f"step {sid!r}: `use` needs `out:`, the part's outputs you want to read")
        elif kind == "solve":
            cfg["expression"] = arg
        elif kind in ("assert", "evaluate"):
            cfg["condition"] = arg
        elif kind == "guard":
            cfg["policy_ref"] = arg
        elif kind == "fork":
            if not isinstance(arg, list) or not arg:
                raise CompactError(f"step {sid!r}: fork needs a list of branch names")
            ports += [str(b) for b in arg]
        elif kind == "node":
            ports = list(dict.fromkeys([*ports, *body.get("ports", [])]))
        if kind == "node":
            ports = [p for p in ports if not p.startswith(("in_", "out_"))]

        in_edges: List[Tuple[Tuple[str, str], str]] = []
        defaults: Dict[str, Any] = {}
        in_map = dict(body.get("in", {}))
        if kind == "output":
            single = arg if isinstance(arg, dict) else ({outputs[0]: arg} if len(outputs) == 1 else None)
            if single is None:
                raise CompactError(f"step {sid!r}: output needs {{workflow output: reference}} when the workflow has "
                                   f"{len(outputs)} outputs")
            in_map = {**single, **in_map}
        for name, value in in_map.items():
            if isinstance(value, dict) and set(value) == {"value"}:
                value, literal = value["value"], True
            else:
                literal = False
            target = ref(sid, value) if not literal else None
            port = f"in_{name}"
            ports.append(port)
            if target:
                in_edges.append((target, port))
            elif kind == "output":
                raise CompactError(f"step {sid!r}: output {name!r} needs a reference, got {value!r}")
            else:
                defaults[port] = value
        if kind == "join":
            sources = [control(sid, s) for s in arg]
            edges += [{"source": s, "target": f"{sid}.trigger", "type": "triggers"} for s in sources]
        if defaults:
            pre = cfg.setdefault("phases", {}).setdefault("pre", {})
            pre.setdefault("defaults", {}).update(defaults)
        if kind != "output":
            ports += [f"out_{o}" for o in outs[sid]]
        node = {"id": sid, "type": node_type, "ports": list(dict.fromkeys(ports))}
        if cfg:
            node["config"] = cfg
        nodes.append(node)
        ctrl[sid] = [p for p in node["ports"] if not p.startswith(("in_", "out_"))]

        for (src, port), tin in in_edges:
            edges.append({"source": f"{src}.{port}", "target": f"{sid}.{tin}", "type": "binds"})

        if kind == "join":
            pass
        elif "on" in body:
            for s in ([body["on"]] if isinstance(body["on"], str) else body["on"]):
                edges.append({"source": control(sid, s), "target": f"{sid}.trigger", "type": "triggers"})
        elif previous is None:
            edges.append({"source": f"{ENTRY}.entry", "target": f"{sid}.trigger", "type": "triggers"})
        else:
            prev_ctrl = ctrl[previous]
            if parsed_kind(parsed, previous) == "fork":
                raise CompactError(f"step {sid!r} follows the fork {previous!r}: give it `on: {previous}.<branch>`")
            edges.append({"source": f"{previous}.{prev_ctrl[1]}", "target": f"{sid}.trigger", "type": "triggers"})
        previous = sid

    out = {k: v for k, v in data.items() if k not in ("nodes", "edges")}
    out["nodes"] = nodes + list(data.get("nodes", []))
    out["edges"] = edges + list(data.get("edges", []))
    order = [k for k in ("version", "workflow", "resources", "nodes", "edges") if k in out]
    return {**{k: out[k] for k in order}, **{k: v for k, v in out.items() if k not in order}}


def parsed_kind(parsed: List[Tuple[str, str, Dict]], sid: str) -> str:
    return next(k for s, k, _ in parsed if s == sid)
