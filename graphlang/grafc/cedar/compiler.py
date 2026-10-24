"""Cedar to Rust code generator.

Each policy becomes a Rust function over `cedar_rt::Request`; the module's `evaluate_detailed` applies
Cedar's decision rule (see rust_gen/templates/cedar_rt.rs, which implements the evaluation semantics and must
be shipped beside the generated module as `cedar_rt.rs`). Generated code calls only that runtime, so its
behaviour is the runtime's, and `tests/test_cedar_differential.py` checks it against the official engine.

Not supported (rejected with CedarCompileError, never silently approximated): extension types and functions
(ip, decimal, datetime, duration and their methods), entity tags, and policy templates.
"""

from pathlib import Path
from typing import List

from .ast_nodes import *
from .errors import CedarCompileError
from .lexer import CedarLexer
from .parser import CedarParser
from .slicer import PolicySlicer, GuardNodeConfig
from .type_checker import CedarTypeChecker, SET_METHODS

RUNTIME_PATH = Path(__file__).resolve().parent.parent / "rust_gen" / "templates" / "cedar_rt.rs"
CMP_OPS = {"<", "<=", ">", ">="}


def rust_str(s: str) -> str:
    """A Rust string literal for s."""
    out = []
    for ch in s:
        if ch == '\\':
            out.append('\\\\')
        elif ch == '"':
            out.append('\\"')
        elif ch == '\n':
            out.append('\\n')
        elif ch == '\r':
            out.append('\\r')
        elif ch == '\t':
            out.append('\\t')
        elif ch == '\0':
            out.append('\\0')
        elif ord(ch) < 0x20 or ord(ch) == 0x7f:
            out.append('\\u{%x}' % ord(ch))
        else:
            out.append(ch)
    return '"' + ''.join(out) + '"'


def uid(ref: EntityRef) -> str:
    return f"Uid::new({rust_str(ref.entity_type)}, {rust_str(ref.entity_id)})"


class CedarCompiler:
    """Compiles Cedar policies to a Rust module."""

    @staticmethod
    def runtime_source() -> str:
        """The `cedar_rt.rs` the generated modules depend on."""
        return RUNTIME_PATH.read_text(encoding="utf-8")

    @staticmethod
    def parse(cedar_source: str) -> PolicySet:
        return CedarParser(CedarLexer(cedar_source).tokenize()).parse()

    def compile(self, cedar_source: str, func_name: str = "evaluate", check_types: bool = True) -> str:
        """Compile a whole policy set. `check_types=False` skips the definite-type-error check (used to test that
        the generated code reproduces Cedar's run-time errors too)."""
        return self.compile_policy_set(self.parse(cedar_source), func_name, check_types)

    def compile_sliced(self, cedar_source: str, guard_config: GuardNodeConfig) -> str:
        """Compile only the policies that can apply to a GUARD node's request (see PolicySlicer)."""
        sliced = PolicySlicer(self.parse(cedar_source)).slice_for_guard(guard_config)
        return self.compile_policy_set(sliced, f"evaluate_{guard_config.node_id}")

    def compile_policy_set(self, policy_set: PolicySet, func_name: str = "evaluate", check_types: bool = True) -> str:
        if check_types:
            checker = CedarTypeChecker()
            checker.check(policy_set)
            checker.raise_if_errors()
        lines = [
            "// Auto-generated from Cedar policies by grafc. DO NOT EDIT: regenerate from the .cedar source.",
            "// Needs cedar_rt.rs (CedarCompiler.runtime_source()) in the same crate.",
            "#![allow(unused_variables, unused_parens, unused_imports, dead_code)]",
            "use crate::cedar_rt::*;",
            "",
        ]
        for p in policy_set.policies:
            lines.extend(self._policy_fn(p))
        lines.append("/// Cedar's decision with the reasons and the policies that errored.")
        lines.append("pub fn evaluate_detailed(req: &Request) -> Decision {")
        lines.append("    let mut d = DecisionBuilder::new();")
        for p in policy_set.policies:
            lines.append(f'    d.run("{p.policy_id}", {"true" if p.effect == Effect.FORBID else "false"}, '
                         f'{p.policy_id}(req));')
        lines.append("    d.finish()")
        lines.append("}")
        lines.append("")
        lines.append(f"/// Fail closed: true only if the request is allowed and no policy errored.")
        lines.append(f"pub fn {func_name}(req: &Request) -> bool {{")
        lines.append("    evaluate_detailed(req).allowed()")
        lines.append("}")
        return "\n".join(lines) + "\n"

    # ---- policies -----------------------------------------------------------------------------
    def _policy_fn(self, p: Policy) -> List[str]:
        lines = []
        for a in p.annotations:
            if a.value is not None:
                lines.append(f"/// @{a.name}({a.value!r})".replace("\n", " "))
        lines.append(f"fn {p.policy_id}(req: &Request) -> Res<bool> {{")
        scope = self._scope(p.scope)
        if scope:
            lines.append(f"    if !({scope}) {{ return Ok(false); }}")
        for c in p.conditions:
            body = f"as_bool({self._expr(c.body)})?"
            lines.append(f"    if {'!' if c.kind == 'when' else ''}({body}) {{ return Ok(false); }}")
        lines.append("    Ok(true)")
        lines.append("}")
        lines.append("")
        return lines

    def _scope(self, s: PolicyScope) -> str:
        checks = []
        for var, c in (("principal", s.principal), ("resource", s.resource)):
            target = f"req.{var}"
            if c.op == "eq":
                checks.append(f"{target} == {uid(c.entity)}")
            elif c.op == "in":
                checks.append(f"entity_in(req, &{target}, &{uid(c.entity)})")
            elif c.op == "is":
                checks.append(f"{target}.ty == {rust_str(c.entity_type)}")
            elif c.op == "is_in":
                checks.append(f"{target}.ty == {rust_str(c.entity_type)} && entity_in(req, &{target}, &{uid(c.entity)})")
        a = s.action
        if a.op == "eq":
            checks.append(f"req.action == {uid(a.entities[0])}")
        elif a.op == "in":
            members = ", ".join(uid(e) for e in a.entities)
            checks.append(f"[{members}].iter().any(|u: &Uid| entity_in(req, &req.action, u))")
        return " && ".join(checks)

    # ---- expressions: each yields Rust of type Res<Value> -------------------------------------
    def _unsupported(self, what: str, at) -> CedarCompileError:
        return CedarCompileError(f"{what} is not supported by grafc", getattr(at, "line", 0), getattr(at, "column", 0))

    def _expr(self, e: Expr) -> str:
        if isinstance(e, Literal):
            if e.literal_type == "String":
                return f"lit_str({rust_str(e.value)})"
            if e.literal_type == "Bool":
                return f"lit_bool({'true' if e.value else 'false'})"
            return f"lit_long({e.value}i64)" if e.value != -2**63 else "lit_long(i64::MIN)"
        if isinstance(e, Variable):
            return f"var_{e.name}(req)"
        if isinstance(e, EntityRef):
            return f"lit_entity({rust_str(e.entity_type)}, {rust_str(e.entity_id)})"
        if isinstance(e, AttributeAccess):
            return f"attr(req, {self._expr(e.object)}, {rust_str(e.attribute)})"
        if isinstance(e, HasAttribute):
            return f"has(req, {self._expr(e.object)}, {rust_str(e.attribute)})"
        if isinstance(e, InExpression):
            return f"in_(req, {self._expr(e.left)}, {self._expr(e.right)})"
        if isinstance(e, IsExpression):
            is_ = f"is_({self._expr(e.left)}, {rust_str(e.entity_type)})"
            if e.in_expr is None:
                return is_
            return f"and_(|| {is_}, || in_(req, {self._expr(e.left)}, {self._expr(e.in_expr)}))"
        if isinstance(e, LikeExpression):
            parts = ", ".join("None" if p is None else f"Some({rust_str(p)})" for p in e.pattern)
            return f"like({self._expr(e.left)}, &[{parts}])"
        if isinstance(e, BinaryOp):
            l, r = self._expr(e.left), self._expr(e.right)
            if e.op == "&&":
                return f"and_(|| {l}, || {r})"
            if e.op == "||":
                return f"or_(|| {l}, || {r})"
            if e.op == "==":
                return f"eq({l}, {r})"
            if e.op == "!=":
                return f"neq({l}, {r})"
            if e.op in CMP_OPS:
                return f'cmp({l}, {r}, "{e.op}")'
            return f"arith({l}, {r}, '{e.op}')"
        if isinstance(e, UnaryOp):
            return f"not_({self._expr(e.operand)})" if e.op == "!" else f"neg({self._expr(e.operand)})"
        if isinstance(e, IfThenElse):
            return f"if_({self._expr(e.condition)}, || {self._expr(e.then_expr)}, || {self._expr(e.else_expr)})"
        if isinstance(e, SetLiteral):
            return "set_lit(vec![" + ", ".join(self._expr(x) for x in e.elements) + "])"
        if isinstance(e, RecordLiteral):
            return "record_lit(vec![" + ", ".join(f"({rust_str(k)}, {self._expr(v)})" for k, v in e.fields.items()) + "])"
        if isinstance(e, MethodCall):
            if e.method not in SET_METHODS:
                raise self._unsupported(f"the method .{e.method}()", e)
            return f"method({self._expr(e.object)}, {rust_str(e.method)}, vec![" + ", ".join(self._expr(a) for a in e.arguments) + "])"
        if isinstance(e, ExtensionCall):
            raise self._unsupported(f"the extension function {e.function}()", e)
        raise self._unsupported(type(e).__name__, e)
