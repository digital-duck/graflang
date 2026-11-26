"""`graf util arch-drift`: does the code still match the architecture graph?

The architecture says which package depends on which (`requires` / `optional` edges between nodes that name a `pkg` and a `repo`). Each repo's
`pyproject.toml` says the same thing in its own words. This compares the two and reports the difference, so the graph cannot quietly go
stale and the code cannot quietly grow a dependency the architecture never allowed:

    missing-in-graph   the code depends on a package the graph has no edge to          (the graph is behind the code)
    missing-in-code    the graph has a `requires`/`optional` edge the code does not use    (the code is behind the graph, or the edge is wrong)
    weaker-in-code     the graph says `requires`, the code only has it as an extra
    stronger-in-code   the graph says `optional`, the code requires it
    wrong-package      the node's `pkg` is not the name the repo's pyproject.toml declares
    unknown-command    the node lists a `cmd` that is not a console script of the repo (a pip or repo name, a typo, a command not shipped yet)
    unlisted-command   the repo ships a console script the node does not list                                              (warning)
    missing-repo       the node names a repo that is not under --root

Only Python projects with a `pyproject.toml` are read; nodes without `pkg`/`repo` (and `network` edges) are skipped. No dependency beyond PyYAML.
"""
from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

ERRORS = {"missing-in-graph", "missing-in-code", "wrong-package", "missing-repo", "unknown-command"}      # the others are warnings


@dataclass
class Finding:
    code: str
    node: str
    message: str

    @property
    def is_error(self) -> bool:
        return self.code in ERRORS

    def __str__(self) -> str:
        return f"{'error' if self.is_error else 'warning'}: [{self.code}] {self.node}: {self.message}"


def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _req_name(spec: str) -> str | None:
    m = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", spec)
    return _norm(m.group(1)) if m else None


def read_scripts(pyproject: Path) -> set[str]:
    """The console scripts a pyproject.toml declares."""
    return set((tomllib.loads(pyproject.read_text(encoding="utf-8")).get("project", {}).get("scripts") or {}))


def read_dependencies(pyproject: Path) -> tuple[str | None, set[str], set[str]]:
    """(declared name, required dependencies, optional dependencies [extras]) of a pyproject.toml, names normalized."""
    project = tomllib.loads(pyproject.read_text(encoding="utf-8")).get("project", {})
    required = {n for n in map(_req_name, project.get("dependencies") or []) if n}
    optional = {n for specs in (project.get("optional-dependencies") or {}).values() for n in map(_req_name, specs) if n}
    name = project.get("name")
    return (_norm(name) if name else None), required, optional - required


def drift(arch: dict, root: str | Path) -> list[Finding]:
    root = Path(root)
    nodes = {n["id"]: n for layer in arch.get("layers") or [] for n in [*(layer.get("nodes") or []), *[m for g in layer.get("groups") or [] for m in g.get("nodes") or []]]}
    by_pkg = {_norm(n["pkg"]): n["id"] for n in nodes.values() if n.get("pkg")}
    findings: list[Finding] = []
    for nid, n in nodes.items():
        if not (n.get("pkg") and n.get("repo")):
            continue
        py = root / n["repo"] / "pyproject.toml"
        if not py.is_file():
            if (root / n["repo"]).is_dir():
                continue            # a repo that is not a Python project (Go, ...): nothing to compare
            findings.append(Finding("missing-repo", nid, f"repo {n['repo']!r} not found under {root}"))
            continue
        declared, required, optional = read_dependencies(py)
        if declared and declared != _norm(n["pkg"]):
            findings.append(Finding("wrong-package", nid, f"the graph says pkg {n['pkg']!r} but {n['repo']}/pyproject.toml declares {declared!r}"))
        scripts, listed = read_scripts(py), set(n.get("cmd") or [])
        for c in sorted(listed - scripts):
            findings.append(Finding("unknown-command", nid, f"cmd {c!r} is not a console script of {n['repo']} (it ships: {', '.join(sorted(scripts)) or 'none'})"))
        for c in sorted(scripts - listed) if listed or n.get("cmd") is not None else []:
            findings.append(Finding("unlisted-command", nid, f"{n['repo']} ships console script {c!r} which the node does not list in cmd"))
        edges = {e["to"]: e.get("kind", "requires") for e in arch.get("edges") or [] if e["from"] == nid and e.get("kind", "requires") != "network"}
        in_code = {by_pkg[d]: ("requires" if d in required else "optional") for d in required | optional if d in by_pkg and by_pkg[d] != nid}
        for target, kind in sorted(in_code.items()):
            if target not in edges:
                findings.append(Finding("missing-in-graph", nid, f"{n['repo']} {kind} {target!r} in pyproject.toml, but the graph has no edge {nid} -> {target}"))
            elif edges[target] == "requires" and kind == "optional":
                findings.append(Finding("weaker-in-code", nid, f"the graph requires {target!r}, the code has it only as an extra"))
            elif edges[target] == "optional" and kind == "requires":
                findings.append(Finding("stronger-in-code", nid, f"the graph marks {target!r} optional, the code requires it"))
        for target, kind in sorted(edges.items()):
            if target in nodes and nodes[target].get("pkg") and target not in in_code:
                findings.append(Finding("missing-in-code", nid, f"the graph has {kind} edge {nid} -> {target}, but {n['repo']}/pyproject.toml does not depend on {nodes[target]['pkg']!r}"))
    return findings
