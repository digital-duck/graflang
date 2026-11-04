"""Readable YAML for graph files: a text with quotes in it is written as a `|` block, not as a quoted string with doubled quotes.

    condition: '@in_mode == ''solver'''          becomes          condition: |-
                                                                    @in_mode == 'solver'

`readable(text)` rewrites a YAML text (comments and layout stay; a value only changes its style, never its content, and the result is
checked against the original). `dump_readable(doc)` dumps plain data the same way. A block scalar cannot sit inside `[...]` or `{...}`,
and a key cannot be one, so those are left as they are.
"""
from __future__ import annotations

import io
from typing import Any

import yaml
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.scalarstring import LiteralScalarString

_INDICATORS = "@`!&*%|>{}[]#?,"


def _hard(s: str) -> bool:
    """A string a person would find hard to read once it is quoted: it holds a quote or a line break, or starts with an indicator."""
    return bool(s) and ("'" in s or '"' in s or "\n" in s or s[0] in _INDICATORS) and s == s.strip() and "\t" not in s and "\r" not in s \
        and all(ch.isprintable() or ch == "\n" for ch in s)


def _walk(node: Any, flow: bool) -> Any:
    if isinstance(node, CommentedMap):
        here = flow or node.fa.flow_style() is True
        for k in list(node.keys()):
            node[k] = _walk(node[k], here)
        return node
    if isinstance(node, CommentedSeq):
        here = flow or node.fa.flow_style() is True
        for i, v in enumerate(node):
            node[i] = _walk(v, here)
        return node
    if isinstance(node, str) and not flow and not isinstance(node, LiteralScalarString) and _hard(node):
        return LiteralScalarString(node)
    return node


def readable(text: str) -> str:
    """`text` with hard-to-read strings as `|` blocks; the text itself when it does not parse or nothing would change."""
    y = YAML()
    y.preserve_quotes = True
    y.width = 4096
    try:
        doc = y.load(text)
        if not isinstance(doc, (CommentedMap, CommentedSeq)):
            return text
        y.indent(mapping=2, sequence=_seq_indent(text) + 2, offset=_seq_indent(text))
        out = io.StringIO()
        y.dump(_walk(doc, False), out)
    except Exception:                                              # noqa: BLE001 - any YAML trouble: leave the text alone
        return text
    new = out.getvalue()
    safe = YAML(typ="safe")
    try:
        same = safe.load(new) == safe.load(text)
    except Exception:                                              # noqa: BLE001
        same = False
    return new if same else text


def _seq_indent(text: str) -> int:
    lines = text.splitlines()
    for i, line in enumerate(lines[:-1]):
        if line.rstrip().endswith(":") and lines[i + 1].lstrip().startswith("- "):
            return len(lines[i + 1]) - len(lines[i + 1].lstrip()) - (len(line) - len(line.lstrip()))
    return 2


class _Dumper(yaml.SafeDumper):
    def choose_scalar_style(self):
        style = super().choose_scalar_style()
        ev = self.event
        if style in ("'", '"') and not self.simple_key_context and getattr(self, "analysis", None) is not None and self.analysis.allow_block \
                and _hard(ev.value):
            return "|"
        return style


def dump_readable(doc: Any) -> str:
    return yaml.dump(doc, Dumper=_Dumper, sort_keys=False, default_flow_style=False, allow_unicode=True, width=4096)
