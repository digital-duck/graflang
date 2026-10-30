"""spl2graph: lift an SPL workflow into a GraphLang graph IR (``*.graph.yaml``).

AST-direct (no LLM), sibling of spl3/spl2mmd.py.  Mapping:

    WORKFLOW inputs / outputs        -> INPUT node ``wf_entry`` / OUTPUT node ``wf_exit``
    GENERATE f(..) INTO @v           -> GENERATE   (config.function / arguments / model)
    CALL w(..) INTO @v               -> GENERATE   (config.procedure_ref = procedures.w)
    SOLVE @v := expr                 -> SOLVE      (config.expression)
    ASSERT expr [OTHERWISE ..]       -> ASSERT     (pass / fail), fail wired to the OTHERWISE body
    EVALUATE @x WHEN .. ELSE ..      -> chain of EVALUATE nodes (pass / fail)
    WHILE cond DO .. END             -> LOOP       (subgraph; unbound body inputs read the LOOP's inputs)
    CALL PARALLEL .. END             -> FORK, one GENERATE per branch, JOIN
    @v := expr                       -> CONTEXT    (action "set")
    RETRY / RAISE                    -> RECOVER    (action "retry" / "halt")
    COMMIT @v                        -> binds @v to wf_exit, triggers wf_exit
    LOGGING                          -> dropped (not part of the dataflow)

Control flow is explicit ``triggers`` edges, data flow is ``binds`` edges from the node that last
produced @var.  Anything the converter cannot map is skipped and reported in ``warnings``.
"""
from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass, field

from spl.ast_nodes import (
    AssignmentStatement, CallStatement, CreateFunctionStatement, CompoundCondition as CompoundConditionV2, Condition, CommitStatement, DoBlock, EvaluateStatement, FStringLiteral,
    GenerateIntoStatement, ListLiteral, Literal, LoggingStatement, MapLiteral, ParamRef, ProcedureStatement, RaiseStatement,
    RetryStatement, SemanticCondition, StorageSubscript, WhileStatement, WorkflowStatement,
)
from spl3.ast_nodes import (
    AssertStatement, CallParallelStatement, CompoundCondition, NoneLiteral, SetLiteral, SolveStatement, UnaryOp,
)

from graphlang.grafr.expr import FUNCS

GRAPH_VERSION = "1.0-graph"
_CALL = re.compile(r"\b([A-Za-z_]\w*)\(")
_SOLVE_MARK = re.compile(r"@@(\w+)@@")
_FSTR_VAR = re.compile(r"\{@(\w+)\}")


class NoWorkflowError(ValueError):
    """Raised when the script has no WORKFLOW to lift."""


# --------------------------------------------------------------------------- expressions

def expr_vars(obj) -> list[str]:
    """@variables referenced by an expression / condition, in first-use order."""
    found: list[str] = []

    def add(name):
        if name not in found:
            found.append(name)

    def walk(o):
        if isinstance(o, ParamRef):
            add(o.name.lstrip("@"))
        elif isinstance(o, FStringLiteral):
            for v in _FSTR_VAR.findall(o.template):
                add(v)
        elif isinstance(o, StorageSubscript):
            add(o.storage_var.lstrip("@"))
            walk(o.key)
        elif isinstance(o, str):
            for v in _SOLVE_MARK.findall(o):
                add(v)
        elif isinstance(o, (list, tuple)):
            for x in o:
                walk(x)
        elif isinstance(o, dict):
            for x in o.values():
                walk(x)
        elif dataclasses.is_dataclass(o):
            for f in dataclasses.fields(o):
                walk(getattr(o, f.name))

    walk(obj)
    return found


_OPS = {"=": "==", "<>": "!="}


def _quote(text: str) -> str:
    """Quote with ' unless the text has a ' and no \"; then \" (else triple quotes)."""
    text = text.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
    if "'" not in text:
        return "'" + text + "'"
    if '"' not in text:
        return '"' + text + '"'
    if "'''" not in text:
        return "'''" + text + "'''"
    return '"""' + text + '"""' 


def template(text: str) -> str:
    """SOLVE / ASSERT ``@@var@@`` markers -> GraphLang ``@in_var`` port references."""
    return _SOLVE_MARK.sub(lambda m: f"@in_{m.group(1)}", text)


def render(e, inport: bool = False) -> str:
    """Expression / condition -> GraphLang expression text.  ``inport`` writes ``@var`` as the node's
    own ``@in_var`` port (what EVALUATE / ASSERT / LOOP conditions read)."""
    if e is None:
        return ""
    if isinstance(e, ParamRef):
        return ("@in_" if inport else "@") + e.name.lstrip("@")
    if isinstance(e, Literal):
        if e.literal_type == "string":
            return _quote(str(e.value))
        if e.literal_type == "bool":
            return "TRUE" if e.value else "FALSE"
        return str(e.value)
    if isinstance(e, FStringLiteral):
        return "f" + _quote(e.template)
    if isinstance(e, NoneLiteral):
        return "NONE"
    if isinstance(e, StorageSubscript):
        return f"{'@in_' if inport else '@'}{e.storage_var.lstrip('@')}[{render(e.key, inport)}]"
    if isinstance(e, ListLiteral):
        return "[" + ", ".join(render(x, inport) for x in e.elements) + "]"
    if isinstance(e, SetLiteral):
        return "{" + ", ".join(render(x, inport) for x in e.elements) + "}"
    if isinstance(e, MapLiteral):
        return "{" + ", ".join(f"{render(k, inport)}: {render(v, inport)}" for k, v in e.pairs) + "}"
    if isinstance(e, CompoundConditionV2):
        parts = [render(e.conditions[0], inport)]
        for conj, c in zip(e.conjunctions, e.conditions[1:]):
            parts += [conj, render(c, inport)]
        return " ".join(parts)
    if isinstance(e, UnaryOp):
        return f"{e.operator} {render(e.operand, inport)}"
    if isinstance(e, CompoundCondition):
        return f"{render(e.left, inport)} {_OPS.get(e.operator, e.operator)} {render(e.right, inport)}"
    if isinstance(e, SemanticCondition):
        return e.semantic_value
    if getattr(e, "operator", None) == "IN" and getattr(e.right, "name", "") == "__in_list__":
        left = render(e.left, inport)  # no IN in GraphLang expressions: expand to ORs
        return "(" + " OR ".join(f"{left} == {render(a, inport)}" for a in e.right.arguments) + ")"
    if hasattr(e, "left") and hasattr(e, "operator") and hasattr(e, "right"):  # Condition / Comparison
        return f"{render(e.left, inport)} {_OPS.get(e.operator, e.operator)} {render(e.right, inport)}"
    if hasattr(e, "left") and hasattr(e, "op") and hasattr(e, "right"):        # BinaryOp
        return f"{render(e.left, inport)} {e.op} {render(e.right, inport)}"
    if hasattr(e, "arguments") and hasattr(e, "name"):                          # FunctionCall
        return f"{e.name}({', '.join(render(a, inport) for a in e.arguments)})"
    if hasattr(e, "name") and hasattr(e, "value"):                              # NamedArg
        return f"{e.name}={render(e.value, inport)}"
    if hasattr(e, "name"):                                                      # Identifier
        return str(e.name)
    if hasattr(e, "parts"):                                                     # DottedName
        return ".".join(e.parts)
    return str(e)


def _semantic(value: str) -> str:
    """SemanticCondition -> expression over the subject port (deterministic forms are expanded)."""
    q = lambda t: "'" + t.replace("'", "\\'") + "'"
    if value.startswith("contains:"):
        return " OR ".join(f"contains(@in_subject, {q(v)})" for v in value[len("contains:"):].split("|"))
    if value.startswith("startswith:"):
        return f"startswith(@in_subject, {q(value[len('startswith:'):])})"
    return f"@in_subject == {q(value)}"


# --------------------------------------------------------------------------- scope

@dataclass
class _Scope:
    """One node/edge list (the workflow, or a LOOP body) plus its control frontier."""
    nodes: list = field(default_factory=list)
    edges: list = field(default_factory=list)
    producers: dict = field(default_factory=dict)   # var -> ["node.out_var", ...] that may hold it here
    frontier: list = field(default_factory=list)    # [(node_id, control_port)] awaiting a successor
    used: list = field(default_factory=list)        # vars read here but not produced here


class SPLToGraphConverter:
    """Convert one ``WorkflowStatement`` to a GraphLang graph dict."""

    def __init__(self, workflows: set[str] | None = None, source_name: str = "", source_dir=None,
                 procedures: dict[str, str] | None = None, functions: dict | None = None):
        self._workflows = workflows or set()   # workflows defined in the same .spl file
        self._functions = functions or {}      # name -> CREATE FUNCTION in the same file: its body is the prompt
        self._source_name = source_name
        self._known = procedures or {}         # name -> path, for callees that live outside this text
        self._source_dir = source_dir          # sibling <name>.spl files count as procedures too
        self.warnings: list[str] = []
        self._counters: dict[str, int] = {}
        self._procedures: dict[str, str] = {}
        self._wf: WorkflowStatement | None = None
        self._scope = _Scope()
        self._depth = 0                        # > 0 inside a LOOP body

    # -- helpers ------------------------------------------------------------
    def _id(self, prefix: str) -> str:
        n = self._counters[prefix] = self._counters.get(prefix, 0) + 1
        return f"{prefix}_{n}"

    def _warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def _add(self, node_id, ntype, ports, config=None, *, trigger=True) -> str:
        sc = self._scope
        node = {"id": node_id, "type": ntype}
        if config:
            node["config"] = config
        node["ports"] = list(ports)
        sc.nodes.append(node)
        if trigger:
            for src, port in sc.frontier:
                sc.edges.append({"source": f"{src}.{port}", "target": f"{node_id}.trigger", "type": "triggers"})
        return node_id

    def _bind_inputs(self, node_id: str, variables: list[str], renames: dict | None = None) -> list[str]:
        """Add in_<var> ports + binds edges from the producers; returns the in_ port names."""
        sc = self._scope
        node = next(n for n in sc.nodes if n["id"] == node_id)
        ports = []
        for v in variables:
            port = f"in_{(renames or {}).get(v, v)}"
            if port not in node["ports"]:
                node["ports"].append(port)
            ports.append(port)
            if v in sc.producers:
                for src in sc.producers[v]:
                    sc.edges.append({"source": src, "target": f"{node_id}.{port}", "type": "binds"})
            elif v not in sc.used:
                sc.used.append(v)
        return ports

    def _produce(self, node_id: str, var: str) -> None:
        node = next(n for n in self._scope.nodes if n["id"] == node_id)
        port = f"out_{var}"
        if port not in node["ports"]:
            node["ports"].append(port)
        self._scope.producers[var] = [f"{node_id}.{port}"]

    def _join_producers(self, before: dict, branches: list) -> None:
        """After branches meet, a variable may come from any branch that continues (phi)."""
        sc = self._scope
        merged: dict = {}
        for producers, continues in branches:
            if not continues:
                continue
            for var, srcs in producers.items():
                have = merged.setdefault(var, [])
                have += [x for x in srcs if x not in have]
        sc.producers = merged if merged else {k: list(v) for k, v in before.items()}

    def _step(self, node_id: str, port: str = "complete") -> None:
        self._scope.frontier = [(node_id, port)]

    # -- entry point --------------------------------------------------------
    def convert_workflow(self, wf: WorkflowStatement) -> dict:
        self._wf = wf
        sc = self._scope = _Scope()
        entry = "wf_entry"
        sc.nodes.append({"id": entry, "type": "INPUT",
                         "ports": ["entry"] + [f"out_{i.name.lstrip('@')}" for i in wf.inputs]})
        for i in wf.inputs:
            sc.producers[i.name.lstrip("@")] = [f"{entry}.out_{i.name.lstrip('@')}"]
        sc.frontier = [(entry, "entry")]

        self._exit_ports = [f"in_{o.name.lstrip('@')}" for o in wf.outputs] or ["in_result"]
        self._block(wf.body)

        exit_node = {"id": "wf_exit", "type": "OUTPUT", "ports": ["trigger", "exit"] + self._exit_ports}
        sc.nodes.append(exit_node)
        for src, port in sc.frontier:
            sc.edges.append({"source": f"{src}.{port}", "target": "wf_exit.trigger", "type": "triggers"})

        graph = {
            "version": GRAPH_VERSION,
            "workflow": {
                "name": wf.name,
                "inputs": [self._param(i) for i in wf.inputs],
                "outputs": [{"name": o.name.lstrip("@"), "type": o.param_type or "TEXT"} for o in wf.outputs],
            },
        }
        if self._procedures:
            graph["resources"] = {"procedures": dict(self._procedures)}
        graph["nodes"] = sc.nodes
        graph["edges"] = sc.edges
        return graph

    @staticmethod
    def _param(p) -> dict:
        d = {"name": p.name.lstrip("@"), "type": p.param_type or "TEXT"}
        if p.default_value is not None:
            dv = p.default_value
            d["default"] = dv.value if isinstance(dv, Literal) and dv.literal_type != "bool" else (bool(dv.value) if isinstance(dv, Literal) else render(dv))
        return d

    # -- statements ---------------------------------------------------------
    def _block(self, stmts) -> None:
        for s in stmts:
            sc = self._scope
            if not sc.frontier and sc.nodes and not isinstance(s, LoggingStatement):
                # nothing leads here (an earlier RETURN / RAISE ended every path)
                self._warn(f"unreachable {type(s).__name__} skipped")
                continue
            self._statement(s)

    def _statement(self, s) -> None:
        if isinstance(s, GenerateIntoStatement):
            self._generate(s)
        elif isinstance(s, CallStatement):
            self._call(s)
        elif isinstance(s, CallParallelStatement):
            self._call_parallel(s)
        elif isinstance(s, SolveStatement):
            nid = self._add(self._id("solve"), "SOLVE", ["trigger", "complete"],
                            {"expression": template(s.python_template), **({"type": s.target_type} if s.target_type else {})})
            self._bind_inputs(nid, expr_vars(s.python_template))
            self._produce(nid, s.target_variable.lstrip("@"))
            self._step(nid)
        elif isinstance(s, AssertStatement):
            self._assert(s)
        elif isinstance(s, EvaluateStatement):
            self._evaluate(s)
        elif isinstance(s, WhileStatement):
            self._while(s)
        elif isinstance(s, AssignmentStatement):
            nid = self._add(self._id("set"), "CONTEXT", ["trigger", "complete"],
                            {"action": "set", "expression": render(s.expression)})
            self._bind_inputs(nid, expr_vars(s.expression))
            self._produce(nid, s.variable.lstrip("@"))
            self._step(nid)
        elif isinstance(s, RetryStatement):
            nid = self._add(self._id("retry"), "RECOVER", ["trigger", "retry"], {"action": "retry"})
            self._step(nid, "retry")
        elif isinstance(s, RaiseStatement):
            nid = self._add(self._id("raise"), "RECOVER", ["trigger", "halt"],
                            {"action": "halt", "exception": s.exception_type,
                             **({"message": s.message} if s.message else {})})
            self._scope.frontier = []
        elif isinstance(s, CommitStatement):
            self._commit(s)
        elif isinstance(s, LoggingStatement):
            pass
        elif isinstance(s, DoBlock):
            self._block(s.statements)
            if s.exception_handlers:
                self._warn("EXCEPTION handlers in a DO block were dropped")
        else:
            self._warn(f"skipped unsupported statement {type(s).__name__}")

    def _generate(self, s: GenerateIntoStatement) -> None:
        gc = s.generate_clause
        nid = self._generate_node(gc.function_name, gc.arguments, s.target_variable, gc.model, gc.output_budget, gc.temperature)
        self._step(nid)

    def _generate_node(self, function: str, arguments: list, target: str, model=None, output_budget=None,
                       temperature=None) -> str:
        """GENERATE node for `function(args)`. A function defined in this file gives its body as the prompt, each
        `{param}` becoming the port `in_param`, fed by the argument (a plain @var is bound; a literal is written into
        the prompt; anything else is computed by a SOLVE node first). Else the call text itself is the prompt."""
        fn = self._functions.get(function)
        bindings: list[tuple[str, str]] = []                   # (variable, parameter) to bind once the node exists
        if fn is None:
            args = ", ".join(render(a) for a in arguments)
            cfg: dict = {"function": function, "prompt_inline": f"{function}({args})"}
            self._warn(f"function {function!r} is not defined in this file: its call text is used as the prompt")
        else:
            prompt = fn.body.strip()
            for param, arg in zip(fn.parameters, arguments):
                mark = "{" + param.name + "}"
                if isinstance(arg, ParamRef):
                    prompt = prompt.replace(mark, "{{in_" + param.name + "}}")
                    bindings.append((arg.name.lstrip("@"), param.name))
                elif isinstance(arg, Literal):
                    prompt = prompt.replace(mark, str(arg.value))
                else:
                    var = self._compute(render(arg), arg)
                    prompt = prompt.replace(mark, "{{in_" + param.name + "}}")
                    bindings.append((var, param.name))
            cfg = {"function": function, "prompt_inline": prompt}
        if arguments and fn is None:
            cfg["arguments"] = [render(a) for a in arguments]
        if model:
            cfg["model"] = model
        if output_budget is not None:
            cfg["output_budget"] = output_budget
        if temperature is not None:
            cfg["temperature"] = temperature
        nid = self._add(self._id("gen"), "GENERATE", ["trigger", "complete"], cfg)
        if fn is None:
            self._bind_inputs(nid, expr_vars([arguments, model, output_budget]))
        else:
            for var, param in bindings:
                self._bind_inputs(nid, [var], {var: param})
            self._bind_inputs(nid, expr_vars([model, output_budget]))
        if target:
            self._produce(nid, target.lstrip("@"))
        return nid

    def _compute(self, expression: str, source) -> str:
        """A SOLVE node that evaluates `expression` first; returns the variable holding the result."""
        nid = self._add(self._id("calc"), "SOLVE", ["trigger", "complete"], {"expression": re.sub(r"@(\w+)", r"@in_\1", expression)})
        self._bind_inputs(nid, expr_vars(source))
        self._produce(nid, nid)
        self._step(nid)
        return nid

    def _is_procedure(self, name: str) -> bool:
        sibling = self._source_dir is not None and (self._source_dir / f"{name}.spl").exists()
        return name in self._workflows or sibling or name in self._known

    def _call(self, s: CallStatement, *, trigger=True, workflow=False) -> str:
        name = s.procedure_name
        args = [render(a) for a in s.arguments]
        if workflow or self._is_procedure(name):
            default = f"./{self._source_name}" if name in self._workflows else f"./{name}.spl"
            self._procedures.setdefault(name, self._known.get(name, default))
            nid = self._add(self._id("call"), "GENERATE", ["trigger", "complete"],
                            {"procedure_ref": f"procedures.{name}", **({"arguments": args} if args else {})},
                            trigger=trigger)
        else:  # a Python tool (@spl_tool): deterministic, so SOLVE rather than GENERATE
            nid = self._add(self._id("tool"), "SOLVE", ["trigger", "complete"],
                            {"expression": f"{name}({', '.join(args)})", "tool": name}, trigger=trigger)
        self._bind_inputs(nid, expr_vars(s.arguments))
        if s.target_variable:
            self._produce(nid, s.target_variable.lstrip("@"))
        if trigger:
            self._step(nid)
        return nid

    def _call_parallel(self, s: CallParallelStatement) -> None:
        sc = self._scope
        fork = self._add(self._id("fork"), "FORK", ["trigger"])
        join = self._id("join")
        branch_ids = []
        for b in s.branches:
            sc.frontier = [(fork, f"branch_{len(branch_ids) + 1}")]
            next(n for n in sc.nodes if n["id"] == fork)["ports"].append(f"branch_{len(branch_ids) + 1}")
            if b.workflow_name in self._functions and b.workflow_name not in self._workflows:
                branch_ids.append(self._generate_node(b.workflow_name, b.arguments, b.target_var))
            else:
                branch_ids.append(self._call(CallStatement(b.workflow_name, b.arguments, b.target_var or None),
                                             workflow=self._is_procedure(b.workflow_name)))
        sc.frontier = [(i, "complete") for i in branch_ids]
        self._add(join, "JOIN", ["trigger", "complete"])
        self._step(join)

    def _hoist_tool_calls(self, text: str) -> str:
        """A condition may only call the built-in functions. A call to anything else (a Python tool) becomes a SOLVE node
        that runs first; the condition reads its result instead."""
        out, pos = [], 0
        while True:
            m = next((m for m in _CALL.finditer(text, pos) if m.group(1) not in FUNCS), None)
            if m is None:
                break
            depth, i = 0, m.end() - 1
            while i < len(text):
                depth += (text[i] == "(") - (text[i] == ")")
                i += 1
                if depth == 0:
                    break
            call = text[m.start():i]
            nid = self._add(self._id("tool"), "SOLVE", ["trigger", "complete"], {"expression": call, "tool": m.group(1)})
            self._bind_inputs(nid, list(dict.fromkeys(re.findall(r"@in_(\w+)", call))))
            self._produce(nid, nid)
            self._step(nid)
            out.append(text[pos:m.start()] + f"@in_{nid}")
            pos = i
            self._hoisted.append(nid)
        return "".join(out) + text[pos:]

    def _assert(self, s: AssertStatement) -> None:
        self._hoisted: list[str] = []
        cond = self._hoist_tool_calls(template(s.python_template))
        nid = self._add(self._id("assert"), "ASSERT", ["trigger", "pass", "fail"], {"condition": cond})
        self._bind_inputs(nid, [*expr_vars(s.python_template), *self._hoisted])
        ends: list = [(nid, "pass")]
        if s.otherwise_body:
            before = {k: list(v) for k, v in self._scope.producers.items()}
            self._scope.frontier = [(nid, "fail")]
            self._block(s.otherwise_body)
            ends += self._scope.frontier
            self._join_producers(before, [(self._scope.producers, bool(self._scope.frontier)), (before, True)])
        else:
            ends.append((nid, "fail"))
        self._scope.frontier = ends

    def _evaluate(self, s: EvaluateStatement) -> None:
        sc = self._scope
        ends: list = []
        pending = list(sc.frontier)
        before = {k: list(v) for k, v in sc.producers.items()}
        outcomes: list = []
        for n_when, wc in enumerate(s.when_clauses, 1):
            sc.frontier = pending
            sc.producers = {k: list(v) for k, v in before.items()}
            c = wc.condition
            cfg: dict
            if isinstance(c, SemanticCondition):
                cond = True
                cfg = {"condition": _semantic(c.semantic_value)}
                if not c.semantic_value.startswith(("contains:", "startswith:")):
                    cfg["semantic"] = True
            else:
                cond = False
                if hasattr(c, "operator"):
                    cmp = Condition(s.expression, c.operator, c.right)
                    cfg = {"condition": render(cmp, True)}
                else:
                    cfg = {"condition": render(c, True)}
            cfg["branch"] = n_when  # 1-based WHEN index; graph2spl re-chains EVALUATE nodes by it
            nid = self._add(self._id("eval"), "EVALUATE", ["trigger", "pass", "fail"], cfg)
            vs = expr_vars(s.expression) + expr_vars(wc.condition)
            if cond:  # semantic: the subject is a single bound value
                self._bind_inputs(nid, expr_vars(s.expression), renames={v: "subject" for v in expr_vars(s.expression)})
            else:
                self._bind_inputs(nid, vs)
            sc.frontier = [(nid, "pass")]
            self._block(wc.statements)
            ends += sc.frontier
            outcomes.append((sc.producers, bool(sc.frontier)))
            pending = [(nid, "fail")]
        sc.frontier = pending
        sc.producers = {k: list(v) for k, v in before.items()}
        if s.else_statements:
            self._block(s.else_statements)
        outcomes.append((sc.producers, bool(sc.frontier)))
        sc.frontier = ends + sc.frontier
        self._join_producers(before, outcomes)

    def _while(self, s: WhileStatement) -> None:
        outer = self._scope
        body = self._scope = _Scope()
        self._depth += 1
        # Empty frontier: the body's first node has no trigger edge (LOOP starts nodes nothing triggers).
        self._block(s.body)
        self._scope = outer
        self._depth -= 1

        cond_vars = expr_vars(s.condition)
        produced = list(body.producers)
        reads = [v for v in dict.fromkeys(body.used + [v for v in cond_vars if v not in produced]) if v != "cycle"]
        lid = self._id("loop")
        cond = render(s.condition)
        for v in reads:  # LOOP inputs are read as @in_<var>; loop state (outputs, @cycle) stays bare
            cond = re.sub(rf"@{v}\b", f"@in_{v}", cond)
        cfg: dict = {"condition": cond}
        if s.max_iterations is not None:
            cfg["max_iterations"] = s.max_iterations
        cfg["outputs"] = {v: {"from": srcs[-1]} for v, srcs in body.producers.items()}
        cfg["subgraph"] = {"nodes": body.nodes, "edges": body.edges}
        self._add(lid, "LOOP", ["trigger", "loop", "exit"], cfg)
        self._bind_inputs(lid, reads)
        for v in produced:
            self._produce(lid, v)
        self._step(lid, "exit")

    def _commit(self, s: CommitStatement) -> None:
        sc = self._scope
        if self._depth:
            self._warn("COMMIT inside a WHILE body was skipped (a LOOP body cannot reach wf_exit)")
            return
        if not isinstance(s.expression, ParamRef):
            # a computed / literal value: build it in a node so wf_exit has one clear source
            out_name = self._exit_ports[0].removeprefix("in_")
            nid = self._add(self._id("set"), "CONTEXT", ["trigger", "complete"],
                            {"action": "set", "expression": render(s.expression)})
            self._bind_inputs(nid, expr_vars(s.expression))
            self._produce(nid, out_name)
            self._step(nid)
            names = [out_name]
        else:
            names = expr_vars(s.expression)
        for v in names:
            port = f"in_{v}" if f"in_{v}" in self._exit_ports else self._exit_ports[0]
            if v in sc.producers:
                for src in sc.producers[v]:
                    edge = {"source": src, "target": f"wf_exit.{port}", "type": "binds"}
                    if edge not in sc.edges:
                        sc.edges.append(edge)
        # RETURN leaves the workflow: wire this path to wf_exit and end it
        for src, port in sc.frontier:
            sc.edges.append({"source": f"{src}.{port}", "target": "wf_exit.trigger", "type": "triggers"})
        sc.frontier = []


# --------------------------------------------------------------------------- public API

def _parse(source: str):
    from spl.lexer import Lexer
    from spl3.parser import SPL3Parser

    return SPL3Parser(Lexer(source).tokenize()).parse().statements


def spl_to_graph(source: str, workflow: str | None = None, source_name: str = "", source_dir=None,
                 procedures: dict[str, str] | None = None) -> tuple[dict, list[str]]:
    """Parse SPL source; return (graph dict, warnings).  Default workflow: the last one defined
    (the entry point by SPL convention, callees come first)."""
    statements = _parse(source)
    wfs = [s for s in statements if isinstance(s, WorkflowStatement)]
    if not wfs:
        raise NoWorkflowError("no WORKFLOW found - spl2graph lifts agentic workflows only")
    if workflow:
        match = [w for w in wfs if w.name == workflow]
        if not match:
            raise NoWorkflowError(f"workflow {workflow!r} not found (have: {', '.join(w.name for w in wfs)})")
        wf = match[0]
    else:
        wf = wfs[-1]
    functions = {s.name: s for s in statements if isinstance(s, CreateFunctionStatement)}
    conv = SPLToGraphConverter({w.name for w in wfs}, source_name, source_dir, procedures, functions)
    return conv.convert_workflow(wf), conv.warnings


def graph_to_yaml(graph: dict) -> str:
    import yaml
    return yaml.safe_dump(graph, sort_keys=False, default_flow_style=False, allow_unicode=True)
