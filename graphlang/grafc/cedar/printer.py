"""Print a Cedar AST back to Cedar source (minimal parentheses). Used for diagnostics, composition output and
to check the parser: printing and re-parsing must give the same structure as the original."""

from typing import List, Optional
from .ast_nodes import *

# binding strength; higher binds tighter
P_IF, P_OR, P_AND, P_REL, P_ADD, P_MUL, P_UNARY, P_POSTFIX = range(8)
BIN_PREC = {"||": P_OR, "&&": P_AND, "==": P_REL, "!=": P_REL, "<": P_REL, "<=": P_REL, ">": P_REL, ">=": P_REL,
            "+": P_ADD, "-": P_ADD, "*": P_MUL}
ESCAPES = {'\\': '\\\\', '"': '\\"', '\n': '\\n', '\t': '\\t', '\r': '\\r', '\0': '\\0'}


def quote(s: str) -> str:
    out = []
    for ch in s:
        if ch in ESCAPES:
            out.append(ESCAPES[ch])
        elif ord(ch) < 0x20 or ord(ch) == 0x7f:
            out.append('\\u{%x}' % ord(ch))
        else:
            out.append(ch)
    return '"' + ''.join(out) + '"'


def quote_pattern(parts: List[Optional[str]]) -> str:
    out = []
    for p in parts:
        out.append('*' if p is None else quote(p)[1:-1].replace('*', '\\*'))
    return '"' + ''.join(out) + '"'


def _paren(text: str, prec: int, needed: int) -> str:
    return f"({text})" if prec < needed else text


def expr_prec(e: Expr) -> int:
    if isinstance(e, IfThenElse):
        return P_IF
    if isinstance(e, BinaryOp):
        return BIN_PREC[e.op]
    if isinstance(e, (InExpression, HasAttribute, LikeExpression, IsExpression)):
        return P_REL
    if isinstance(e, UnaryOp):
        return P_UNARY
    if isinstance(e, Literal) and e.literal_type == "Long" and e.value < 0:
        return P_UNARY
    return P_POSTFIX


def expr_to_cedar(e: Expr) -> str:
    if isinstance(e, Literal):
        if e.literal_type == "String":
            return quote(e.value)
        if e.literal_type == "Bool":
            return "true" if e.value else "false"
        return str(e.value)
    if isinstance(e, Variable):
        return e.name
    if isinstance(e, EntityRef):
        return f"{e.entity_type}::{quote(e.entity_id)}"
    if isinstance(e, AttributeAccess):
        obj = _paren(expr_to_cedar(e.object), expr_prec(e.object), P_POSTFIX)
        return f"{obj}.{e.attribute}" if _is_ident(e.attribute) else f"{obj}[{quote(e.attribute)}]"
    if isinstance(e, HasAttribute):
        obj = _paren(expr_to_cedar(e.object), expr_prec(e.object), P_ADD)
        return f"{obj} has {e.attribute}" if _is_ident(e.attribute) else f"{obj} has {quote(e.attribute)}"
    if isinstance(e, InExpression):
        return f"{_side(e.left, P_ADD)} in {_side(e.right, P_ADD)}"
    if isinstance(e, IsExpression):
        tail = f" in {_side(e.in_expr, P_ADD)}" if e.in_expr is not None else ""
        return f"{_side(e.left, P_ADD)} is {e.entity_type}{tail}"
    if isinstance(e, LikeExpression):
        return f"{_side(e.left, P_ADD)} like {quote_pattern(e.pattern)}"
    if isinstance(e, BinaryOp):
        prec = BIN_PREC[e.op]
        if prec == P_REL:                               # not chainable: both sides must be Add-level or tighter
            return f"{_side(e.left, P_ADD)} {e.op} {_side(e.right, P_ADD)}"
        left = _paren(expr_to_cedar(e.left), expr_prec(e.left), prec)               # left-associative
        right = _paren(expr_to_cedar(e.right), expr_prec(e.right), prec + 1)
        return f"{left} {e.op} {right}"
    if isinstance(e, UnaryOp):
        return f"{e.op}{_paren(expr_to_cedar(e.operand), expr_prec(e.operand), P_UNARY)}"
    if isinstance(e, IfThenElse):
        return f"if {expr_to_cedar(e.condition)} then {expr_to_cedar(e.then_expr)} else {expr_to_cedar(e.else_expr)}"
    if isinstance(e, SetLiteral):
        return "[" + ", ".join(expr_to_cedar(x) for x in e.elements) + "]"
    if isinstance(e, RecordLiteral):
        return "{" + ", ".join(f"{quote(k)}: {expr_to_cedar(v)}" for k, v in e.fields.items()) + "}"
    if isinstance(e, MethodCall):
        obj = _paren(expr_to_cedar(e.object), expr_prec(e.object), P_POSTFIX)
        return f"{obj}.{e.method}(" + ", ".join(expr_to_cedar(a) for a in e.arguments) + ")"
    if isinstance(e, ExtensionCall):
        return f"{e.function}(" + ", ".join(expr_to_cedar(a) for a in e.arguments) + ")"
    raise TypeError(f"cannot print {type(e).__name__}")


def _side(e: Expr, needed: int) -> str:
    return _paren(expr_to_cedar(e), expr_prec(e), needed)


def _is_ident(name: str) -> bool:
    return bool(name) and (name[0].isalpha() or name[0] == '_') and all(c.isalnum() or c == '_' for c in name) \
        and name.isascii()


def _scope_part(keyword: str, c) -> str:
    if c.op == "_":
        return keyword
    if c.op == "eq":
        return f"{keyword} == {expr_to_cedar(c.entity)}"
    if c.op == "in":
        return f"{keyword} in {expr_to_cedar(c.entity)}"
    if c.op == "is":
        return f"{keyword} is {c.entity_type}"
    return f"{keyword} is {c.entity_type} in {expr_to_cedar(c.entity)}"


def policy_to_cedar(p: Policy) -> str:
    lines = [f"@{a.name}({quote(a.value)})" if a.value is not None else f"@{a.name}" for a in p.annotations]
    s = p.scope
    if s.action.op == "_":
        action = "action"
    elif s.action.op == "eq":
        action = f"action == {expr_to_cedar(s.action.entities[0])}"
    else:
        action = "action in [" + ", ".join(expr_to_cedar(x) for x in s.action.entities) + "]"
    lines.append(f"{p.effect.value}(")
    lines.append(f"    {_scope_part('principal', s.principal)},")
    lines.append(f"    {action},")
    lines.append(f"    {_scope_part('resource', s.resource)}")
    lines.append(")")
    for c in p.conditions:
        lines.append(f"{c.kind} {{ {expr_to_cedar(c.body)} }}")
    return "\n".join(lines) + ";"


def to_cedar(policy_set: PolicySet) -> str:
    return "\n\n".join(policy_to_cedar(p) for p in policy_set.policies) + ("\n" if policy_set.policies else "")
