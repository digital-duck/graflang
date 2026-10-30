"""Edit a workflow file without losing what the author wrote (the engine behind `graf vis --edit`).

`GraphEditor` opens a long-form `*.graph.yaml`, applies edits (add, remove, rename a node; set its config or ports; add or remove an
edge) and writes the file back with its comments and layout kept (ruamel round trip). An edit is applied if the file stays
well formed (unique ids, edges between real ports); whether the graph is *valid* is a separate question, because a graph is
invalid half way through adding a node and wiring it: `problems()` runs `graf validate` on the current state, and `save()` refuses to
write while it reports errors. Every edit can be undone.

A hand edit may set anything a node can hold (a human wrote it); the `MUTATE` rule that a model can never add code is not applied here.
"""
from __future__ import annotations

import copy
import io
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from jsonschema import ValidationError, validate
from ruamel.yaml import YAML

from ..grafr.compact import is_compact
from ..grafr.ports import apply_input_types, normalize_ports
from ..grafr.runtime import SCHEMA_PATH, split_ref
from ..grafr.topology import check

import json


class EditError(ValueError):
    """The edit cannot be applied (the message says why)."""


def _plain(value: Any) -> Any:
    """ruamel's round-trip containers as ordinary dicts and lists."""
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value


class GraphEditor:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._yaml = YAML()
        self._yaml.preserve_quotes = True
        self._yaml.width = 4096                                # never re-wrap the author's long lines
        text = self.path.read_text(encoding="utf-8")
        self._yaml.indent(mapping=2, sequence=self._dash_offset(text) + 2, offset=self._dash_offset(text))   # write lists the way the file does
        self.doc = self._yaml.load(text)
        if not isinstance(self.doc, dict) or "nodes" not in self.doc or "workflow" not in self.doc:
            if is_compact(self.doc):
                raise EditError("this file uses the compact `steps:` form; edit the YAML text, or run `graf expand` to get the long form")
            raise EditError("not a GraphLang workflow (needs workflow:, nodes: and edges:)")
        self.doc.setdefault("edges", [])
        self._undo: List[str] = []
        self.saved_text = self._dump()

    @staticmethod
    def _dash_offset(text: str) -> int:
        """How far the `- ` of the `nodes:` list is indented in this file (0 or 2 are the usual styles)."""
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if line.rstrip() == "nodes:" and i + 1 < len(lines) and lines[i + 1].lstrip().startswith("- "):
                return len(lines[i + 1]) - len(lines[i + 1].lstrip())
        return 2

    # ---- reading -----------------------------------------------------------------------------
    def _dump(self) -> str:
        buf = io.StringIO()
        self._yaml.dump(self.doc, buf)
        return buf.getvalue()

    def data(self) -> Dict[str, Any]:
        """The graph as plain dicts, ready for `check` and for drawing."""
        graph = _plain(self.doc)
        graph["_source_dir"] = str(self.path.resolve().parent)
        normalize_ports(graph["nodes"])
        apply_input_types(graph)
        return graph

    def node(self, node_id: str) -> Dict[str, Any]:
        return self.data()["nodes"][self._index(node_id)]

    def node_ids(self) -> List[str]:
        return [str(n["id"]) for n in self.doc["nodes"]]

    def problems(self) -> Tuple[List[str], List[str]]:
        """(errors, warnings) from the same checks as `graf validate`, schema included."""
        graph = self.data()
        try:
            validate(instance={k: v for k, v in graph.items() if k != "_source_dir"}, schema=json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))
        except ValidationError as e:
            where = "/".join(str(p) for p in e.absolute_path) or "<root>"
            return [f"schema: {where}: {e.message}"], []
        try:
            return check(graph)
        except (KeyError, ValueError) as e:
            return [f"cannot check the graph: {e}"], []

    @property
    def changed(self) -> bool:
        return self._dump() != self.saved_text

    # ---- editing -----------------------------------------------------------------------------
    def _index(self, node_id: str) -> int:
        for i, n in enumerate(self.doc["nodes"]):
            if n["id"] == node_id:
                return i
        raise EditError(f"no node {node_id!r}")

    def _port_names(self, node: Dict) -> List[str]:
        ports = node["ports"]
        return list(ports) if isinstance(ports, (list, tuple)) else list(ports.keys())

    def _check_endpoint(self, ref: str) -> None:
        try:
            node_id, port = split_ref(ref)
        except ValueError as e:
            raise EditError(str(e)) from None
        node = self.doc["nodes"][self._index(node_id)]
        if port not in self._port_names(node):
            raise EditError(f"node {node_id!r} has no port {port!r} (it has {self._port_names(node)})")

    def _edit(self, change) -> None:
        before = self._dump()
        try:
            change()
        except Exception:
            self.doc = self._yaml.load(before)                 # a failed edit leaves nothing half done
            raise
        self._undo.append(before)

    def add_node(self, node_id: str, node_type: str, ports: List[str], config: Optional[Dict[str, Any]] = None) -> None:
        if not node_id or not all(c.isalnum() or c == "_" for c in node_id):
            raise EditError("a node id uses letters, digits and underscores")
        if node_id in self.node_ids():
            raise EditError(f"there is already a node {node_id!r}")
        if not ports:
            raise EditError("a node needs at least one port")

        def change():
            node = {"id": node_id, "type": node_type}
            if config:
                node["config"] = copy.deepcopy(config)
            node["ports"] = list(ports)
            self.doc["nodes"].append(node)
        self._edit(change)

    def remove_node(self, node_id: str) -> None:
        index = self._index(node_id)

        def change():
            del self.doc["nodes"][index]
            keep = [e for e in self.doc["edges"] if split_ref(e["source"])[0] != node_id and split_ref(e["target"])[0] != node_id]
            self.doc["edges"][:] = keep
        self._edit(change)

    def rename_node(self, old: str, new: str) -> None:
        index = self._index(old)
        if new in self.node_ids():
            raise EditError(f"there is already a node {new!r}")
        if not new or not all(c.isalnum() or c == "_" for c in new):
            raise EditError("a node id uses letters, digits and underscores")

        def change():
            self.doc["nodes"][index]["id"] = new
            for e in self.doc["edges"]:
                for side in ("source", "target"):
                    node, _, port = e[side].partition(".")
                    if node == old:
                        e[side] = f"{new}.{port}"
        self._edit(change)

    def set_config(self, node_id: str, key: str, value: Any) -> None:
        index = self._index(node_id)

        def change():
            node = self.doc["nodes"][index]
            if "config" not in node or node["config"] is None:
                node["config"] = {}
            node["config"][key] = copy.deepcopy(value)
        self._edit(change)

    def delete_config(self, node_id: str, key: str) -> None:
        index = self._index(node_id)
        node = self.doc["nodes"][index]
        if key not in (node.get("config") or {}):
            raise EditError(f"node {node_id!r} has no config key {key!r}")

        def change():
            del node["config"][key]
            if not node["config"]:
                del node["config"]
        self._edit(change)

    def set_ports(self, node_id: str, ports: List[str]) -> None:
        index = self._index(node_id)
        gone = set(self._port_names(self.doc["nodes"][index])) - set(ports)
        dangling = [e for e in self.doc["edges"] for side in ("source", "target")
                    if split_ref(e[side])[0] == node_id and split_ref(e[side])[1] in gone]
        if dangling:
            e = dangling[0]
            raise EditError(f"edge {e['source']} -> {e['target']} still uses a port you removed; remove the edge first")
        self._edit(lambda: self.doc["nodes"][index].__setitem__("ports", list(ports)))

    def add_edge(self, source: str, target: str, edge_type: str) -> None:
        if edge_type not in ("triggers", "binds"):
            raise EditError("an edge is `triggers` (control) or `binds` (data)")
        self._check_endpoint(source)
        self._check_endpoint(target)
        if any(e["source"] == source and e["target"] == target and e["type"] == edge_type for e in self.doc["edges"]):
            raise EditError(f"{source} -> {target} ({edge_type}) is already there")
        self._edit(lambda: self.doc["edges"].append({"source": source, "target": target, "type": edge_type}))

    def remove_edge(self, source: str, target: str, edge_type: str) -> None:
        for i, e in enumerate(self.doc["edges"]):
            if e["source"] == source and e["target"] == target and e["type"] == edge_type:
                self._edit(lambda: self.doc["edges"].__delitem__(i))
                return
        raise EditError(f"no edge {source} -> {target} ({edge_type})")

    def undo(self) -> bool:
        if not self._undo:
            return False
        self.doc = self._yaml.load(self._undo.pop())
        return True

    # ---- writing -----------------------------------------------------------------------------
    def save(self) -> None:
        """Write the file if `graf validate` reports no errors. The old file is replaced only after the new one is complete."""
        errors, _ = self.problems()
        if errors:
            raise EditError(f"not saved: {len(errors)} problem(s), first: {errors[0]}")
        text = self._dump()
        fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), prefix=f".{self.path.name}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(text)
            os.replace(tmp, self.path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
        self.saved_text = text
