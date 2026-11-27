"""`graf util arch-gate`: a component may only claim the status it has earned.

Every node of an architecture graph can declare a lifecycle `status` (planned < prototype < validated < product) and a `contract`:

    contract:
      tests:      [tests]                     # paths under the node's repo that must exist (a folder must hold at least one test file)
      files:      [src/pkg/recipes]           # other paths the node promises to ship
      guarantees: ["a cycle is rejected (tests/test_validator.py::test_cycle_is_detected)"]   # what it promises; a product must state some,
                                                                                         # and a cited `file.py::test_name` must exist in the repo

The gate computes the status each node has *earned*, from facts it can check, and fails when a node claims more:

    prototype   the repo exists
    validated   + the contract names tests and they exist, the contract's files exist, and the node has no drift error (see `arch-drift`)
    product     + the contract states guarantees (each test it cites as `path.py::test_name` must exist), and everything the node `requires`
                has itself earned `product` (a `requires` target with no `repo` is an outside service and does not count)

With `run_cited` the gate also runs the tests the guarantees cite (in each node's own repo, with the interpreter you name) and records what happened to
each: passed, failed, skipped, or not found. A cited test that did not pass blocks `product`: a guarantee is only as good as the test behind it, and a
skipped test (a missing optional package, a server that is down) proves nothing.

So a promotion is a change to the `.arch.yaml` that CI can accept or refuse, and an AI agent cannot declare something finished that the graph
says is not. A node with no `status` is unrated and not gated. No dependency beyond PyYAML.
"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
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


_CITED_TEST = re.compile(r"([\w./-]+\.py)::(\w+)")


def cited_tests(guarantees: list[str]) -> list[tuple[str, str]]:
    """The tests a node's guarantees cite as `path/to/test_x.py::test_name`."""
    return [m for g in guarantees for m in _CITED_TEST.findall(g)]


def _test_exists(repo: Path, path: str, name: str) -> bool:
    f = repo / path
    return f.is_file() and re.search(rf"^\s*(?:async\s+)?def {re.escape(name)}\b", f.read_text(encoding="utf-8", errors="replace"), re.M) is not None


@dataclass
class Evidence:
    """What happened to one cited test."""
    path: str
    name: str
    outcome: str          # passed | failed | skipped | missing (pytest did not collect it) | error (pytest could not run)
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.outcome == "passed"

    def __str__(self) -> str:
        return f"{self.path}::{self.name} {self.outcome}" + (f" ({self.detail})" if self.detail else "")


def _nodes_of(arch: dict) -> dict[str, dict]:
    return {n["id"]: n for layer in arch.get("layers") or [] for n in [*(layer.get("nodes") or []), *[m for g in layer.get("groups") or [] for m in g.get("nodes") or []]]}


def _outcomes(xml_path: Path, names: list[str]) -> dict[str, tuple[str, str]]:
    """{cited name: (outcome, detail)} from a pytest junit file. A parametrized test counts under its plain name: it passed if any case passed
    and none failed."""
    cases = []
    for tc in ET.parse(xml_path).getroot().iter("testcase"):
        if tc.find("failure") is not None or tc.find("error") is not None:
            node = tc.find("failure") if tc.find("failure") is not None else tc.find("error")
            cases.append((tc.get("name", ""), "failed", (node.get("message") or "")[:100]))
        elif tc.find("skipped") is not None:
            cases.append((tc.get("name", ""), "skipped", (tc.find("skipped").get("message") or "")[:100]))
        else:
            cases.append((tc.get("name", ""), "passed", ""))
    out = {}
    for n in names:
        mine = [c for c in cases if c[0] == n or c[0].startswith(n + "[")]
        if not mine:
            out[n] = ("missing", "pytest did not collect it")
        elif any(c[1] == "failed" for c in mine):
            out[n] = ("failed", next(c[2] for c in mine if c[1] == "failed"))
        elif any(c[1] == "passed" for c in mine):
            out[n] = ("passed", "")
        else:
            out[n] = ("skipped", mine[0][2])
    return out


def run_cited(arch: dict, root: str | Path, *, python: str | None = None, timeout: int = 300, only: list[str] | None = None) -> dict[str, list[Evidence]]:
    """Run the tests the guarantees cite, node by node, in each node's repo. Returns {node id: [Evidence, ...]}. `only` limits it to those nodes."""
    root, python = Path(root), python or sys.executable
    result: dict[str, list[Evidence]] = {}
    for nid, n in _nodes_of(arch).items():
        if (only and nid not in only) or not n.get("repo"):
            continue
        cited = cited_tests((n.get("contract") or {}).get("guarantees") or [])
        if not cited:
            continue
        repo = root / n["repo"]
        by_file: dict[str, list[str]] = {}
        for path, name in cited:
            by_file.setdefault(path, []).append(name)
        evidence: list[Evidence] = []
        for path, names in by_file.items():
            target = str(Path(path).parent) if path.endswith("conftest.py") else path          # a contract mixin in conftest.py is collected through its test files
            if not repo.is_dir():
                evidence += [Evidence(path, n_, "error", f"repo {n['repo']!r} not found") for n_ in names]
                continue
            with tempfile.TemporaryDirectory() as tmp:
                xml = Path(tmp) / "r.xml"
                cmd = [python, "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--junitxml={xml}", target, "-k", " or ".join(names)]
                try:
                    r = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, timeout=timeout)
                except subprocess.TimeoutExpired:
                    evidence += [Evidence(path, n_, "error", f"timed out after {timeout} s") for n_ in names]
                    continue
                if not xml.is_file():
                    why = (r.stdout + r.stderr).strip().splitlines()[-1:] or ["pytest wrote no report"]
                    evidence += [Evidence(path, n_, "error", why[0][:100]) for n_ in names]
                    continue
                for n_, (outcome, detail) in _outcomes(xml, names).items():
                    evidence.append(Evidence(path, n_, outcome, detail))
        result[nid] = evidence
    return result


def gate(arch: dict, root: str | Path, evidence: dict[str, list[Evidence]] | None = None) -> list[NodeGate]:
    root = Path(root)
    nodes = _nodes_of(arch)
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
        for path, name in cited_tests(contract.get("guarantees") or []):
            if repo is None or not _test_exists(repo, path, name):
                blockers["product"].append(f"a guarantee cites {path}::{name}, which does not exist")
        for e in (evidence or {}).get(nid, []):
            if not e.ok:
                blockers["product"].append(f"a cited test did not pass: {e}")
        for t in requires.get(nid, []):
            if t in stack or not nodes[t].get("repo"):      # no repo = an outside service or machine (hosted providers, GPUs): nothing of ours to promote
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
