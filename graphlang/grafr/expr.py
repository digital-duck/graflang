"""A small, safe expression evaluator for EVALUATE / ASSERT / LOOP conditions.

Never calls `eval`/`exec`: the expression is parsed to a Python AST, checked against a whitelist, and
interpreted by `_eval` below. What it accepts:

* variables written `@name`  (`@in_analysis`, `@cycle`); a bare name is an error
* literals: numbers, 'strings', TRUE / FALSE / NULL (any case)
* `AND`, `OR`, `NOT` (any case; `and`/`or`/`not` also work), comparisons (== != < <= > >= in, not in),
  arithmetic (+ - * / // %), parentheses, list/tuple literals
* calls to a fixed set of functions: contains, startswith, endswith, len, lower, upper, strip, abs,
  min, max, int, float, str, bool, is_empty, json_get

Everything else is rejected: attribute access, subscripts, lambdas, comprehensions, imports, `**`,
keyword arguments, calls to anything not listed. Expressions are limited in length and size, and
string/list repetition is capped, so an expression cannot exhaust memory or time.
"""
from __future__ import annotations

import ast
import io
import json
import re
import tokenize
from typing import Any, Callable, Dict

MAX_LEN = 2000
MAX_NODES = 300
MAX_REPEAT = 10_000
VAR_PREFIX = "_v_"
WORDS = {"AND": "and", "OR": "or", "NOT": "not", "IN": "in", "TRUE": "True", "FALSE": "False", "NULL": "None"}


class ExpressionError(ValueError):
    """The expression is not allowed, or cannot be evaluated with the given variables."""


def _contains(a: Any, b: Any) -> bool:
    if a is None:
        return False
    if isinstance(a, (list, tuple, set, dict)):
        return b in a
    return str(b) in str(a)


def _json_get(value: Any, key: Any, default: Any = "") -> Any:
    """Read a field out of JSON: `value` is a dict or JSON text (a code fence around it is ignored); `key` is a field
    name, or a dotted path (`result.violated.0`: names for objects, numbers for lists). Returns the field with its JSON
    type (so a `true` stays a boolean a condition can test), or `default` when the text is not JSON or the path is absent.
    Unlike SPL's `json_get`, which always returns text."""
    if isinstance(value, str):
        text = value.strip()
        fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        try:
            value = json.loads(fenced.group(1).strip() if fenced else text)
        except ValueError:
            return default
    for part in str(key).split("."):
        if isinstance(value, dict) and part in value:
            value = value[part]
        elif isinstance(value, list) and part.isdigit() and int(part) < len(value):
            value = value[int(part)]
        else:
            return default
    return value


FUNCS: Dict[str, Callable[..., Any]] = {
    "json_get": _json_get,
    "contains": _contains,
    "startswith": lambda a, b: str(a).startswith(str(b)),
    "endswith": lambda a, b: str(a).endswith(str(b)),
    "len": len,
    "lower": lambda a: str(a).lower(),
    "upper": lambda a: str(a).upper(),
    "strip": lambda a: str(a).strip(),
    "abs": abs, "min": min, "max": max,
    "int": int, "float": float, "str": str, "bool": bool,
    "is_empty": lambda a: a is None or (hasattr(a, "__len__") and len(a) == 0),
}

_ALLOWED = (ast.Expression, ast.BoolOp, ast.And, ast.Or, ast.UnaryOp, ast.Not, ast.USub, ast.UAdd,
            ast.BinOp, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod,
            ast.Compare, ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn,
            ast.Constant, ast.Name, ast.Load, ast.Call, ast.List, ast.Tuple)
_BINOPS = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b, ast.Mult: lambda a, b: a * b,
           ast.Div: lambda a, b: a / b, ast.FloorDiv: lambda a, b: a // b, ast.Mod: lambda a, b: a % b}
_CMPS = {ast.Eq: lambda a, b: a == b, ast.NotEq: lambda a, b: a != b, ast.Lt: lambda a, b: a < b,
         ast.LtE: lambda a, b: a <= b, ast.Gt: lambda a, b: a > b, ast.GtE: lambda a, b: a >= b,
         ast.In: lambda a, b: a in b, ast.NotIn: lambda a, b: a not in b}


def _translate(expr: str) -> str:
    """`@x` -> `_v_x`, and the word operators/constants to Python's. Strings are left alone (the tokenizer
    keeps them as single tokens)."""
    out, toks = [], list(tokenize.generate_tokens(io.StringIO(expr).readline))
    i = 0
    while i < len(toks):
        t = toks[i]
        if t.type == tokenize.OP and t.string == "@" and i + 1 < len(toks) and toks[i + 1].type == tokenize.NAME:
            out.append((tokenize.NAME, VAR_PREFIX + toks[i + 1].string))
            i += 2
            continue
        if t.type == tokenize.NAME and t.string.upper() in WORDS:
            out.append((tokenize.NAME, WORDS[t.string.upper()]))
        elif t.type not in (tokenize.NEWLINE, tokenize.NL, tokenize.ENDMARKER, tokenize.COMMENT):
            out.append((t.type, t.string))
        i += 1
    return tokenize.untokenize(out)


def parse(expr: str) -> ast.Expression:
    """Parse and validate. Raises ExpressionError if anything is not whitelisted."""
    if not isinstance(expr, str) or not expr.strip():
        raise ExpressionError("empty expression")
    if len(expr) > MAX_LEN:
        raise ExpressionError(f"expression longer than {MAX_LEN} characters")
    try:
        tree = ast.parse(_translate(expr.strip()).strip(), mode="eval")
    except (SyntaxError, tokenize.TokenError, IndentationError) as e:
        raise ExpressionError(f"cannot parse {expr!r}: {e}") from None
    nodes = list(ast.walk(tree))
    if len(nodes) > MAX_NODES:
        raise ExpressionError(f"expression too large ({len(nodes)} nodes, limit {MAX_NODES})")
    for n in nodes:
        if not isinstance(n, _ALLOWED):
            raise ExpressionError(f"{type(n).__name__} is not allowed in {expr!r}")
        if isinstance(n, ast.Constant) and not isinstance(n.value, (str, int, float, bool, type(None))):
            raise ExpressionError(f"literal {n.value!r} is not allowed")
        if isinstance(n, ast.Call):
            if not isinstance(n.func, ast.Name) or n.func.id not in FUNCS:
                raise ExpressionError(f"only these functions may be called: {sorted(FUNCS)}")
            if n.keywords or any(isinstance(a, ast.Starred) for a in n.args):
                raise ExpressionError("keyword and star arguments are not allowed")
        if isinstance(n, ast.Name) and not n.id.startswith(VAR_PREFIX) \
                and not any(isinstance(p, ast.Call) and p.func is n for p in nodes):
            raise ExpressionError(f"bare name {n.id!r}: write variables as @{n.id}")
    return tree


def variables(expr: str) -> set:
    """Names of the @variables an expression uses."""
    return {n.id[len(VAR_PREFIX):] for n in ast.walk(parse(expr)) if isinstance(n, ast.Name) and n.id.startswith(VAR_PREFIX)}


def _eval(node: ast.AST, scope: Dict[str, Any]) -> Any:
    if isinstance(node, ast.Expression):
        return _eval(node.body, scope)
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        name = node.id[len(VAR_PREFIX):]
        if name not in scope:
            raise ExpressionError(f"unknown variable @{name}; available: {sorted(scope)}")
        return scope[name]
    if isinstance(node, (ast.List, ast.Tuple)):
        items = [_eval(e, scope) for e in node.elts]
        return items if isinstance(node, ast.List) else tuple(items)
    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            result: Any = True
            for v in node.values:
                result = _eval(v, scope)
                if not result:
                    return result
            return result
        result = False
        for v in node.values:
            result = _eval(v, scope)
            if result:
                return result
        return result
    if isinstance(node, ast.UnaryOp):
        v = _eval(node.operand, scope)
        return (not v) if isinstance(node.op, ast.Not) else (-v if isinstance(node.op, ast.USub) else +v)
    if isinstance(node, ast.BinOp):
        a, b = _eval(node.left, scope), _eval(node.right, scope)
        if isinstance(node.op, ast.Mult):
            for seq, n in ((a, b), (b, a)):
                if isinstance(seq, (str, list, tuple)) and isinstance(n, int) and len(seq) * max(n, 0) > MAX_REPEAT:
                    raise ExpressionError("repetition too large")
        return _BINOPS[type(node.op)](a, b)
    if isinstance(node, ast.Compare):
        left = _eval(node.left, scope)
        for op, comp in zip(node.ops, node.comparators):
            right = _eval(comp, scope)
            if not _CMPS[type(op)](left, right):
                return False
            left = right
        return True
    if isinstance(node, ast.Call):
        return FUNCS[node.func.id](*[_eval(a, scope) for a in node.args])
    raise ExpressionError(f"cannot evaluate {type(node).__name__}")        # unreachable after parse()


def evaluate(expr: str, scope: Dict[str, Any] | None = None) -> Any:
    """Evaluate `expr` against `scope` (variable name without '@' -> value)."""
    tree = parse(expr)
    try:
        return _eval(tree, scope or {})
    except ExpressionError:
        raise
    except (TypeError, ValueError, ZeroDivisionError, OverflowError, AttributeError) as e:
        raise ExpressionError(f"cannot evaluate {expr!r}: {type(e).__name__}: {e}") from None


def evaluate_condition(expr: str, scope: Dict[str, Any] | None = None) -> bool:
    return bool(evaluate(expr, scope))
