"""Static checks on a loaded GraphLang graph: wiring, resources and conditions, without running it.

`check(graph_data)` returns (errors, warnings). Errors are things that would fail or misbehave at run
time; warnings are suspicious but allowed (an input nothing feeds, a node nothing triggers).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from .ports import apply_input_types, assignable, check_types, normalize_ports, port_type
from .lifecycle import check_phases
from .expr import ExpressionError, variables
from .resolver import ResourceResolver, SUFFIX
from .solve_backend import check_solve

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
        errors += [f"{prefix}{n['type']} {n['id']!r}: {m}" for m in check_types(n)]
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
            (st, _), (dt, _) = port_type(by_id[src], sport), port_type(by_id[tgt], tport)
            if not assignable(st, dt):
                errors.append(f"{prefix}{e['source']} -> {e['target']}: {st} cannot be bound to a {dt} port")

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
        errors += [f"{where}: {m}" for m in check_phases(n)]
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
        elif typ == "RECOVER":
            action = cfg.get("action", "halt")
            if action not in ("halt", "abort", "skip", "retry"):
                errors.append(f"{where}: action must be halt, abort, skip or retry, not {action!r}")
            if action == "retry":
                if "retry" not in n["ports"]:
                    errors.append(f"{where}: action retry needs a 'retry' port to wire back to the failed node")
                if cfg.get("then", "abort") not in ("halt", "abort", "skip"):
                    errors.append(f"{where}: then must be halt, abort or skip")
        elif typ == "SOLVE":
            solve_errors, solve_warnings = check_solve(n, resolver.base_dir)
            errors += [f"{where}: {m}" for m in solve_errors]
            warnings += [f"{where}: {m}" for m in solve_warnings]
        elif typ == "LOOP":
            _check_loop(n, prefix, resolver, errors, warnings)

        for port in sorted(in_ports):
            if (nid, port) not in fed and not (port in boundary or port[3:] in loop_vars) and typ not in ("OUTPUT",):
                warnings.append(f"{where}: input {port!r} is not fed by any binds edge")
        if typ not in ("INPUT", "LOOP") and "trigger" in n["ports"] and nid not in triggered and not prefix:
            warnings.append(f"{where}: nothing triggers it")
    _check_races(nodes, edges, prefix, errors)


class _Order:
    """Control-flow order inside one scope, read from its `triggers` edges.

    `ordered(a, b)`: one node can reach the other, so one of them runs after the other (happens-before).
    `exclusive(a, b)`: some node routes to only one of its control ports per firing (everything but a FORK), and `a`
    is reachable only from one of those ports and `b` only from another, so at most one of them runs.
    """

    def __init__(self, nodes: List[Dict], edges: List[Dict]):
        self.type = {n["id"]: n["type"] for n in nodes}
        self.by_port: Dict[Tuple[str, str], Set[str]] = {}
        self.by_node: Dict[str, Set[str]] = {}
        for e in edges:
            if e["type"] != "triggers":
                continue
            (src, _, sport), (tgt, _, _) = e["source"].partition("."), e["target"].partition(".")
            if src in self.type and tgt in self.type:
                self.by_port.setdefault((src, sport), set()).add(tgt)
                self.by_node.setdefault(src, set()).add(tgt)
        self._reach_cache: Dict[Any, Set[str]] = {}

    def _reach(self, starts: Set[str]) -> Set[str]:
        key = frozenset(starts)
        if key not in self._reach_cache:
            seen, todo = set(), list(starts)
            while todo:
                n = todo.pop()
                if n not in seen:
                    seen.add(n)
                    todo += self.by_node.get(n, ())
            self._reach_cache[key] = seen
        return self._reach_cache[key]

    def ordered(self, a: str, b: str) -> bool:
        return b in self._reach({a}) or a in self._reach({b})

    def exclusive(self, a: str, b: str) -> bool:
        for node, typ in self.type.items():
            if typ == "FORK":
                continue
            ports = {port: self._reach(t) for (n, port), t in self.by_port.items() if n == node}
            for p1, r1 in ports.items():
                for p2, r2 in ports.items():
                    if p1 < p2 and ((a in r1 and a not in r2 and b in r2 and b not in r1)
                                    or (b in r1 and b not in r2 and a in r2 and a not in r1)):
                        return True
        return False


def _check_races(nodes: List[Dict], edges: List[Dict], prefix: str, errors: List[str]) -> None:
    """Report a race and a deadlock, both found by counting tokens on the control graph.

    Race: two nodes write the same input port through `binds` edges, and neither runs after the other nor excludes the
    other. The port then holds whichever the scheduler ran last, which is not part of the program.
    Deadlock: a JOIN waits for a token on every incoming `triggers` edge, so two sources of which at most one can run
    mean it never fires.
    """
    order = _Order(nodes, edges)
    writers: Dict[str, Set[str]] = {}
    for e in edges:
        if e["type"] == "binds":
            tgt, src = e["target"], e["source"].partition(".")[0]
            if src in order.type:
                writers.setdefault(tgt, set()).add(src)
    for port, srcs in sorted(writers.items()):
        srcs = sorted(srcs)
        for i, a in enumerate(srcs):
            for b in srcs[i + 1:]:
                if not order.ordered(a, b) and not order.exclusive(a, b):
                    errors.append(f"{prefix}race: {a!r} and {b!r} both write {port!r} and neither runs after the other "
                                  f"or excludes it; order them with a `triggers` path, or route them from one branch")
    for n in nodes:
        if n["type"] != "JOIN":
            continue
        srcs = sorted({e["source"].partition(".")[0] for e in edges
                       if e["type"] == "triggers" and e["target"] == f"{n['id']}.trigger" and e["source"].partition(".")[0] in order.type})
        for i, a in enumerate(srcs):
            for b in srcs[i + 1:]:
                if order.exclusive(a, b):
                    errors.append(f"{prefix}deadlock: JOIN {n['id']!r} waits for both {a!r} and {b!r}, but at most one of them runs")


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


RISKY_TYPES = ("EMIT", "QUERY")       # reach outside the workflow; anything else is risky only when marked `risky: true`


def _risky(node: Dict) -> bool:
    return node["type"] in RISKY_TYPES or bool(node.get("config", {}).get("risky"))


def _contains_risky(node: Dict) -> List[str]:
    """Risky nodes inside a LOOP body (any depth), as `loop/node` names; the LOOP is then treated as risky itself."""
    found = []
    for b in node.get("config", {}).get("subgraph", {}).get("nodes", []):
        if _risky(b):
            found.append(f"{node['id']}/{b['id']}")
        if b["type"] == "LOOP":
            found += [f"{node['id']}/{f}" for f in _contains_risky(b)]
    return found


def _check_guarded(nodes: List[Dict], edges: List[Dict], errors: List[str]) -> None:
    """Every risky node must be reachable only through a GUARD's `allow` port.

    A node is risky when its type is in RISKY_TYPES or it has `config.risky: true` (put it on an OUTPUT that releases
    data, or on a `procedure_ref` node that acts on the world). A LOOP is risky when its body holds a risky node. We follow
    `triggers` edges from the INPUT node with every edge that leaves a GUARD removed: a risky node still reached has a path
    that skips the guard. We then follow each guard's `deny` port the same way: a risky node reached from there is run
    after a refusal. Data (`binds`) edges are not control flow and are ignored; so are guards inside LOOP bodies.
    """
    by_id = {n["id"]: n for n in nodes}
    guards = {n["id"] for n in nodes if n["type"] == "GUARD"}
    out: Dict[str, List[str]] = {}
    deny_from: Dict[str, List[str]] = {}
    for e in edges:
        if e["type"] != "triggers":
            continue
        (src, _, sport), (tgt, _, _) = e["source"].partition("."), e["target"].partition(".")
        if src not in by_id or tgt not in by_id:
            continue
        if src in guards:
            if sport == "deny":
                deny_from.setdefault(src, []).append(tgt)
        else:
            out.setdefault(src, []).append(tgt)

    def reach(starts):
        seen, todo = set(), list(starts)
        while todo:
            n = todo.pop()
            if n not in seen:
                seen.add(n)
                todo += out.get(n, [])
        return seen

    risky = {}
    for n in nodes:
        inside = _contains_risky(n) if n["type"] == "LOOP" else []
        if _risky(n) or inside:
            risky[n["id"]] = f"{n['type']} {n['id']!r}" + (f" (its body holds risky {', '.join(inside)})" if inside else "")
    unguarded = reach(n["id"] for n in nodes if n["type"] == "INPUT")
    for nid, what in risky.items():
        if nid in unguarded:
            errors.append(f"{what} is risky but can run without passing a GUARD's allow port")
    for g, targets in deny_from.items():
        for nid in sorted(set(risky) & reach(targets)):
            errors.append(f"{risky[nid]} can run after GUARD {g!r} denies")


def invariants(nodes: List[Dict], edges: List[Dict]) -> List[str]:
    """The structural guarantees that must hold for every graph that exists, the loaded one and each one a MUTATE
    produces: risky nodes stay behind a GUARD, no race, no deadlock. A delta is refused if it adds an error to this list."""
    errors: List[str] = []
    _check_guarded(nodes, edges, errors)
    _check_races(nodes, edges, "", errors)
    return errors


def check(graph_data: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []
    resolver = ResourceResolver(Path(graph_data.get("_source_dir", ".")), graph_data.get("resources"))
    nodes, edges = graph_data["nodes"], graph_data["edges"]
    normalize_ports(nodes)
    apply_input_types(graph_data)
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
    _check_guarded(nodes, edges, errors)
    for kind in SUFFIX:
        for name, rel in graph_data.get("resources", {}).get(kind, {}).items():
            if not (resolver.base_dir / rel).exists():
                errors.append(f"resources.{kind}.{name}: {rel} does not exist")
    return errors, warnings
