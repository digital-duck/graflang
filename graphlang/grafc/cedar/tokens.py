"""Cedar token definitions."""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any


class TokenType(Enum):
    # Literals
    STRING = auto()
    LONG = auto()
    BOOL_TRUE = auto()
    BOOL_FALSE = auto()
    IDENTIFIER = auto()

    # Keywords
    PERMIT = auto()
    FORBID = auto()
    WHEN = auto()
    UNLESS = auto()
    IN = auto()
    HAS = auto()
    LIKE = auto()
    IS = auto()
    IF = auto()
    THEN = auto()
    ELSE = auto()
    PRINCIPAL = auto()
    ACTION = auto()
    RESOURCE = auto()
    CONTEXT = auto()

    # Operators
    EQ = auto()          # ==
    NEQ = auto()         # !=
    LT = auto()          # <
    LTE = auto()         # <=
    GT = auto()          # >
    GTE = auto()         # >=
    AND = auto()         # &&
    OR = auto()          # ||
    NOT = auto()         # !
    PLUS = auto()        # +
    MINUS = auto()       # -
    STAR = auto()        # *
    DOT = auto()         # .
    DOUBLE_COLON = auto()  # ::

    # Delimiters
    LPAREN = auto()
    RPAREN = auto()
    LBRACE = auto()
    RBRACE = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    COMMA = auto()
    SEMICOLON = auto()
    COLON = auto()

    AT = auto()          # @ (annotations)
    EOF = auto()


@dataclass
class Token:
    type: TokenType
    value: Any
    line: int
    column: int
    raw: str = ""        # STRING tokens: the text between the quotes, escapes unprocessed (for `like` patterns)

    def __repr__(self):
        return f"Token({self.type.name}, {self.value!r}, L{self.line}:C{self.column})"


# Words that are reserved in some position. `principal action resource context` are only special as scope
# variables; Cedar still allows them as attribute names (`context.action`), so the parser accepts any word
# token after a `.` or `has` (see WORD_TOKENS).
KEYWORDS = {
    "permit": TokenType.PERMIT,
    "forbid": TokenType.FORBID,
    "when": TokenType.WHEN,
    "unless": TokenType.UNLESS,
    "in": TokenType.IN,
    "has": TokenType.HAS,
    "like": TokenType.LIKE,
    "is": TokenType.IS,
    "if": TokenType.IF,
    "then": TokenType.THEN,
    "else": TokenType.ELSE,
    "principal": TokenType.PRINCIPAL,
    "action": TokenType.ACTION,
    "resource": TokenType.RESOURCE,
    "context": TokenType.CONTEXT,
    "true": TokenType.BOOL_TRUE,
    "false": TokenType.BOOL_FALSE,
}

# Every token type that is a word (identifier or keyword): usable as an attribute name.
WORD_TOKENS = frozenset({TokenType.IDENTIFIER, *KEYWORDS.values()})
