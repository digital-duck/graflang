"""`graf util arch-gate`: a component may only claim the status it has earned.

Every node of an architecture graph can declare a lifecycle `status` (planned < prototype < validated < product) and a `contract`:

    contract:
      tests:      [tests]                     # paths under the node's repo that must exist (a folder must hold at least one test file)
      files:      [src/pkg/recipes]           # other paths the node promises to ship
      guarantees: ["`graf validate` rejects a graph with a cycle"]      # what it promises, in words; a product must state some

The gate computes the status each node has *earned*, from facts it can check, and fails when a node claims more:

    prototype   the repo exists
    validated   + the contract names tests and they exist, the contract's files exist, and the node has no drift error (see `arch-drift`)
    product     + the contract states guarantees, and everything the node `requires` has itself earned `product`

So a promotion is a change to the `.arch.yaml` that CI can accept or refuse, and an AI agent cannot declare something finished that the graph
says is not. A node with no `status` is unrated and not gated. No dependency beyond PyYAML.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .arch2mmd import STATUSES
from .arch_drift import drift

LEVEL = {name: i for i, name in enumerate(STATUSES)}


@dataclass
class NodeGate:
    node: str
    claimed: str | None
    earned: str
    blockers: list[str] = field(default_factory=list)       # why the next level above `earned` is not earned yet

    @property
    def ok(self) -> bool:
        return self.claimed is None or LEVEL[self.claimed] <= LEVEL[self.earned]


def _has_tests(path: Path) -> bool:
    if path.is_file():
        return True
    return path.is_dir() and any(next(path.rglob(pat), None) for pat in ("test_*.py", "*_test.py", "*_test.go", "*.spec.*", "*.test.*"))


def gate(arch: dict, root: str | Path) -> list[NodeGate]:
    root = Path(root)
    nodes = {n["id"]: n for layer in arch.get("layers") or [] for n in [*(layer.get("nodes") or []), *[m for g in layer.get("groups") or [] for m in g.get("nodes") or []]]}
    drift_errors: dict[str, list[str]] = {}
    for f in drift(arch, root):
        if f.is_error:
            drift_errors.setdefault(f.node, []).append(f.message)
    requires: dict[str, list[str]] = {}
    for e in arch.get("edges") or []:
        if e.get("kind", "requires") == "requires" and e["from"] in nodes and e["to"] in nodes:
            requires.setdefault(e["from"], []).append(e["to"])
    memo: dict[str, NodeGate] = {}

    def earn(nid: str, stack: tuple[str, ...] = ()) -> NodeGate:
        if nid in memo:
            return memo[nid]
        n = nodes[nid]
        contract = n.get("contract") or {}
        repo = root / n["repo"] if n.get("repo") else None
        blockers: dict[str, list[str]] = {"prototype": [], "validated": [], "product": []}
        if repo is None:
            blockers["prototype"].append("the node names no repo")
        elif not repo.is_dir():
            blockers["prototype"].append(f"repo {n['repo']!r} not found under {root}")
        tests = contract.get("tests") or []
        if not tests:
            blockers["validated"].append("the contract names no tests")
        for t in tests:
            if repo is None or not _has_tests(repo / t):
                blockers["validated"].append(f"contract test path {t!r} has no tests")
        for p in contract.get("files") or []:
            if repo is None or not (repo / p).exists():
                blockers["validated"].append(f"contract file {p!r} does not exist")
        blockers["validated"] += [f"drift: {m}" for m in drift_errors.get(nid, [])]
        if not contract.get("guarantees"):
            blockers["product"].append("the contract states no guarantees")
        for t in requires.get(nid, []):
            if t in stack:
                continue
            if nodes[t].get("status") is None:
                blockers["product"].append(f"requires {t!r}, which has no status")
            elif LEVEL[earn(t, stack + (nid,)).earned] < LEVEL["product"]:
                blockers["product"].append(f"requires {t!r}, which has earned only {earn(t, stack + (nid,)).earned!r}")
        earned, why = "planned", []
        for level in ("prototype", "validated", "product"):
            if blockers[level]:
                why = blockers[level]
                break
            earned = level
        memo[nid] = NodeGate(nid, n.get("status"), earned, why)
        return memo[nid]

    return [earn(nid) for nid in nodes]
