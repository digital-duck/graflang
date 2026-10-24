"""Differential testing of the Cedar compiler against the official engine (cedarpy).

Random policy sets and requests are evaluated twice: by cedarpy, and by the Rust that grafc generates (one
crate holding every policy set, compiled once with rustc). Decisions, reasons and the set of policies that
errored must agree. Needs rustc: set GRAFLANG_RUSTC, or have `rustc` on PATH.
"""
import json
import os
import random
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Tuple

import cedarpy

from graphlang.grafc.cedar.compiler import CedarCompiler, rust_str

TYPES = ["User", "Group", "Doc", "Svc"]
ACTIONS = ["read", "write", "grp"]
IDS = ["a", "b", "c"]
ATTRS = ["n", "m", "s", "t", "flag", "tags", "rec", "who"]
PATTERNS = ['"a*"', '"*b"', '"a*c"', '"*"', '"abc"', '"*b*"', '"a\\*c"', '""', '"x*y*z"']


def find_rustc():
    path = os.environ.get("GRAFLANG_RUSTC") or shutil.which("rustc")
    return path if path and Path(path).exists() else None


# ---- random policies -------------------------------------------------------------------------------

class Gen:
    def __init__(self, rng: random.Random):
        self.r = rng

    def ent(self):
        return f'{self.r.choice(TYPES)}::"{self.r.choice(IDS)}"'

    def action_ent(self):
        return f'Action::"{self.r.choice(ACTIONS)}"'

    def entity(self, d):
        c = self.r.random()
        if c < 0.2:
            return "principal"
        if c < 0.3:
            return "resource"
        if c < 0.4:
            return "action"
        if c < 0.5:
            return "context.who"
        return self.ent() if c < 0.9 else self.long(d)

    def long(self, d):
        c = self.r.random()
        if d <= 0 or c < 0.3:
            return str(self.r.choice([0, 1, 2, 3, 5, 9223372036854775807, -1]))
        if c < 0.5:
            return self.r.choice(["context.n", "context.m", "principal.age", "resource.size"])
        if c < 0.85:
            return f"({self.long(d - 1)} {self.r.choice(['+', '-', '*'])} {self.long(d - 1)})"
        return f"(-{self.long(d - 1)})"

    def string(self, d):
        c = self.r.random()
        if c < 0.4:
            return self.r.choice(['"abc"', '"a"', '"b"', '"axc"', '""', '"x1y2z"'])
        if c < 0.8:
            return self.r.choice(["context.s", "context.t", "principal.name", "context.rec.k"])
        return self.long(d)

    def sets(self, d):
        c = self.r.random()
        if c < 0.4:
            return "context.tags"
        if c < 0.7:
            return "[" + ", ".join(self.string(0) for _ in range(self.r.randint(0, 3))) + "]"
        if c < 0.9:
            return "[" + ", ".join(self.ent() for _ in range(self.r.randint(1, 3))) + "]"
        return self.long(d)

    def bool(self, d):
        c = self.r.random()
        if d <= 0:
            c = c * 0.4
        if c < 0.08:
            return self.r.choice(["true", "false"])
        if c < 0.15:
            return "context.flag"
        if c < 0.27:
            return f"{self.long(d - 1)} {self.r.choice(['<', '<=', '>', '>='])} {self.long(d - 1)}"
        if c < 0.35:
            return f"{self.long(d - 1)} {self.r.choice(['==', '!='])} {self.long(d - 1)}"
        if c < 0.41:
            return f"{self.string(d - 1)} {self.r.choice(['==', '!='])} {self.string(d - 1)}"
        if c < 0.46:
            return f"{self.entity(d - 1)} {self.r.choice(['==', '!='])} {self.entity(d - 1)}"
        if c < 0.55:
            return f"({self.bool(d - 1)}) && ({self.bool(d - 1)})"
        if c < 0.64:
            return f"({self.bool(d - 1)}) || ({self.bool(d - 1)})"
        if c < 0.69:
            return f"!({self.bool(d - 1)})"
        if c < 0.76:
            holder = self.r.choice(["context", "principal", "resource", "context.rec"])
            return f"{holder} has {self.r.choice(ATTRS + ['age', 'name', 'k', 'size'])}"
        if c < 0.82:
            return f"{self.string(d - 1)} like {self.r.choice(PATTERNS)}"
        if c < 0.88:
            return f"{self.entity(d - 1)} in {self.r.choice([self.sets(0), self.ent(), 'principal', 'context.who'])}"
        if c < 0.91:
            return f"{self.entity(d - 1)} is {self.r.choice(TYPES)}"
        if c < 0.93:
            return f"{self.entity(d - 1)} is {self.r.choice(TYPES)} in {self.ent()}"
        if c < 0.97:
            m = self.r.choice(["contains", "containsAll", "containsAny", "isEmpty"])
            if m == "isEmpty":
                return f"{self.sets(0)}.isEmpty()"
            arg = self.sets(0) if m != "contains" else self.r.choice([self.string(0), self.ent(), self.long(0)])
            return f"{self.sets(0)}.{m}({arg})"
        return f"if {self.bool(d - 1)} then {self.bool(d - 1)} else {self.bool(d - 1)}"

    def scope_part(self, kw):
        c = self.r.random()
        if c < 0.45:
            return kw
        if c < 0.65:
            return f"{kw} == {self.ent()}"
        if c < 0.8:
            return f"{kw} in {self.ent()}"
        if c < 0.9:
            return f"{kw} is {self.r.choice(TYPES)}"
        return f"{kw} is {self.r.choice(TYPES)} in {self.ent()}"

    def action_part(self):
        c = self.r.random()
        if c < 0.45:
            return "action"
        if c < 0.7:
            return f"action == {self.action_ent()}"
        if c < 0.85:
            return f"action in {self.action_ent()}"
        return "action in [" + ", ".join(self.action_ent() for _ in range(self.r.randint(1, 3))) + "]"

    def policy(self):
        effect = self.r.choice(["permit", "forbid"])
        conds = "".join(f"\n  {self.r.choice(['when', 'unless'])} {{ {self.bool(3)} }}" for _ in range(self.r.choice([0, 1, 1, 2])))
        return f"{effect}(\n  {self.scope_part('principal')},\n  {self.action_part()},\n  {self.scope_part('resource')}\n){conds};"

    def policy_set(self, n):
        return "\n\n".join(self.policy() for _ in range(n))

    # ---- requests -------------------------------------------------------------------------------
    def value(self):
        c = self.r.random()
        if c < 0.25:
            return self.r.choice([0, 1, 2, 3, 5, -1])
        if c < 0.45:
            return self.r.choice(["abc", "a", "b", "axc", "", "x1y2z", "abbc"])
        if c < 0.6:
            return self.r.choice([True, False])
        if c < 0.75:
            return [self.r.choice(["a", "abc", "b"]) for _ in range(self.r.randint(0, 3))]
        if c < 0.85:
            return {"__entity": {"type": self.r.choice(TYPES), "id": self.r.choice(IDS)}}
        return {"k": self.r.choice(["abc", "z", 1])}

    def request(self):
        ctx = {a: self.value() for a in ATTRS if self.r.random() < 0.7}
        if "who" in ctx and not (isinstance(ctx["who"], dict) and "__entity" in ctx["who"]):
            ctx["who"] = {"__entity": {"type": self.r.choice(TYPES), "id": self.r.choice(IDS)}}
        ents = []
        for t in TYPES:
            for i in IDS:
                if self.r.random() < 0.5:
                    attrs = {}
                    if self.r.random() < 0.7:
                        attrs["age"] = self.r.choice([5, 20, 40])
                    if self.r.random() < 0.7:
                        attrs["name"] = self.r.choice(["abc", "bob"])
                    if self.r.random() < 0.4:
                        attrs["size"] = self.r.choice([1, 100])
                    me = TYPES.index(t) * len(IDS) + IDS.index(i)       # parents only from earlier entities: no cycles
                    parents = [{"type": pt, "id": pi} for pt in TYPES for pi in IDS
                               if TYPES.index(pt) * len(IDS) + IDS.index(pi) < me and self.r.random() < 0.25]
                    ents.append({"uid": {"type": t, "id": i}, "attrs": attrs, "parents": parents})
        return {"principal": (self.r.choice(TYPES), self.r.choice(IDS)),
                "action": ("Action", self.r.choice(ACTIONS)),
                "resource": (self.r.choice(TYPES), self.r.choice(IDS)),
                "context": ctx, "entities": ents}


# ---- official engine -------------------------------------------------------------------------------

def _cedar_value(v):
    return v


def cedar_decide(policies: str, req: Dict) -> Tuple[bool, List[str], List[str]]:
    p, a, r = req["principal"], req["action"], req["resource"]
    request = {"principal": f'{p[0]}::"{p[1]}"', "action": f'{a[0]}::"{a[1]}"', "resource": f'{r[0]}::"{r[1]}"',
               "context": req["context"]}
    entities = list(req["entities"])
    res = cedarpy.is_authorized(request, policies, entities)
    assert res.decision != cedarpy.Decision.NoDecision, res.diagnostics.errors
    errs = sorted({m.group(0) for e in res.diagnostics.errors for m in [re.search(r"policy\d+", e)] if m})
    return res.decision == cedarpy.Decision.Allow, sorted(res.diagnostics.reasons), errs


# ---- generated Rust -------------------------------------------------------------------------------

def rs_value(v) -> str:
    if isinstance(v, bool):
        return f"Value::Bool({'true' if v else 'false'})"
    if isinstance(v, int):
        return f"Value::Long({v}i64)"
    if isinstance(v, str):
        return f"Value::Str({rust_str(v)}.to_string())"
    if isinstance(v, list):
        return "Value::Set(BTreeSet::from([" + ", ".join(rs_value(x) for x in v) + "]))"
    if "__entity" in v:
        e = v["__entity"]
        return f"Value::Entity(Uid::new({rust_str(e['type'])}, {rust_str(e['id'])}))"
    return "Value::Record(BTreeMap::from([" + ", ".join(f"({rust_str(k)}.to_string(), {rs_value(x)})" for k, x in v.items()) + "]))"


def rs_request(req: Dict) -> str:
    uid = lambda t, i: f"Uid::new({rust_str(t)}, {rust_str(i)})"  # noqa: E731
    lines = [f"let mut req = Request::new({uid(*req['principal'])}, {uid(*req['action'])}, {uid(*req['resource'])});"]
    for k, v in req["context"].items():
        lines.append(f"req.context.insert({rust_str(k)}.to_string(), {rs_value(v)});")
    for e in req["entities"]:
        attrs = ", ".join(f"({rust_str(k)}.to_string(), {rs_value(v)})" for k, v in e["attrs"].items())
        parents = ", ".join(uid(p["type"], p["id"]) for p in e["parents"])
        lines.append(f"req.entities.insert({uid(e['uid']['type'], e['uid']['id'])}, EntityData {{ "
                     f"attrs: BTreeMap::from([{attrs}]), parents: BTreeSet::from([{parents}]) }});")
    return "\n        ".join(lines)


def build_crate(cases: List[Tuple[str, List[Dict]]], compiler=None, funcs=None) -> str:
    """cases: [(policy source, [requests])]. Returns one Rust source file that prints a line per request."""
    compiler = compiler or CedarCompiler()
    parts = ["use std::collections::{BTreeMap, BTreeSet};",
             "mod cedar_rt {", compiler.runtime_source(), "}",
             "use cedar_rt::*;"]
    for i, (src, _) in enumerate(cases):
        parts.append(f"mod set{i} {{\n{compiler.compile(src, check_types=False)}\n}}")
    parts.append("fn main() {")
    for i, (_, reqs) in enumerate(cases):
        for j, req in enumerate(reqs):
            parts.append(f"    {{\n        {rs_request(req)}\n"
                         f"        let d = set{i}::evaluate_detailed(&req);\n"
                         f'        let reasons: Vec<String> = d.reasons.clone();\n'
                         f'        let errs: Vec<String> = d.errors.iter().map(|(id, _)| id.clone()).collect();\n'
                         f'        println!("{i} {j} {{}} {{}} {{}}", if d.allow {{ "A" }} else {{ "D" }}, reasons.join(","), errs.join(","));\n    }}')
    parts.append("}")
    return "\n".join(parts)


def run_rust(source: str, workdir: Path) -> Dict[Tuple[int, int], Tuple[bool, List[str], List[str]]]:
    rustc = find_rustc()
    workdir.mkdir(parents=True, exist_ok=True)
    src, exe = workdir / "diff.rs", workdir / "diff_bin"
    src.write_text(source, encoding="utf-8")
    done = subprocess.run([rustc, "--edition", "2021", "-A", "warnings", "-o", str(exe), str(src)],
                          capture_output=True, text=True)
    if done.returncode:
        raise RuntimeError("rustc failed:\n" + done.stderr[:4000])
    out = subprocess.run([str(exe)], capture_output=True, text=True, check=True).stdout
    results = {}
    for line in out.splitlines():
        parts = line.split(" ")
        i, j, decision = int(parts[0]), int(parts[1]), parts[2]
        reasons = sorted(x for x in parts[3].split(",") if x) if len(parts) > 3 else []
        errs = sorted(set(x for x in parts[4].split(",") if x)) if len(parts) > 4 else []
        results[(i, j)] = (decision == "A", reasons, errs)
    return results


def compare(cases: List[Tuple[str, List[Dict]]], workdir: Path) -> List[str]:
    """Returns a list of disagreements (empty = the compiled Rust matches Cedar on every request)."""
    rust = run_rust(build_crate(cases), workdir)
    bad = []
    for i, (src, reqs) in enumerate(cases):
        for j, req in enumerate(reqs):
            want = cedar_decide(src, req)
            got = rust[(i, j)]
            if want != got:
                bad.append(f"set {i} request {j}: cedar={want} grafc={got}\n--- policies\n{src}\n--- request\n{json.dumps(req, default=str)[:600]}")
    return bad
