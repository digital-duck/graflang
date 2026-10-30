"""Typed ports (design E2).

A node lists its ports as names (`ports: [trigger, in_topic, out_text]`, every type `ANY`) or as a mapping from name to
type (`ports: {trigger: control, in_topic: TEXT, out_text: TEXT, out_plan: {type: JSON, schema: {...}}}`).
`normalize_ports` turns the mapping form into the list the runtime uses and records the types in `node["port_types"]`.

Types: ANY (default), TEXT, INTEGER, FLOAT, BOOL, LIST, JSON (any JSON value, optionally with a JSON Schema), and
`control` for control ports (not checked). A type may carry trust labels, `TEXT!sql_safe`: a sink that names labels
accepts only a source that carries all of them, so `TEXT!sql_safe` takes a sanitizer's `TEXT!sql_safe` output and refuses a
plain `TEXT` one. A source's extra labels are fine. The INPUT node's `out_*` ports take the type declared in
`workflow.inputs` unless they name their own. `graf validate` checks that each `binds` edge can carry its value
(`assignable`); a run checks each typed value as the node writes it (`check_value`).
"""
from __future__ import annotations

from typing import Any, Dict, Iterator, List, Optional, Tuple

from jsonschema import Draft202012Validator

TYPES = {"ANY", "TEXT", "INTEGER", "FLOAT", "BOOL", "LIST", "JSON", "CONTROL"}
JSON_VALUED = {"INTEGER", "FLOAT", "BOOL", "LIST", "JSON"}


INPUT_TYPES = {"TEXT": "TEXT", "STRING": "TEXT", "INTEGER": "INTEGER", "INT": "INTEGER", "FLOAT": "FLOAT", "NUMBER": "FLOAT",
               "REAL": "FLOAT", "BOOL": "BOOL", "BOOLEAN": "BOOL"}


def _type_of(spec: Any) -> Tuple[str, Optional[Dict]]:
    """(type name with its labels, e.g. 'TEXT!sql_safe', schema)."""
    if isinstance(spec, dict):
        return str(spec.get("type", "ANY")), spec.get("schema")
    return str(spec), None


def split_labels(type_name: str) -> Tuple[str, frozenset]:
    base, *labels = type_name.split("!")
    return base.upper(), frozenset(labels)


def _all_nodes(nodes: List[Dict]) -> Iterator[Dict]:
    for n in nodes:
        yield n
        body = n.get("config", {}).get("subgraph")
        if isinstance(body, dict):
            yield from _all_nodes(body.get("nodes", []))


def normalize_ports(nodes: List[Dict]) -> None:
    """Rewrite mapping-form `ports` to a list, in place, for the nodes and the nodes inside LOOP bodies. Idempotent."""
    for n in _all_nodes(nodes):
        if isinstance(n.get("ports"), dict):
            specs = n["ports"]
            n["ports"] = list(specs)
            n["port_types"] = {name: spec for name, spec in specs.items()}


def apply_input_types(graph_data: Dict) -> None:
    """Give the INPUT node's `out_<name>` ports the type declared for workflow input <name>, unless they declare one."""
    declared = {p["name"]: INPUT_TYPES.get(str(p.get("type", "TEXT")).upper()) for p in graph_data["workflow"].get("inputs", [])}
    for n in graph_data["nodes"]:
        if n["type"] == "INPUT":
            types = n.setdefault("port_types", {})
            for port in n["ports"]:
                if port.startswith("out_") and port[4:] in declared and declared[port[4:]] and port not in types:
                    types[port] = declared[port[4:]]


def port_type(node: Dict, port: str) -> Tuple[str, Optional[Dict]]:
    return _type_of(node.get("port_types", {}).get(port, "ANY"))


def assignable(src: str, dst: str) -> bool:
    """Can a value of type `src` (labels included) go on a port of type `dst`?"""
    (sb, sl), (db, dl) = split_labels(src), split_labels(dst)
    if not dl <= sl:
        return False
    if "ANY" in (sb, db) or sb == db:
        return True
    return (sb, db) == ("INTEGER", "FLOAT") or (db == "JSON" and sb in JSON_VALUED)


def check_types(node: Dict) -> List[str]:
    """Messages for the declared types of one node: unknown type names, a schema on a type that cannot take one."""
    errors = []
    for name, spec in node.get("port_types", {}).items():
        t, schema = split_labels(_type_of(spec)[0])[0], _type_of(spec)[1]
        if t not in TYPES:
            errors.append(f"port {name!r} has unknown type {t!r} (use {sorted(TYPES - {'CONTROL'})} or control)")
        elif (t == "CONTROL") != (not name.startswith(("in_", "out_"))):
            errors.append(f"port {name!r}: {'control' if t == 'CONTROL' else 'data'} type on a "
                          f"{'data' if t == 'CONTROL' else 'control'} port")
        if schema is not None:
            try:
                Draft202012Validator.check_schema(schema)
            except Exception as e:
                errors.append(f"port {name!r} schema is not a JSON Schema: {getattr(e, 'message', e)}")
    return errors


_PY = {"TEXT": (str,), "INTEGER": (int,), "FLOAT": (int, float), "BOOL": (bool,), "LIST": (list, tuple)}


def check_value(node: Dict, port: str, value: Any) -> None:
    """Raise ValueError if `value` does not fit the declared type of `port`. None (nothing yet) always fits."""
    t, schema = port_type(node, port)
    t = split_labels(t)[0]
    if value is None or t in ("ANY", "CONTROL"):
        return
    if t in _PY:
        ok = isinstance(value, _PY[t]) and not (t in ("INTEGER", "FLOAT") and isinstance(value, bool))
        if not ok:
            raise ValueError(f"node {node['id']!r} port {port!r} is {t} but got {type(value).__name__}: {str(value)[:60]!r}")
    if schema is not None:
        err = next(iter(Draft202012Validator(schema).iter_errors(value)), None)
        if err is not None:
            where = "/".join(str(p) for p in err.absolute_path) or "(root)"
            raise ValueError(f"node {node['id']!r} port {port!r}: {where}: {err.message}")
