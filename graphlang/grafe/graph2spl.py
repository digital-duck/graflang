"""graph2spl (`graf export-spl`): write SPL source from a GraphLang graph (``*.graph.yaml``).  Inverse of SPL.py's spl2graph.
Needs nothing from SPL.py: it only writes `.spl` text.

Structured reconstruction (no LLM): follows `triggers` edges from the entry node, turns EVALUATE /
ASSERT branches back into EVALUATE..WHEN / ASSERT..OTHERWISE blocks (the branches meet again at the
nearest common successor), LOOP subgraphs into WHILE, FORK..JOIN into CALL PARALLEL.

spl2graph drops LOGGING, EXCEPTION handlers, CREATE FUNCTION bodies and early COMMITs, so graph2spl
cannot bring them back; the contract is a fixed point, not a text match (tests/test_export_spl.py checks it when SPL.py
is installed):

    graph == spl_to_graph(graph_to_spl(graph))

A function whose prompt the graph carries comes back as CREATE FUNCTION, a Python tool as CREATE TOOL_API. Features SPL
has no word for (lifecycle phases, typed ports, bindings) are dropped and reported in the warnings.
"""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

_IN_PORT = re.compile(r"@in_(\w+)")
_IND = "  "
_IN_SUBJECT = re.compile(r"\(@in_(\w+) == ")
_COMPARE = re.compile(r"(.+?) (==|!=|>=|<=|>|<) (.+)")


class GraphToSPLError(ValueError):
    """The graph cannot be turned back into SPL."""


def _var(port: str) -> str:
    return port.split(".")[-1].removeprefix("out_").removeprefix("in_")


_STRING = re.compile(r'\'(?:[^\'\\]|\\.)*\'|"(?:[^"\\]|\\.)*"')


def _solve_template(expr: str) -> str:
    """SOLVE / ASSERT expression: ``@in_x`` -> ``@x`` (the parser adds the @@x@@ markers itself).
    Inside a string literal the parser leaves text alone, so the marker is written out as ``@@x@@``."""
    out, pos = [], 0
    for m in _STRING.finditer(expr):
        out.append(_IN_PORT.sub(r"@\1", expr[pos:m.start()]))
        out.append(_IN_PORT.sub(r"@@\1@@", m.group(0)))
        pos = m.end()
    out.append(_IN_PORT.sub(r"@\1", expr[pos:]))
    return "".join(out)


def _spl_condition(cond: str) -> str:
    """GraphLang condition (``@in_x``, ``==``) -> SPL WHILE condition (``@x``, ``=``)."""
    return _IN_PORT.sub(r"@\1", cond).replace(" == ", " = ").replace(" != ", " != ")


class _Scope:
    """One node/edge set (the workflow or a LOOP body) with control/data lookups."""

    def __init__(self, nodes: list, edges: list):
        self.nodes = {n["id"]: n for n in nodes}
        self.order = [n["id"] for n in nodes]
        self.succ: dict[tuple, list] = defaultdict(list)
        self.bound: dict[tuple, str] = {}        # (node, in_port) -> source "node.out_port"
        self.bound_all: dict[tuple, list] = defaultdict(list)
        self.has_trigger: set = set()
        for e in edges:
            src, sport = e["source"].split(".")
            tgt, tport = e["target"].split(".")
            if e["type"] == "triggers":
                self.succ[(src, sport)].append(tgt)
                self.has_trigger.add(tgt)
            else:
                self.bound[(tgt, tport)] = e["source"]
                self.bound_all[(tgt, tport)].append(e["source"])
        self._reach: dict[str, set] = {}

    def reach(self, nid: str) -> set:
        if nid not in self._reach:
            seen, todo = set(), [nid]
            while todo:
                cur = todo.pop()
                if cur in seen:
                    continue
                seen.add(cur)
                for port in self.nodes[cur]["ports"]:
                    todo.extend(self.succ.get((cur, port), []))
            self._reach[nid] = seen
        return self._reach[nid]

    def after(self, nid: str, port: str):
        t = self.succ.get((nid, port), [])
        return t[0] if t else None

    def merge(self, starts: list):
        """Nearest node reached by the most branches (>= 2); None if the branches never meet."""
        sets = [self.reach(s) for s in starts if s]
        count: dict[str, int] = defaultdict(int)
        for r in sets:
            for n in r:
                if self.nodes[n]["type"] != "OUTPUT":  # each path returns for itself
                    count[n] += 1
        if not count or max(count.values()) < 2:
            return None
        best = [n for n, c in count.items() if c == max(count.values())]
        for c in best:  # the earliest: it reaches every other candidate
            if all(o in self.reach(c) for o in best):
                return c
        return None

    def out_var(self, nid: str):
        outs = [p for p in self.nodes[nid]["ports"] if p.startswith("out_")]
        return outs[0][4:] if outs else None


class GraphToSPL:
    def __init__(self, graph: dict):
        self.graph = graph
        self.warnings: list[str] = []
        self.functions: list[str] = []
        self.defs: dict[str, str] = {}           # function name -> its CREATE FUNCTION text
        self._joined = None
        self.tools: list[str] = []
        self.procedures = set((graph.get("resources") or {}).get("procedures", {}))

    # -- public -------------------------------------------------------------
    def convert(self) -> str:
        g = self.graph
        top = _Scope(g["nodes"], g["edges"])
        wf = g["workflow"]
        entry = next((n for n in g["nodes"] if n["type"] == "INPUT"), None)
        if entry is None:
            raise GraphToSPLError("no INPUT node: not a GraphLang workflow graph")
        self._note_unsupported(g["nodes"])
        body = self._seq(top, top.after(entry["id"], "entry"), None, 1, entry["id"])
        head = [f"WORKFLOW {wf['name']}"]
        if wf.get("inputs"):
            head.append(_IND + "INPUT:")
            head.append(",\n".join(_IND * 2 + self._param(p) for p in wf["inputs"]))
        if wf.get("outputs"):
            head.append(_IND + "OUTPUT: " + ", ".join(self._param(p) for p in wf["outputs"]))
        head.append("DO")

        lines = ["-- generated by `graf export-spl`"]
        for name, path in (g.get("resources") or {}).get("procedures", {}).items():
            lines.append(f"-- procedure {name}: {path}")
        if self.functions:
            lines.append("-- define before running: CREATE FUNCTION " + ", ".join(dict.fromkeys(self.functions)))
        if self.tools:
            lines.append("-- tools used (@spl_tool): " + ", ".join(dict.fromkeys(self.tools)))
        lines += [""] + [d for d in self.defs.values()] + head + body + ["END", ""]
        return "\n".join(lines)

    def _note_unsupported(self, nodes: list) -> None:
        for n in nodes:
            phases = {k: v for k, v in n.get("config", {}).get("phases", {}).items()
                      if not (k == "pre" and set(v) == {"defaults"} and n["type"] == "GENERATE" and "params" in n["config"])}
            if phases:
                self.warnings.append(f"node {n['id']!r}: lifecycle phases {sorted(phases)} have no SPL form and were dropped")
            if n.get("config", {}).get("subgraph"):
                self._note_unsupported(n["config"]["subgraph"]["nodes"])

    # -- pieces -------------------------------------------------------------
    @staticmethod
    def _param(p: dict) -> str:
        out = f"@{p['name']} {p.get('type', 'TEXT')}"
        if "default" in p:
            d = p["default"]
            if isinstance(d, bool):
                d = "TRUE" if d else "FALSE"
            elif isinstance(d, str):
                d = "''" if d == "" else "'" + d.replace("\\", "\\\\").replace("'", "\\'") + "'"
            out += f" := {d}"
        return out

    def _return(self, sc: _Scope, prev: str, out_node: dict):
        """RETURN for the path that reaches wf_exit from `prev`: the latest producer on that path."""
        for port in out_node["ports"]:
            srcs = sc.bound_all.get((out_node["id"], port), [])
            cands = [s for s in srcs if prev in sc.reach(s.split(".")[0])]
            for c in cands:
                if all(c.split(".")[0] in sc.reach(o.split(".")[0]) for o in cands):
                    return f"RETURN @{_var(c)}"
            if cands and len({_var(c) for c in cands}) == 1:  # branches each assigned the same variable
                return f"RETURN @{_var(cands[0])}"
        return None

    def _seq(self, sc: _Scope, cur, stop, depth: int, prev=None) -> list:
        ind = _IND * depth
        out: list[str] = []
        guard = 0
        while cur and cur != stop:
            guard += 1
            if guard > 10_000:
                raise GraphToSPLError("control flow does not terminate (cycle?)")
            n = sc.nodes[cur]
            t = n["type"]
            if t == "OUTPUT":
                ret = self._return(sc, prev, n)
                if ret:
                    out.append(ind + ret)
                break
            prev = cur
            if t in ("GENERATE", "SOLVE", "CONTEXT"):
                out.append(ind + self._simple(sc, n))
                cur = sc.after(cur, "complete")
            elif t == "RECOVER":
                cfg = n.get("config", {})
                if cfg.get("action") == "retry":
                    out.append(ind + "RETRY")
                    cur = sc.after(cur, "retry")
                else:
                    msg = cfg.get("message")
                    out.append(ind + f"RAISE {cfg.get('exception', 'Error')}" + (f" '{msg}'" if msg else ""))
                    cur = None
            elif t == "ASSERT":
                cur = self._assert(sc, n, out, depth)
            elif t == "EVALUATE":
                cur = self._evaluate(sc, n, out, depth)
            elif t == "LOOP":
                cur = self._loop(sc, n, out, depth)
            elif t == "FORK":
                cur = self._fork(sc, n, out, depth)
                prev = self._joined or prev
            else:
                self.warnings.append(f"node {cur!r}: unsupported type {t}, skipped")
                cur = sc.after(cur, "complete")
        return out

    def _simple(self, sc: _Scope, n: dict) -> str:
        cfg, t = n.get("config", {}), n["type"]
        var = sc.out_var(n["id"])
        if t == "CONTEXT":
            return f"@{var} := {cfg['expression']}"
        if t == "SOLVE" and "tool" in cfg:
            self.tools.append(cfg["tool"])
            call = cfg["expression"] if "expression" in cfg else f"{cfg['tool']}({', '.join(cfg.get('arguments', []))})"
            if "tool_params" in cfg and not cfg.get("tool_builtin"):
                self._define_tool(cfg)
            return f"CALL {call} INTO {'@' + var if var else 'NONE'}"
        if t == "SOLVE":
            ty = f" {cfg['type']}" if cfg.get("type") else ""
            return f"SOLVE @{var}{ty} := {_solve_template(cfg['expression'])};"
        args = ", ".join(cfg.get("arguments", []))
        ref = cfg.get("procedure_ref")
        if ref:
            return f"CALL {ref.split('.', 1)[-1]}({args}) INTO {'@' + var if var else 'NONE'}"
        if "function" not in cfg:                                  # written by hand, not lifted from SPL
            cfg, args = self._native_function(sc, n, cfg)
        self._define(cfg)
        s = f"GENERATE {cfg['function']}({args})"
        if cfg.get("output_budget") is not None:
            s += f" WITH OUTPUT BUDGET {cfg['output_budget']} TOKENS"
        if cfg.get("model"):
            m = cfg["model"]
            s += f" USING MODEL {m if m.startswith('@') else repr(m)}"
        return s + f" INTO @{var}"

    def _prompt_text(self, cfg: dict) -> str:
        if "prompt_inline" in cfg:
            return cfg["prompt_inline"]
        if "prompt_ref" in cfg:
            kind, _, name = cfg["prompt_ref"].partition(".")
            rel = (self.graph.get("resources") or {}).get(kind + "s" if not kind.endswith("s") else kind, {}).get(name)
            if rel is None:
                raise GraphToSPLError(f"prompt {cfg['prompt_ref']!r} is not listed under resources")
            path = Path(self.graph.get("_source_dir", ".")) / rel
            if path.suffix == ".md" or path.is_file():
                return path.read_text(encoding="utf-8").strip()
        raise GraphToSPLError("GENERATE node has no prompt_inline or readable prompt_ref")

    def _native_function(self, sc: _Scope, n: dict, cfg: dict) -> tuple:
        """A GENERATE written in GraphLang becomes a function named after the node: its inputs are the parameters, its prompt the
        body, its bound or default values the arguments."""
        params = [p[3:] for p in n["ports"] if p.startswith("in_")]
        defaults = cfg.get("phases", {}).get("pre", {}).get("defaults", {})
        args = []
        for p in params:
            src = sc.bound.get((n["id"], f"in_{p}"))
            if src is not None:
                args.append("@" + _var(src))
            elif f"in_{p}" in defaults:
                d = defaults[f"in_{p}"]
                args.append(repr(d) if isinstance(d, str) else str(d))
            else:
                args.append(f"@{p}")                           # a loop's own input, or a workflow input of that name
        body = self._prompt_text(cfg)
        for p in params:
            body = body.replace("{{in_" + p + "}}", "{" + p + "}")
        return {**cfg, "function": n["id"], "params": params, "prompt_inline": body}, ", ".join(args)

    def _define_tool(self, cfg: dict) -> None:
        """The tool's Python source is in the node's code, ahead of the line that calls it."""
        name = cfg["tool"]
        body = cfg["code"].rsplit(f"_spl_result = {name}(", 1)[0].strip("\n")
        params = ", ".join(f"{p} TEXT" for p in cfg["tool_params"])
        self.defs.setdefault(f"tool:{name}", f"CREATE TOOL_API {name}({params})\nRETURNS {cfg.get('tool_returns', 'TEXT')} AS PYTHON $$\n{body}\n$$;\n")

    def _define(self, cfg: dict) -> None:
        """A function the graph carries a prompt for gets its CREATE FUNCTION back; else it is only named in a comment."""
        name = cfg["function"]
        if "params" not in cfg:
            self.functions.append(name)
            return
        body = re.sub(r"\{\{in_(\w+)\}\}", r"{\1}", cfg["prompt_inline"])
        params = ", ".join(f"{p} TEXT" for p in cfg["params"])
        text = f"CREATE FUNCTION {name}({params})\nRETURNS TEXT AS $$\n{body}\n$$;\n"
        if self.defs.setdefault(name, text) != text:
            self.warnings.append(f"function {name!r} is used with different prompts; the first one is kept")

    def _assert(self, sc, n, out, depth):
        ind = _IND * depth
        nid = n["id"]
        p, f = sc.after(nid, "pass"), sc.after(nid, "fail")
        head = f"ASSERT {_solve_template(n['config']['condition'])}"
        if f is None or f == p:
            out.append(ind + head + ";")
            return p
        body = self._seq(sc, f, p, depth + 1, nid)
        if len(body) == 1:
            out.append(ind + head + "\n" + ind + _IND + "OTHERWISE " + body[0].strip())
        else:
            out += [ind + head, ind + _IND + "OTHERWISE DO"] + [_IND + b for b in body] + [ind + _IND + "END"]
        return p

    def _evaluate(self, sc, n, out, depth):
        ind = _IND * depth
        chain = [n]
        while True:  # WHEN k+1 is reached through WHEN k's fail port
            nxt = sc.after(chain[-1]["id"], "fail")
            nn = sc.nodes.get(nxt) if nxt else None
            if (nn and nn["type"] == "EVALUATE"
                    and nn.get("config", {}).get("branch") == chain[-1].get("config", {}).get("branch", 0) + 1):
                chain.append(nn)
            else:
                break
        else_start = sc.after(chain[-1]["id"], "fail")
        starts = [sc.after(c["id"], "pass") for c in chain] + [else_start]
        m = sc.merge(starts)
        cfg0 = chain[0].get("config", {})
        subj = sc.bound.get((chain[0]["id"], "in_subject"))
        in_ = _IN_SUBJECT.match(cfg0.get("condition", "")) if subj is None else None
        cmp_ = _COMPARE.match(cfg0.get("condition", "")) if subj is None and not in_ else None
        if subj is not None:
            subject = f"@{_var(subj)}"
        elif in_:
            subject = "@" + in_.group(1)
        elif cmp_:
            subject = _IN_PORT.sub(r"@\1", cmp_.group(1))
        else:
            subject = "@subject"
            self.warnings.append(f"EVALUATE {n['id']!r}: subject not recoverable")
        out.append(ind + f"EVALUATE {subject}")
        for c in chain:
            out.append(ind + _IND + f"WHEN {self._when(c['config'])} THEN")
            out += self._seq(sc, sc.after(c["id"], "pass"), m, depth + 2, c["id"])
        else_body = self._seq(sc, else_start, m, depth + 2, chain[-1]["id"])
        if else_body:
            out.append(ind + _IND + "ELSE")
            out += else_body
        out.append(ind + "END")
        return m

    @staticmethod
    def _when(cfg: dict) -> str:
        c = cfg["condition"]
        subj = r"@in_\w+"
        if m := re.fullmatch(rf"(?:contains\({subj}, '((?:[^'\\]|\\.)*)'\)(?: OR )?)+", c):
            vals = re.findall(rf"contains\({subj}, '((?:[^'\\]|\\.)*)'\)", c)
            return " OR ".join(f"contains('{v}')" for v in vals)
        if m := re.fullmatch(rf"startswith\({subj}, '((?:[^'\\]|\\.)*)'\)", c):
            return f"STARTSWITH '{m.group(1)}'"
        if cfg.get("semantic") and (m := re.fullmatch(rf"{subj} == '((?:[^'\\]|\\.)*)'", c)):
            return f"'{m.group(1)}'"
        if m := re.fullmatch(r"\((@in_\w+ == .+)\)", c):  # IN (...) expanded to ORs
            vals = re.findall(r"@in_\w+ == ('(?:[^'\\]|\\.)*'|[^ )]+)", m.group(1))
            return "IN (" + ", ".join(vals) + ")"
        if m := _COMPARE.match(c):
            op = "=" if m.group(2) == "==" else m.group(2)
            rhs = _IN_PORT.sub(r"@\1", m.group(3))
            return f"{op} {rhs}"
        return _IN_PORT.sub(r"@\1", c)

    def _loop(self, sc, n, out, depth):
        ind = _IND * depth
        cfg = n["config"]
        sub = cfg["subgraph"]
        body = _Scope(sub["nodes"], sub["edges"])
        starts = [i for i in body.order if i not in body.has_trigger]
        if len(starts) > 1:
            self.warnings.append(f"LOOP {n['id']!r}: {len(starts)} start nodes, using the first")
        out.append(ind + f"WHILE {_spl_condition(cfg['condition'])} DO")
        out += self._seq(body, starts[0] if starts else None, None, depth + 1)
        out.append(ind + "END")
        return sc.after(n["id"], "exit")

    def _fork(self, sc, n, out, depth):
        ind = _IND * depth
        starts = [sc.after(n["id"], p) for p in n["ports"] if p.startswith("branch_")]
        join = sc.merge(starts)
        out.append(ind + "CALL PARALLEL")
        for s in starts:
            node = sc.nodes[s]
            ref = node.get("config", {}).get("procedure_ref")
            if not ref:
                self.warnings.append(f"FORK branch {s!r} is not a workflow call, skipped")
                continue
            var = sc.out_var(s)
            args = ", ".join(node["config"].get("arguments", []))
            out.append(ind + _IND + f"{ref.split('.', 1)[-1]}({args}) INTO @{var}")
        out.append(ind + "END")
        self._joined = join
        return sc.after(join, "complete") if join else None


def graph_to_spl(graph: dict) -> tuple[str, list[str]]:
    """Return (SPL source, warnings)."""
    conv = GraphToSPL(graph)
    text = conv.convert()
    return text, conv.warnings
