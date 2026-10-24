"""Facade for the enhanced Cedar compiler."""

from .cedar.compiler import CedarCompiler as _CedarCompiler
from .cedar.errors import CedarError


class CedarCompiler:
    """Enhanced Cedar compiler facade."""
    
    def compile(self, cedar_source: str) -> str:
        """Compile Cedar policy source to Rust code."""
        compiler = _CedarCompiler()
        return compiler.compile(cedar_source)
    
    def compile_file(self, path: str) -> str:
        """Compile a .cedar file to Rust code."""
        from pathlib import Path
        source = Path(path).read_text(encoding="utf-8")
        return self.compile(source)
