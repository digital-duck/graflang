"""Static checks on a loaded GraphLang graph: wiring, resources and conditions, without running it.

`check(graph_data)` returns (errors, warnings). Errors are things that would fail or misbehave at run
time; warnings are suspicious but allowed (an input nothing feeds, a node nothing triggers).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from .expr import ExpressionError, variables
from .resolver import ResourceResolver, SUFFIX

CONTROL_EXCLUDED = ("in_", "out_")


def _control_ports(node: Dict) -> List[str]:
    return [p for p in node["ports"] if p != "trigger" and not p.startswith(CONTROL_EXCLUDED)]


def _check_condition(where: str, expr: str, known: Set[str], errors: List[str]) -> None:
    try:
        unknown = variables(expr) - known
    except ExpressionError as e:
        errors.append(f"{where}: {e}")
        return
    if unknown:
        errors.append(f"{where}: condition uses {sorted('@' + u for u in unknown)}, which is not available "
                      f"(available: {sorted('@' + k for k in known)})")


def _check_scope(nodes: List[Dict], edges: List[Dict], prefix: str, resolver: ResourceResolver,
                 loop_vars: Set[str], boundary: Set[str], errors: List[str], warnings: List[str]) -> None:
    by_id: Dict[str, Dict] = {}
    for n in nodes:
        if n["id"] in by_id:
            errors.append(f"{prefix}duplicate node id {n['id']!r}")
        by_id[n["id"]] = n

    triggered: Set[str] = set()
    fed: Set[Tuple[str, str]] = set()
    for e in edges:
        ends = []
        for side in ("source", "target"):
            node, _, port = e[side].partition(".")
            if node not in by_id:
                errors.append(f"{prefix}edge {e['source']} -> {e['target']}: no node {node!r}")
            elif port not in by_id[node]["ports"]:
                errors.append(f"{prefix}edge {e['source']} -> {e['target']}: node {node!r} has no port {port!r}")
            else:
                ends.append((node, port))
        if len(ends) != 2:
            continue
        (src, sport), (tgt, tport) = ends
        if e["type"] == "triggers":
            if sport == "trigger" or sport.startswith(CONTROL_EXCLUDED):
                errors.append(f"{prefix}{e['source']} -> {e['target']}: a triggers edge must leave a control port, not {sport!r}")
            if tport != "trigger":
                errors.append(f"{prefix}{e['source']} -> {e['target']}: a triggers edge must end at a trigger port, not {tport!r}")
            triggered.add(tgt)
        else:
            if not sport.startswith("out_") or not tport.startswith("in_"):
                errors.append(f"{prefix}{e['source']} -> {e['target']}: a binds edge goes from an out_ port to an in_ port")
            fed.add((tgt, tport))

    for n in nodes:
        nid, typ, cfg = n["id"], n["type"], n.get("config", {})
        where = f"{prefix}{typ} {nid!r}"
        in_ports = {p for p in n["ports"] if p.startswith("in_")}
        for ref_key, kind in (("prompt_ref", "prompts"), ("procedure_ref", "procedures"), ("policy_ref", "policies")):
            if ref_key in cfg:
                path = resolver.path_for(cfg[ref_key], kind)
                name = cfg[ref_key].removeprefix(f"{kind}.")
                if name not in resolver.resources.get(kind, {}):
                    warnings.append(f"{where}: {ref_key} {cfg[ref_key]!r} is not listed under resources.{kind}")
                if not path.exists():
                    errors.append(f"{where}: {ref_key} {cfg[ref_key]!r} -> {path} does not exist")
        if typ in ("EVALUATE", "ASSERT"):
            if not cfg.get("condition"):
                errors.append(f"{where}: no condition")
            else:
                _check_condition(where, cfg["condition"], in_ports, errors)
        elif typ == "GENERATE" and not any(k in cfg for k in ("prompt_ref", "prompt_inline", "procedure_ref")):
            errors.append(f"{where}: needs prompt_ref, prompt_inline or procedure_ref")
        elif typ == "GUARD":
            if not cfg.get("policy_ref"):
                errors.append(f"{where}: no policy_ref (a guard without a policy cannot decide)")
            for k, expr in cfg.get("context_mapping", {}).items():
                _check_condition(f"{where} context_mapping.{k}", expr, in_ports, errors)
            for p in ("allow", "deny"):
                if p not in n["ports"]:
                    errors.append(f"{where}: missing port {p!r}")
        elif typ == "MUTATE":
            if not cfg.get("policy_ref"):
                errors.append(f"{where}: no policy_ref (self-revision is deny-by-default)")
            for p in ("applied", "rejected", "in_delta"):
                if p not in n["ports"]:
                    errors.append(f"{where}: missing port {p!r}")
        elif typ == "LOOP":
            _check_loop(n, prefix, resolver, errors, warnings)

        for port in sorted(in_ports):
            if (nid, port) not in fed and not (port in boundary or port[3:] in loop_vars) and typ not in ("OUTPUT",):
                warnings.append(f"{where}: input {port!r} is not fed by any binds edge")
        if typ not in ("INPUT", "LOOP") and "trigger" in n["ports"] and nid not in triggered and not prefix:
            warnings.append(f"{where}: nothing triggers it")


def _check_loop(n: Dict, prefix: str, resolver: ResourceResolver, errors: List[str], warnings: List[str]) -> None:
    cfg, nid = n.get("config", {}), n["id"]
    where = f"{prefix}LOOP {nid!r}"
    body = cfg.get("subgraph")
    if not body:
        errors.append(f"{where}: no subgraph")
        return
    if "condition" not in cfg and "max_iterations" not in cfg:
        errors.append(f"{where}: needs a condition or max_iterations")
    outputs = cfg.get("outputs", {})
    index_var = cfg.get("index_var", "cycle")
    loop_in = {p for p in n["ports"] if p.startswith("in_")}
    scope = loop_in | set(outputs) | {index_var, "cycle"}
    for key in ("condition", "max_iterations"):
        if isinstance(cfg.get(key), str):
            _check_condition(f"{where} {key}", cfg[key], scope, errors)
    body_ids = {b["id"] for b in body["nodes"]}
    for name, spec in outputs.items():
        kinds = [k for k in ("from", "collect", "fired") if k in spec]
        if len(kinds) != 1:
            errors.append(f"{where}: output {name!r} needs exactly one of from/collect/fired")
            continue
        ref = spec[kinds[0]]
        node, _, port = ref.partition(".")
        if node not in body_ids:
            errors.append(f"{where}: output {name!r} refers to {ref!r}, but the subgraph has no node {node!r}")
        else:
            bn = next(b for b in body["nodes"] if b["id"] == node)
            if port not in bn["ports"]:
                errors.append(f"{where}: output {name!r} refers to {ref!r}, but {node!r} has no port {port!r}")
    for name in outputs:
        if f"out_{name}" not in n["ports"]:
            warnings.append(f"{where}: output {name!r} has no port 'out_{name}' on the node, so nothing can read it")
    _check_scope(body["nodes"], body["edges"], f"{prefix}{nid}/", resolver, scope, loop_in, errors, warnings)


def check(graph_data: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []
    resolver = ResourceResolver(Path(graph_data.get("_source_dir", ".")), graph_data.get("resources"))
    nodes, edges = graph_data["nodes"], graph_data["edges"]
    entries = [n for n in nodes if n["type"] == "INPUT"]
    if len(entries) != 1:
        errors.append(f"expected exactly one INPUT node, found {len(entries)}")
    if not any(n["type"] == "OUTPUT" for n in nodes):
        warnings.append("no OUTPUT node: the workflow returns nothing")
    declared = {p["name"] for p in graph_data["workflow"].get("inputs", [])}
    for n in entries:
        for p in n["ports"]:
            if p.startswith("out_") and p[4:] not in declared:
                errors.append(f"INPUT {n['id']!r}: port {p!r} is not a declared workflow input")
        for d in sorted(declared - {p[4:] for p in n["ports"] if p.startswith("out_")}):
            warnings.append(f"INPUT {n['id']!r}: declared input {d!r} has no out_{d} port")
    _check_scope(nodes, edges, "", resolver, set(), set(), errors, warnings)
    for kind in SUFFIX:
        for name, rel in graph_data.get("resources", {}).get(kind, {}).items():
            if not (resolver.base_dir / rel).exists():
                errors.append(f"resources.{kind}.{name}: {rel} does not exist")
    return errors, warnings
