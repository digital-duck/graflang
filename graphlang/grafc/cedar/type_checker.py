"""Best-effort, schema-less type checking of Cedar policies.

Cedar is checked against a schema; without one nothing is known about attribute types, so this checker
reports only *definite* errors (an expression that would raise at run time whatever the data is), such as
`1 && true`, `"a" < 3` or `!5`. Attributes and calls it cannot type are `ANY`, which is compatible with
everything. It also collects the entity types the policies mention.
"""

from typing import Dict, Set
from .ast_nodes import *
from .errors import CedarTypeError


class CedarType:
    def __init__(self, name: str):
        self.name = name

    def __repr__(self):
        return f"CedarType({self.name})"

    def __eq__(self, other):
        return isinstance(other, CedarType) and self.name == other.name

    def __hash__(self):
        return hash(self.name)


BOOL, LONG, STRING = CedarType("Bool"), CedarType("Long"), CedarType("String")
ENTITY, SET, RECORD = CedarType("Entity"), CedarType("Set"), CedarType("Record")
EXTENSION, ANY = CedarType("Extension"), CedarType("Any")

SET_METHODS = {"contains": 1, "containsAll": 1, "containsAny": 1, "isEmpty": 0}
EXTENSION_FUNCTIONS = {"ip", "decimal", "datetime", "duration"}


def compatible(actual: CedarType, wanted: CedarType) -> bool:
    return actual == wanted or actual == ANY


class CedarTypeChecker:
    def __init__(self):
        self.entity_types: Set[str] = set()
        self.errors: list = []

    def check(self, policy_set: PolicySet) -> bool:
        """Check every policy; returns True if no definite error was found (errors are in `self.errors`)."""
        for policy in policy_set.policies:
            self._scope(policy.scope)
            for condition in policy.conditions:
                t = self._check_expr(condition.body)
                if not compatible(t, BOOL):
                    self._error(f"a {condition.kind} condition must be Bool, got {t.name}", condition.body)
        return not self.errors

    def raise_if_errors(self) -> None:
        if self.errors:
            first = self.errors[0]
            more = f" (and {len(self.errors) - 1} more)" if len(self.errors) > 1 else ""
            raise CedarTypeError(first.message + more, first.line, first.column)

    def _error(self, message: str, at) -> None:
        self.errors.append(CedarTypeError(message, getattr(at, "line", 0), getattr(at, "column", 0)))

    def _scope(self, scope: PolicyScope) -> None:
        if not scope:
            return
        for c in (scope.principal, scope.resource):
            if c.entity is not None:
                self.entity_types.add(c.entity.entity_type)
            if c.entity_type:
                self.entity_types.add(c.entity_type)
        for e in scope.action.entities or []:
            self.entity_types.add(e.entity_type)

    def _need(self, expr: Expr, wanted: CedarType, why: str) -> CedarType:
        t = self._check_expr(expr)
        if not compatible(t, wanted):
            self._error(f"{why} requires {wanted.name}, got {t.name}", expr)
        return t

    def _check_expr(self, expr: Expr) -> CedarType:
        if isinstance(expr, Literal):
            return {"String": STRING, "Long": LONG, "Bool": BOOL}[expr.literal_type]
        if isinstance(expr, Variable):
            return RECORD if expr.name == "context" else ENTITY
        if isinstance(expr, EntityRef):
            self.entity_types.add(expr.entity_type)
            return ENTITY
        if isinstance(expr, AttributeAccess):
            t = self._check_expr(expr.object)
            if t in (BOOL, LONG, STRING, SET):
                self._error(f"cannot read attribute {expr.attribute!r} of {t.name}", expr)
            return ANY
        if isinstance(expr, HasAttribute):
            t = self._check_expr(expr.object)
            if t in (BOOL, LONG, STRING, SET):
                self._error(f"`has` expects a record or entity, got {t.name}", expr)
            return BOOL
        if isinstance(expr, InExpression):
            self._need(expr.left, ENTITY, "`in` on the left")
            rt = self._check_expr(expr.right)
            if rt not in (ENTITY, SET, ANY):
                self._error(f"`in` expects an entity or set on the right, got {rt.name}", expr)
            return BOOL
        if isinstance(expr, IsExpression):
            self._need(expr.left, ENTITY, "`is`")
            self.entity_types.add(expr.entity_type)
            if expr.in_expr is not None:
                self._need(expr.in_expr, ENTITY, "`is ... in`")
            return BOOL
        if isinstance(expr, LikeExpression):
            self._need(expr.left, STRING, "`like`")
            return BOOL
        if isinstance(expr, BinaryOp):
            if expr.op in ("&&", "||"):
                self._need(expr.left, BOOL, f"`{expr.op}`")
                self._need(expr.right, BOOL, f"`{expr.op}`")
                return BOOL
            if expr.op in ("==", "!="):
                self._check_expr(expr.left)
                self._check_expr(expr.right)
                return BOOL
            self._need(expr.left, LONG, f"`{expr.op}`")
            self._need(expr.right, LONG, f"`{expr.op}`")
            return BOOL if expr.op in ("<", "<=", ">", ">=") else LONG
        if isinstance(expr, UnaryOp):
            if expr.op == "!":
                self._need(expr.operand, BOOL, "`!`")
                return BOOL
            self._need(expr.operand, LONG, "unary `-`")
            return LONG
        if isinstance(expr, IfThenElse):
            self._need(expr.condition, BOOL, "an `if` condition")
            a, b = self._check_expr(expr.then_expr), self._check_expr(expr.else_expr)
            return a if a == b else ANY
        if isinstance(expr, SetLiteral):
            for e in expr.elements:
                self._check_expr(e)
            return SET
        if isinstance(expr, RecordLiteral):
            for e in expr.fields.values():
                self._check_expr(e)
            return RECORD
        if isinstance(expr, MethodCall):
            self._check_expr(expr.object)
            args = [self._check_expr(a) for a in expr.arguments]
            if expr.method in SET_METHODS:
                self._need(expr.object, SET, f".{expr.method}()")
                if len(args) != SET_METHODS[expr.method]:
                    self._error(f".{expr.method}() takes {SET_METHODS[expr.method]} argument(s), got {len(args)}", expr)
                if expr.method in ("containsAll", "containsAny") and args and not compatible(args[0], SET):
                    self._error(f".{expr.method}() expects a set, got {args[0].name}", expr)
                return BOOL
            return ANY                      # extension-type methods (isIpv4, lessThan, ...): not typed here
        if isinstance(expr, ExtensionCall):
            for a in expr.arguments:
                self._check_expr(a)
            if expr.function not in EXTENSION_FUNCTIONS:
                self._error(f"unknown function {expr.function!r}", expr)
            return EXTENSION
        return ANY
