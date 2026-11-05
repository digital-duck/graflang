"""What a part touches and costs, and the parent's rules about it (composability steps 4 and 5).

`capabilities(nodes)` reads the (already flattened) nodes of a part and lists what it can do to the world:

    read      files a QUERY reads            write    files an EMIT writes       email   recipients of an EMIT
    webhook   urls an EMIT posts to          stdout   an EMIT that prints        program a SOLVE `kernel`/`subprocess`, or a RUN
    llm_calls model calls one run makes (a loop counts its body once per iteration when `max_iterations` is a number; `llm_exact` is
              False when some count is unknown: an expression bound, a BATCH, a procedure)

The using graph may forbid kinds and cap the total in its header:

    workflow:
      parts_policy: {forbid: [email, webhook, program, write], max_llm_calls: 20}

`forbid` is checked for each use; `max_llm_calls` is the sum over every use (a part used twice counts twice). A violation is an error of
`graf validate` / `graf run`, before anything runs, and the same check guards a part a model adds with MUTATE `add_part`.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

KINDS = ("read", "write", "email", "webhook", "stdout", "program")


def _walk(nodes: List[Dict]):
    for n in nodes:
        yield n
        body = (n.get("config") or {}).get("subgraph")
        if isinstance(body, dict):
            yield from _walk(body.get("nodes", []))


def _calls(nodes: List[Dict]) -> tuple:
    total, exact = 0, True
    for n in nodes:
        cfg, t = n.get("config") or {}, n.get("type")
        if t == "GENERATE":
            total += 1
            if "procedure_ref" in cfg:
                exact = False
        elif t in ("LOOP", "BATCH"):
            body = cfg.get("subgraph") or {}
            inner, inner_exact = _calls(body.get("nodes", []))
            bound = cfg.get("max_iterations")
            if isinstance(bound, int) and not isinstance(bound, bool) and t == "LOOP":
                total += inner * bound
                exact = exact and inner_exact
            else:
                total += inner
                exact = exact and inner == 0
    return total, exact


def capabilities(nodes: List[Dict]) -> Dict[str, Any]:
    caps: Dict[str, Any] = {k: [] for k in KINDS}
    for n in _walk(nodes):
        cfg, t = n.get("config") or {}, n.get("type")
        if t == "QUERY":
            caps["read"].append(str(cfg.get("file", "(path from a port)")))
        elif t == "EMIT":
            ch = cfg.get("channel", "file")
            if ch == "file":
                caps["write"].append(str(cfg.get("file", "(path from a port)")))
            elif ch == "email":
                caps["email"] += [str(r) for r in cfg.get("recipients", [])] or ["(unset)"]
            elif ch == "webhook":
                caps["webhook"].append(str(cfg.get("url", "(unset)")))
            else:
                caps["stdout"].append("stdout")
        elif t == "RUN" or (t == "SOLVE" and cfg.get("backend") in ("kernel", "subprocess")):
            caps["program"].append(str(cfg.get("command") or cfg.get("executor") or cfg.get("backend") or "RUN"))
    caps["llm_calls"], caps["llm_exact"] = _calls(nodes)
    return caps


def suggested_cap(calls: int, margin: float = 0.5) -> int:
    """A `limits.max_llm_calls` for a run that makes `calls` model calls: the count plus a margin (default 50%), rounded up, never
    below calls + 1. The count is a static one (see `_calls`); the cap is what stops a retry loop that fires a node again and again."""
    import math
    return max(calls + 1, math.ceil(calls * (1 + margin)))


def used(caps: Dict[str, Any]) -> List[str]:
    return [k for k in KINDS if caps.get(k)]


def check_policy(caps: Dict[str, Any], policy: Optional[Dict], where: str, so_far: int = 0) -> int:
    """Raise ValueError if the part breaks the parent's `parts_policy`; return the running total of model calls."""
    total = so_far + int(caps.get("llm_calls", 0))
    if not policy:
        return total
    if not isinstance(policy, dict) or set(policy) - {"forbid", "max_llm_calls"}:
        raise ValueError("workflow.parts_policy takes forbid: [..] and max_llm_calls: N")
    bad = sorted(set(policy.get("forbid") or []) - set(KINDS))
    if bad:
        raise ValueError(f"workflow.parts_policy.forbid has {bad}; the kinds are {list(KINDS)}")
    hit = [k for k in policy.get("forbid") or [] if caps.get(k)]
    if hit:
        raise ValueError(f"{where}: the workflow's parts_policy forbids {hit}, which this part does ({', '.join(f'{k}: {caps[k]}' for k in hit)})")
    cap = policy.get("max_llm_calls")
    if cap is not None and total > int(cap):
        raise ValueError(f"{where}: parts together make {total}{'' if caps.get('llm_exact', True) else '+'} model calls, over parts_policy.max_llm_calls {cap}")
    return total


def describe(caps: Dict[str, Any]) -> str:
    bits = [f"{k}: {', '.join(caps[k])}" for k in KINDS if caps[k]]
    calls = f"up to {caps['llm_calls']}{'' if caps['llm_exact'] else '+'} model calls"
    return "; ".join([*bits, calls]) if bits else f"touches nothing outside; {calls}"


def part_summary(path, name: str = "") -> Dict[str, Any]:
    """The interface, capabilities and pin of the recipe whose graph file is `path` (for `graf parts`, Browse and catalogues)."""
    from pathlib import Path
    from .parts import _load_part, folder_hash
    path = Path(path)
    part = _load_part(path.resolve(), ())
    wf = part["workflow"]
    caps = capabilities(part["nodes"])
    return {"name": name or path.stem.removesuffix(".graph"), "file": str(path.resolve()), "hash": folder_hash(path.resolve().parent),
            "inputs": [{k: v for k, v in i.items() if k in ("name", "type", "default", "description")} for i in wf.get("inputs", [])],
            "outputs": [{k: v for k, v in o.items() if k in ("name", "type", "description", "schema")} for o in wf.get("outputs", [])],
            "capabilities": caps}


def use_snippet(ref: str, name: str, summary: Dict[str, Any]) -> str:
    """The text to paste into a compact workflow to use the recipe: its `resources.parts` entry and a `use` step."""
    ins = ", ".join(f"{i['name']}: $in.{i['name']}" for i in summary["inputs"] if "default" not in i)
    outs = ", ".join(o["name"] for o in summary["outputs"])
    return (f"resources:\n  parts:\n    {name}: \"{ref}@{summary['hash']}\"\n\nsteps:\n"
            f"  - {name}_1: {{use: parts.{name}, in: {{{ins}}}, out: [{outs}]}}\n")


def parts_report(graph_path) -> List[Dict[str, Any]]:
    """One entry per `SUBGRAPH` use in a workflow file (compact or long): the part, where it resolves, its pin, interface and capabilities."""
    from pathlib import Path
    from ruamel.yaml import YAML
    from .compact import expand as expand_compact, is_compact
    from .parts import part_file
    graph_path = Path(graph_path)
    data = YAML(typ="safe").load(graph_path.read_text(encoding="utf-8"))
    if is_compact(data):
        data = expand_compact(data)
    declared = (data.get("resources") or {}).get("parts") or {}
    rows = []
    for n in data.get("nodes", []):
        if n.get("type") != "SUBGRAPH":
            continue
        pname = str((n.get("config") or {}).get("part", "")).partition(".")[2]
        ref = declared.get(pname)
        if ref is None:
            continue
        file = part_file(ref, graph_path.parent)
        info = part_summary(file, pname)
        info.update(use=n["id"], ref=str(ref), pinned="@" in str(ref))
        rows.append(info)
    return rows
