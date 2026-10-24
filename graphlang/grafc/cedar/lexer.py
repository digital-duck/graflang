"""Cedar lexer - tokenizes Cedar source code."""

from typing import List
from .tokens import Token, TokenType, KEYWORDS
from .errors import CedarLexError

MAX_LONG = 2**63 - 1          # Cedar's Long is a signed 64-bit integer; `-9223372036854775808` is written -(9223372036854775808)

SIMPLE_ESCAPES = {'n': '\n', 't': '\t', 'r': '\r', '\\': '\\', '0': '\0', "'": "'", '"': '"'}

OPERATORS = {
    '==': TokenType.EQ, '!=': TokenType.NEQ, '<=': TokenType.LTE, '>=': TokenType.GTE,
    '&&': TokenType.AND, '||': TokenType.OR, '::': TokenType.DOUBLE_COLON,
    '<': TokenType.LT, '>': TokenType.GT, '!': TokenType.NOT, '+': TokenType.PLUS, '-': TokenType.MINUS,
    '*': TokenType.STAR, '.': TokenType.DOT, '(': TokenType.LPAREN, ')': TokenType.RPAREN,
    '{': TokenType.LBRACE, '}': TokenType.RBRACE, '[': TokenType.LBRACKET, ']': TokenType.RBRACKET,
    ',': TokenType.COMMA, ';': TokenType.SEMICOLON, ':': TokenType.COLON, '@': TokenType.AT,
}


class CedarLexer:
    """Tokenizes Cedar source code into a stream of tokens."""

    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.column = 1
        self.tokens: List[Token] = []

    def tokenize(self) -> List[Token]:
        while True:
            self._skip_whitespace_and_comments()
            if self.pos >= len(self.source):
                break
            line, col, ch = self.line, self.column, self.source[self.pos]
            if ch == '"':
                self._read_string(line, col)
            elif ch.isdigit():
                self._read_number(line, col)
            elif ch.isalpha() or ch == '_':
                self._read_identifier(line, col)
            else:
                self._read_operator(line, col)
        self.tokens.append(Token(TokenType.EOF, None, self.line, self.column))
        return self.tokens

    # ---- scanning helpers ---------------------------------------------------------------------
    def _skip_whitespace_and_comments(self):
        while self.pos < len(self.source):
            ch = self.source[self.pos]
            if ch in ' \t\r':
                self._advance()
            elif ch == '\n':
                self._advance()
                self.line += 1
                self.column = 1
            elif ch == '/' and self._peek(1) == '/':
                while self.pos < len(self.source) and self.source[self.pos] != '\n':
                    self._advance()
            else:
                break

    def _advance(self) -> str:
        ch = self.source[self.pos]
        self.pos += 1
        self.column += 1
        return ch

    def _peek(self, offset: int = 0) -> str:
        pos = self.pos + offset
        return self.source[pos] if pos < len(self.source) else '\0'

    # ---- tokens -------------------------------------------------------------------------------
    def _read_string(self, line: int, col: int):
        """A string literal. `value` has escapes processed; `raw` keeps them (a `like` pattern needs to tell
        the wildcard `*` from the escaped `\\*`)."""
        self._advance()                       # opening quote
        value, raw = [], []
        while self.pos < len(self.source):
            ch = self.source[self.pos]
            if ch == '"':
                self._advance()
                self.tokens.append(Token(TokenType.STRING, ''.join(value), line, col, raw=''.join(raw)))
                return
            if ch == '\n':
                raise CedarLexError("Unterminated string literal", line, col)
            if ch != '\\':
                value.append(self._advance())
                raw.append(value[-1])
                continue
            self._advance()                   # backslash
            if self.pos >= len(self.source):
                break
            esc = self._advance()
            raw.append('\\' + esc)
            if esc in SIMPLE_ESCAPES:
                value.append(SIMPLE_ESCAPES[esc])
            elif esc == '*':
                value.append('*')             # only meaningful in a pattern
            elif esc == 'u' and self._peek() == '{':
                self._advance()
                digits = []
                while self.pos < len(self.source) and self._peek() != '}':
                    digits.append(self._advance())
                if self._peek() != '}' or not (1 <= len(digits) <= 6):
                    raise CedarLexError("Malformed \\u{...} escape", line, col)
                self._advance()
                raw[-1] = '\\u{' + ''.join(digits) + '}'
                try:
                    value.append(chr(int(''.join(digits), 16)))
                except (ValueError, OverflowError):
                    raise CedarLexError("Invalid unicode escape", line, col) from None
            else:
                raise CedarLexError(f"Invalid escape \\{esc}", line, col)
        raise CedarLexError("Unterminated string literal", line, col)

    def _read_number(self, line: int, col: int):
        """An integer literal. Cedar has no bare decimal literals (`decimal("1.5")` is a function call), and the
        magnitude may be one past MAX_LONG so that -9223372036854775808 can be written; the parser checks."""
        digits = []
        while self.pos < len(self.source) and self.source[self.pos].isdigit():
            digits.append(self._advance())
        self.tokens.append(Token(TokenType.LONG, int(''.join(digits)), line, col))

    def _read_identifier(self, line: int, col: int):
        """[_a-zA-Z][_a-zA-Z0-9]* (no hyphens: `a-1` is a subtraction)."""
        chars = []
        while self.pos < len(self.source) and (self.source[self.pos].isalnum() or self.source[self.pos] == '_'):
            chars.append(self._advance())
        text = ''.join(chars)
        self.tokens.append(Token(KEYWORDS.get(text, TokenType.IDENTIFIER), text, line, col))

    def _read_operator(self, line: int, col: int):
        two = self.source[self.pos:self.pos + 2]
        if len(two) == 2 and two in OPERATORS:
            self._advance()
            self._advance()
            self.tokens.append(Token(OPERATORS[two], two, line, col))
            return
        ch = self._advance()
        if ch in OPERATORS:
            self.tokens.append(Token(OPERATORS[ch], ch, line, col))
            return
        raise CedarLexError(f"Unexpected character: {ch!r}", line, col)
