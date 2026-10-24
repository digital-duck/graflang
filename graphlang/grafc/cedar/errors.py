"""Cedar error types with source locations."""


class CedarError(Exception):
    """Base class for Cedar errors."""
    def __init__(self, message: str, line: int = 0, column: int = 0):
        self.message = message
        self.line = line
        self.column = column
        super().__init__(self._format())
    
    def _format(self) -> str:
        if self.line > 0:
            return f"[L{self.line}:C{self.column}] {self.message}"
        return self.message


class CedarLexError(CedarError):
    """Lexer error."""
    pass


class CedarParseError(CedarError):
    """Parser error."""
    pass


class CedarTypeError(CedarError):
    """Type checking error."""
    pass


class CedarCompileError(CedarError):
    """Code generation error."""
    pass
