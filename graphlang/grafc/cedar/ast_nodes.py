"""Cedar AST node definitions (the Cedar policy language, minus templates and schemas)."""

from dataclasses import dataclass, field
from typing import Any, List, Optional
from enum import Enum


class Effect(Enum):
    PERMIT = "permit"
    FORBID = "forbid"


# ============================================================
# Expressions
# ============================================================

@dataclass
class Expr:
    """Base class for all expressions."""
    line: int = field(default=0, kw_only=True)
    column: int = field(default=0, kw_only=True)


@dataclass
class Literal(Expr):
    """Literal value (string, long, bool)."""
    value: Any
    literal_type: str  # "String", "Long", "Bool"


@dataclass
class EntityRef(Expr):
    """Entity reference like User::"alice" or Org::User::"alice"."""
    entity_type: str
    entity_id: str


@dataclass
class Variable(Expr):
    """Scope variable: principal, action, resource, context."""
    name: str


@dataclass
class AttributeAccess(Expr):
    """expr.attr, or expr["attr"] (the same thing in Cedar)."""
    object: Expr
    attribute: str


@dataclass
class HasAttribute(Expr):
    """expr has attr  /  expr has "attr"."""
    object: Expr
    attribute: str


@dataclass
class InExpression(Expr):
    """expr in entity-or-set."""
    left: Expr
    right: Expr


@dataclass
class IsExpression(Expr):
    """expr is Type  /  expr is Type in entity."""
    left: Expr
    entity_type: str
    in_expr: Optional[Expr] = None


@dataclass
class LikeExpression(Expr):
    """expr like "pat*tern". `pattern` is a list of literal strings and None (= the wildcard *)."""
    left: Expr
    pattern: List[Optional[str]]


@dataclass
class BinaryOp(Expr):
    """&&, ||, ==, !=, <, <=, >, >=, +, -, *."""
    op: str
    left: Expr
    right: Expr


@dataclass
class UnaryOp(Expr):
    """Unary operation: `!` or `-`."""
    op: str
    operand: Expr


@dataclass
class IfThenElse(Expr):
    """if cond then expr1 else expr2."""
    condition: Expr
    then_expr: Expr
    else_expr: Expr


@dataclass
class SetLiteral(Expr):
    """[a, b, c]."""
    elements: List[Expr]


@dataclass
class RecordLiteral(Expr):
    """{"key": value, ...}."""
    fields: dict  # str -> Expr (insertion order kept)


@dataclass
class MethodCall(Expr):
    """expr.method(args), e.g. set.contains(x)."""
    object: Expr
    method: str
    arguments: List[Expr]


@dataclass
class ExtensionCall(Expr):
    """Extension function call: ip("1.2.3.4"), decimal("1.5")."""
    function: str
    arguments: List[Expr]


# ============================================================
# Policy Structure
# ============================================================

@dataclass
class PrincipalConstraint:
    """principal clause: op is "_" (any), "eq", "in", "is" (type only) or "is_in"."""
    op: str
    entity: Optional[EntityRef] = None
    entity_type: Optional[str] = None


@dataclass
class ActionConstraint:
    """action clause: op is "_", "eq", or "in" (one entity or a list)."""
    op: str
    entities: Optional[List[EntityRef]] = None


@dataclass
class ResourceConstraint:
    """resource clause: same forms as principal."""
    op: str
    entity: Optional[EntityRef] = None
    entity_type: Optional[str] = None


@dataclass
class PolicyScope:
    principal: PrincipalConstraint
    action: ActionConstraint
    resource: ResourceConstraint


@dataclass
class Condition:
    """A when/unless clause."""
    kind: str  # "when" or "unless"
    body: Expr


@dataclass
class Annotation:
    """@name("value") or @name."""
    name: str
    value: Optional[str] = None


@dataclass
class Policy:
    effect: Effect
    annotations: List[Annotation] = field(default_factory=list)
    scope: Optional[PolicyScope] = None
    conditions: List[Condition] = field(default_factory=list)
    line: int = 0
    column: int = 0
    policy_id: str = ""      # "policy0", "policy1", ... in file order, as the Cedar engine names them


@dataclass
class PolicySet:
    """A set of Cedar policies (a complete .cedar file)."""
    policies: List[Policy] = field(default_factory=list)
