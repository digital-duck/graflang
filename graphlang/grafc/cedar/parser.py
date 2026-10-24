"""Cedar parser: recursive descent over the Cedar grammar.

    Policy    := {Annotation} Effect '(' Scope ')' {Condition} ';'
    Condition := ('when' | 'unless') '{' Expr '}'
    Expr      := Or | 'if' Expr 'then' Expr 'else' Expr
    Or        := And {'||' And}              And := Relation {'&&' Relation}
    Relation  := Add [ RelOp Add | 'has' (IDENT|STR) | 'like' STR | 'is' Name ['in' Add] ]   (not chainable)
    Add       := Mult {('+'|'-') Mult}       Mult := Unary {'*' Unary}
    Unary     := {'!'} Member | {'-'} Member
    Member    := Primary {'.' IDENT ['(' args ')'] | '[' STR ']'}
    Primary   := literal | variable | Name '::' STR | IDENT '(' args ')' | '(' Expr ')' | '[' args ']' | '{' fields '}'
"""

from typing import List, Optional
from .tokens import Token, TokenType, WORD_TOKENS
from .ast_nodes import *
from .errors import CedarParseError

MAX_LONG = 2**63 - 1
MAX_DEPTH = 100                 # Cedar's own parser limits nesting too; this keeps Python's stack safe
REL_OPS = {TokenType.EQ: "==", TokenType.NEQ: "!=", TokenType.LT: "<", TokenType.LTE: "<=",
           TokenType.GT: ">", TokenType.GTE: ">=", TokenType.IN: "in"}


class CedarParser:
    """Recursive descent parser for Cedar policies."""

    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0
        self.depth = 0

    def parse(self) -> PolicySet:
        policies = []
        while not self._at_end():
            policy = self._parse_policy()
            policy.policy_id = f"policy{len(policies)}"
            policies.append(policy)
        return PolicySet(policies=policies)

    # ---- token helpers ------------------------------------------------------------------------
    def _current(self) -> Token:
        return self.tokens[self.pos]

    def _peek(self, offset: int = 1) -> Token:
        pos = self.pos + offset
        return self.tokens[pos] if pos < len(self.tokens) else self.tokens[-1]

    def _advance(self) -> Token:
        token = self.tokens[self.pos]
        if not self._at_end():
            self.pos += 1
        return token

    def _at_end(self) -> bool:
        return self._current().type == TokenType.EOF

    def _check(self, *types: TokenType) -> bool:
        return self._current().type in types

    def _match(self, *types: TokenType) -> Optional[Token]:
        return self._advance() if self._check(*types) else None

    def _error(self, message: str) -> CedarParseError:
        t = self._current()
        return CedarParseError(message, t.line, t.column)

    def _expect(self, token_type: TokenType, message: str = None) -> Token:
        if self._check(token_type):
            return self._advance()
        raise self._error(message or f"Expected {token_type.name}, got {self._current().type.name}")

    def _expect_word(self, what: str = "a name") -> Token:
        """An identifier or a keyword used as a name (Cedar allows `context.action`)."""
        if self._check(*WORD_TOKENS):
            return self._advance()
        raise self._error(f"Expected {what}, got {self._current().type.name}")

    # ---- policies -----------------------------------------------------------------------------
    def _parse_policy(self) -> Policy:
        line, col = self._current().line, self._current().column
        annotations = []
        while self._check(TokenType.AT):
            annotations.append(self._parse_annotation())
        if self._match(TokenType.PERMIT):
            effect = Effect.PERMIT
        elif self._match(TokenType.FORBID):
            effect = Effect.FORBID
        else:
            raise self._error(f"Expected 'permit' or 'forbid', got {self._current().value!r}")
        self._expect(TokenType.LPAREN)
        scope = self._parse_scope()
        self._expect(TokenType.RPAREN)
        conditions = []
        while self._check(TokenType.WHEN, TokenType.UNLESS):
            conditions.append(self._parse_condition())
        self._expect(TokenType.SEMICOLON)
        return Policy(effect=effect, annotations=annotations, scope=scope, conditions=conditions, line=line, column=col)

    def _parse_annotation(self) -> Annotation:
        self._expect(TokenType.AT)
        name = self._expect_word("an annotation name").value
        value = None
        if self._match(TokenType.LPAREN):
            value = self._expect(TokenType.STRING).value
            self._expect(TokenType.RPAREN)
        return Annotation(name=name, value=value)

    def _parse_scope(self) -> PolicyScope:
        principal = self._parse_principal_or_resource(TokenType.PRINCIPAL, PrincipalConstraint)
        self._expect(TokenType.COMMA)
        action = self._parse_action_constraint()
        self._expect(TokenType.COMMA)
        resource = self._parse_principal_or_resource(TokenType.RESOURCE, ResourceConstraint)
        return PolicyScope(principal=principal, action=action, resource=resource)

    def _parse_principal_or_resource(self, keyword: TokenType, cls):
        self._expect(keyword)
        if self._match(TokenType.EQ):
            return cls(op="eq", entity=self._parse_entity_ref())
        if self._match(TokenType.IN):
            return cls(op="in", entity=self._parse_entity_ref())
        if self._match(TokenType.IS):
            entity_type = self._parse_name()
            if self._match(TokenType.IN):
                return cls(op="is_in", entity=self._parse_entity_ref(), entity_type=entity_type)
            return cls(op="is", entity_type=entity_type)
        return cls(op="_")

    def _parse_action_constraint(self) -> ActionConstraint:
        self._expect(TokenType.ACTION)
        if self._match(TokenType.EQ):
            return ActionConstraint(op="eq", entities=[self._parse_entity_ref()])
        if self._match(TokenType.IN):
            if self._match(TokenType.LBRACKET):
                entities = []
                if not self._check(TokenType.RBRACKET):
                    entities.append(self._parse_entity_ref())
                    while self._match(TokenType.COMMA):
                        if self._check(TokenType.RBRACKET):
                            break
                        entities.append(self._parse_entity_ref())
                self._expect(TokenType.RBRACKET)
                return ActionConstraint(op="in", entities=entities)
            return ActionConstraint(op="in", entities=[self._parse_entity_ref()])
        return ActionConstraint(op="_")

    def _parse_name(self) -> str:
        """A (possibly namespaced) type name: A or A::B::C."""
        parts = [self._expect_word("a type name").value]
        while self._check(TokenType.DOUBLE_COLON) and self._peek().type in WORD_TOKENS:
            self._advance()
            parts.append(self._advance().value)
        return "::".join(parts)

    def _parse_entity_ref(self) -> EntityRef:
        line, col = self._current().line, self._current().column
        parts = [self._expect_word("an entity type").value]
        while self._match(TokenType.DOUBLE_COLON):
            if self._check(TokenType.STRING):
                return EntityRef(entity_type="::".join(parts), entity_id=self._advance().value, line=line, column=col)
            parts.append(self._expect_word("an entity type").value)
        raise CedarParseError('Expected an entity like Type::"id"', line, col)

    def _parse_condition(self) -> Condition:
        kind = "when" if self._match(TokenType.WHEN) else "unless"
        if kind == "unless":
            self._expect(TokenType.UNLESS)
        self._expect(TokenType.LBRACE)
        body = self._parse_expression()
        self._expect(TokenType.RBRACE)
        return Condition(kind=kind, body=body)

    # ---- expressions --------------------------------------------------------------------------
    def _nest(self):
        self.depth += 1
        if self.depth > MAX_DEPTH:
            raise self._error("Expression nested too deeply")

    def _parse_expression(self) -> Expr:
        self._nest()
        try:
            if self._check(TokenType.IF):
                t = self._advance()
                cond = self._parse_expression()
                self._expect(TokenType.THEN)
                then_e = self._parse_expression()
                self._expect(TokenType.ELSE)
                else_e = self._parse_expression()
                return IfThenElse(condition=cond, then_expr=then_e, else_expr=else_e, line=t.line, column=t.column)
            return self._parse_or()
        finally:
            self.depth -= 1

    def _binary(self, op: str, left: Expr, right: Expr) -> BinaryOp:
        return BinaryOp(op=op, left=left, right=right, line=left.line, column=left.column)

    def _parse_or(self) -> Expr:
        left = self._parse_and()
        while self._match(TokenType.OR):
            left = self._binary("||", left, self._parse_and())
        return left

    def _parse_and(self) -> Expr:
        left = self._parse_relation()
        while self._match(TokenType.AND):
            left = self._binary("&&", left, self._parse_relation())
        return left

    def _parse_relation(self) -> Expr:
        """At most one relational operator; `a == b == c` is a Cedar syntax error, so it is one here."""
        left = self._parse_add()
        t = self._current()
        if t.type in REL_OPS:
            self._advance()
            right = self._parse_add()
            if t.type == TokenType.IN:
                node: Expr = InExpression(left=left, right=right, line=left.line, column=left.column)
            else:
                node = self._binary(REL_OPS[t.type], left, right)
        elif t.type == TokenType.HAS:
            self._advance()
            if self._check(TokenType.STRING):
                attr = self._advance().value
            else:
                attr = self._expect_word("an attribute name").value
            node = HasAttribute(object=left, attribute=attr, line=left.line, column=left.column)
        elif t.type == TokenType.LIKE:
            self._advance()
            node = LikeExpression(left=left, pattern=self._pattern(self._expect(TokenType.STRING)),
                                  line=left.line, column=left.column)
        elif t.type == TokenType.IS:
            self._advance()
            entity_type = self._parse_name()
            in_expr = self._parse_add() if self._match(TokenType.IN) else None
            node = IsExpression(left=left, entity_type=entity_type, in_expr=in_expr, line=left.line, column=left.column)
        else:
            return left
        if self._check(*REL_OPS, TokenType.HAS, TokenType.LIKE, TokenType.IS):
            raise self._error("Relational operators cannot be chained; use parentheses")
        return node

    @staticmethod
    def _pattern(tok: Token) -> List[Optional[str]]:
        """Split a pattern string into literal runs and wildcards (None). `\\*` is a literal star."""
        parts: List[Optional[str]] = []
        buf: List[str] = []
        raw, i = tok.raw, 0
        while i < len(raw):
            ch = raw[i]
            if ch == '*':
                if buf:
                    parts.append(''.join(buf))
                    buf = []
                if not parts or parts[-1] is not None:        # collapse ** into one wildcard
                    parts.append(None)
                i += 1
            elif ch == '\\' and i + 1 < len(raw):
                nxt = raw[i + 1]
                if nxt == 'u' and raw[i + 2:i + 3] == '{':
                    j = raw.index('}', i)
                    buf.append(chr(int(raw[i + 3:j], 16)))
                    i = j + 1
                else:
                    buf.append({'n': '\n', 't': '\t', 'r': '\r', '0': '\0'}.get(nxt, nxt))
                    i += 2
            else:
                buf.append(ch)
                i += 1
        if buf:
            parts.append(''.join(buf))
        return parts

    def _parse_add(self) -> Expr:
        left = self._parse_mult()
        while self._check(TokenType.PLUS, TokenType.MINUS):
            op = self._advance().value
            left = self._binary(op, left, self._parse_mult())
        return left

    def _parse_mult(self) -> Expr:
        left = self._parse_unary()
        while self._match(TokenType.STAR):
            left = self._binary("*", left, self._parse_unary())
        return left

    def _parse_unary(self) -> Expr:
        t = self._current()
        if t.type == TokenType.NOT:
            self._advance()
            self._nest()
            try:
                return UnaryOp(op="!", operand=self._parse_unary(), line=t.line, column=t.column)
            finally:
                self.depth -= 1
        if t.type == TokenType.MINUS:
            self._advance()
            if self._check(TokenType.LONG):                    # a negative literal, so -9223372036854775808 fits
                value = self._advance().value
                if value > MAX_LONG + 1:
                    raise CedarParseError("Integer literal out of range", t.line, t.column)
                node: Expr = Literal(value=-value, literal_type="Long", line=t.line, column=t.column)
                return self._parse_postfix_ops(node)
            self._nest()
            try:
                return UnaryOp(op="-", operand=self._parse_unary(), line=t.line, column=t.column)
            finally:
                self.depth -= 1
        return self._parse_postfix()

    def _parse_postfix(self) -> Expr:
        return self._parse_postfix_ops(self._parse_primary())

    def _parse_postfix_ops(self, expr: Expr) -> Expr:
        while True:
            if self._match(TokenType.DOT):
                name = self._expect_word("an attribute or method name").value
                if self._match(TokenType.LPAREN):
                    args = self._parse_args(TokenType.RPAREN)
                    expr = MethodCall(object=expr, method=name, arguments=args, line=expr.line, column=expr.column)
                else:
                    expr = AttributeAccess(object=expr, attribute=name, line=expr.line, column=expr.column)
            elif self._check(TokenType.LBRACKET):
                self._advance()
                key = self._expect(TokenType.STRING).value
                self._expect(TokenType.RBRACKET)
                expr = AttributeAccess(object=expr, attribute=key, line=expr.line, column=expr.column)
            else:
                return expr

    def _parse_args(self, closer: TokenType) -> List[Expr]:
        args: List[Expr] = []
        if not self._check(closer):
            args.append(self._parse_expression())
            while self._match(TokenType.COMMA):
                if self._check(closer):
                    break
                args.append(self._parse_expression())
        self._expect(closer)
        return args

    def _parse_primary(self) -> Expr:
        t = self._current()
        line, col = t.line, t.column
        if self._match(TokenType.LPAREN):
            expr = self._parse_expression()
            self._expect(TokenType.RPAREN)
            return expr
        if self._match(TokenType.STRING):
            return Literal(value=t.value, literal_type="String", line=line, column=col)
        if self._match(TokenType.LONG):
            if t.value > MAX_LONG:
                raise CedarParseError("Integer literal out of range", line, col)
            return Literal(value=t.value, literal_type="Long", line=line, column=col)
        if self._match(TokenType.BOOL_TRUE):
            return Literal(value=True, literal_type="Bool", line=line, column=col)
        if self._match(TokenType.BOOL_FALSE):
            return Literal(value=False, literal_type="Bool", line=line, column=col)
        for tt, name in ((TokenType.PRINCIPAL, "principal"), (TokenType.ACTION, "action"),
                         (TokenType.RESOURCE, "resource"), (TokenType.CONTEXT, "context")):
            if self._match(tt):
                return Variable(name=name, line=line, column=col)
        if self._match(TokenType.LBRACKET):
            return SetLiteral(elements=self._parse_args(TokenType.RBRACKET), line=line, column=col)
        if self._match(TokenType.LBRACE):
            return self._parse_record(line, col)
        if self._check(TokenType.IDENTIFIER):
            # Type::"id", A::B::"id", or an extension function call name(args)
            if self._peek().type == TokenType.DOUBLE_COLON:
                return self._parse_entity_ref()
            name = self._advance().value
            if self._match(TokenType.LPAREN):
                return ExtensionCall(function=name, arguments=self._parse_args(TokenType.RPAREN), line=line, column=col)
            raise CedarParseError(f"Unexpected name {name!r}: write principal, action, resource, context, "
                                  f"an entity like Type::\"id\", or a function call", line, col)
        raise self._error(f"Unexpected token: {t.value!r}")

    def _parse_record(self, line: int, col: int) -> Expr:
        fields: dict = {}
        if not self._check(TokenType.RBRACE):
            while True:
                key = self._advance().value if self._check(TokenType.STRING) else self._expect_word("a record key").value
                self._expect(TokenType.COLON)
                fields[key] = self._parse_expression()
                if not self._match(TokenType.COMMA) or self._check(TokenType.RBRACE):
                    break
        self._expect(TokenType.RBRACE)
        return RecordLiteral(fields=fields, line=line, column=col)
