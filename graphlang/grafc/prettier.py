"""`graf prettier`: write a graph file with its code, prompts and expressions as YAML block scalars.

An expression in quotes needs every `'` doubled (`'@a + ''## '' + @b + ''\\n'''`), a program in a string needs escapes. As a block
(`|` literal, `>` folded) the text is written as it is. Only the style of those attributes changes, never their value, and every
other byte of the file stays exactly as it was (comments, key order, the way other long lines are wrapped): the attributes are found
by their position in the source and only their text is replaced.

* an attribute that already is a block is left alone, so the command can run again on its own output (same text back);
* a text with line breaks becomes a literal block (`|`, `|-` or `|+`, as its ending needs);
* a one-line text is changed only when YAML would have to quote it (`'@a + ''## '' + @b'`) or it is long. A long one is folded
  (`>-`) at spaces, which reads back as the same one-line text; a quoted one of some length becomes a literal block; a short quoted one
  becomes a double-quoted string (an empty-string literal written as four quote characters becomes `"''"`). A short text that needs
  no quotes stays as it is (`expression: '@in_i + 1'` is fine);
* each rewrite is read back and compared with the original text, and an attribute that would not come back exactly (a control
  character YAML cannot put in a block, a comment after the value, ...) is kept as it was and reported;
* at the end the whole file is read back and compared with the original; if anything differs the command stops and writes nothing.

Text inside a flow-style `{...}` or `[...]` (the compact `steps:` form is often written that way) cannot be a block and is left as it is.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from typing import Any, Iterator, List, Tuple

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError
from ruamel.yaml.nodes import MappingNode, ScalarNode, SequenceNode
from ruamel.yaml.scalarstring import DoubleQuotedScalarString, FoldedScalarString, LiteralScalarString

# Attributes that hold program, prompt or expression text. The long form (`nodes:`) uses the first five; the compact `steps:` form the rest.
TEXT_KEYS = ("code", "prompt_inline", "expression", "condition", "result", "generate", "solve", "assert", "evaluate", "while")
MIN_BLOCK = 30                    # a one-line text that needs quotes becomes a block from this length on (a double-quoted string below)
FOLD_LONGER = 80                  # a one-line text longer than this is folded
FOLD_AT = 72                      # characters of text on a folded line (the indentation comes on top)
STR_TAG = "tag:yaml.org,2002:str"


class PrettierError(ValueError):
    """The file cannot be reformatted (not YAML, not a mapping, or the result would not read back the same)."""


@dataclass
class Report:
    rewritten: List[str] = field(default_factory=list)       # "tool_1.code (literal)"
    kept: List[str] = field(default_factory=list)            # "set_4.expression: has a comment next to it"

    def summary(self) -> str:
        by_key: dict = {}
        for item in self.rewritten:
            key = item.split(" ")[0].rpartition(".")[2]
            by_key[key] = by_key.get(key, 0) + 1
        done = ", ".join(f"{key} x{n}" for key, n in sorted(by_key.items())) or "nothing to rewrite"
        return f"{len(self.rewritten)} attribute(s) rewritten ({done}); {len(self.kept)} kept as they were"


def _fold_positions(text: str) -> List[int]:
    """Where to break a long one-line text: at single spaces, about FOLD_AT characters apart. [] when there is nowhere to break."""
    cuts: List[int] = []
    start, last = 0, None
    for i, ch in enumerate(text):
        if ch == " " and 0 < i < len(text) - 1 and text[i - 1] != " " and text[i + 1] != " ":
            last = i
        if i - start >= FOLD_AT and last is not None and last > start:
            cuts.append(last)
            start, last = last + 1, None
    return cuts


def _candidates(text: str, quoted: bool) -> Iterator[tuple]:
    """(form, style) pairs to try for `text`, best first, style being "block" or "double"; nothing when it should stay as it is.
    `quoted`: the YAML emitter would have to quote `text` if it were left a plain string."""
    one_line = text.strip("\n")
    if "\n" in one_line:
        yield LiteralScalarString(text), "block"
        return
    if len(one_line) > FOLD_LONGER:
        cuts = _fold_positions(one_line)
        if cuts and one_line == text:
            folded = FoldedScalarString(text)
            folded.fold_pos = cuts
            yield folded, "block"
        yield LiteralScalarString(text), "block"
    elif quoted and len(one_line) >= MIN_BLOCK:
        yield LiteralScalarString(text), "block"
    elif quoted and "'" in text and not any(c in text for c in '"\\\n'):
        yield DoubleQuotedScalarString(text), "double"           # a double-quoted string instead of a single-quoted one with doubled quotes


def prettify(text: str) -> Tuple[str, Report]:
    """(new text, Report) for the graph file `text`. Raises PrettierError when the file cannot be read or would not read back the same."""
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096                                       # only the blocks folded on purpose break lines
    yaml.indent(mapping=2)
    try:
        root = yaml.compose(text)
    except YAMLError as e:
        raise PrettierError(f"not valid YAML: {e}") from None
    if not isinstance(root, MappingNode):
        raise PrettierError("not a GraphLang file: the top level is not a mapping")
    newline = "\r\n" if "\r\n" in text else "\n"
    report = Report()
    edits: List[Tuple[int, int, str]] = []                  # (start, end, replacement) in the source text
    visited: set = set()

    def dumped(key: str, form: Any) -> str:
        buf = io.StringIO()
        yaml.dump({key: form}, buf)
        return buf.getvalue()

    def reads_back(key: str, form: Any, style: str, original: str) -> bool:
        snippet = dumped(key, form)
        if not re.match(rf"{re.escape(key)}: " + (r"[|>]" if style == "block" else '"'), snippet):    # else the emitter wrote it another way
            return False
        try:
            return YAML(typ="safe").load(snippet)[key] == original
        except YAMLError:                                                     # e.g. a control character the emitter wrote raw
            return False

    def render(key: str, form: Any, style: str, key_column: int) -> str:
        """The text that replaces the value: `form` as the emitter writes it, its lines moved to sit under a key at `key_column`."""
        body = dumped(key, form)[len(key) + 2:]
        if style == "double":
            return body.rstrip("\n")
        header, _, rest = body.partition("\n")
        lines = rest.split("\n")
        if lines and lines[-1] == "":
            lines.pop()                                                       # the newline that ends the dump: the file's own follows
        pad = " " * key_column
        return newline.join([header] + [pad + line if line else "" for line in lines])

    def visit(key_node: ScalarNode, value_node: ScalarNode, label: str) -> None:
        key, original = key_node.value, value_node.value
        if id(value_node) in visited or value_node.tag != STR_TAG or value_node.style in ("|", ">") or getattr(value_node, "anchor", None):
            return
        visited.add(id(value_node))
        natural = dumped(key, original)[len(key) + 2:]
        candidates = list(_candidates(original, quoted=natural[:1] in ("'", '"')))
        if not candidates:
            return
        start, end = value_node.start_mark.index, value_node.end_mark.index
        if not re.fullmatch(r":[ \t]+", text[key_node.end_mark.index:start]) or text[start] in "&!*":
            report.kept.append(f"{label}.{key}: the value does not start on the key's line")
            return
        line_end = text.find("\n", end)
        if text[end:line_end if line_end >= 0 else len(text)].strip(" \t\r"):
            report.kept.append(f"{label}.{key}: has a comment next to it")      # it would end up inside the block
            return
        for form, style in candidates:
            if reads_back(key, form, style, original):
                new = render(key, form, style, key_node.start_mark.column)
                if new != text[start:end]:
                    edits.append((start, end, new))
                    how = "folded" if isinstance(form, FoldedScalarString) else "literal" if style == "block" else "double-quoted"
                    report.rewritten.append(f"{label}.{key} ({how})")
                return
        report.kept.append(f"{label}.{key}: cannot be written as a block (control characters?)")

    def walk(node: Any, label: str) -> None:
        """Anything written in flow style (`{a: b}`, `[a, b]`) is left alone: a block scalar cannot be written inside it."""
        if id(node) in visited or not isinstance(node, (MappingNode, SequenceNode)) or node.flow_style:
            return
        visited.add(id(node))
        if isinstance(node, SequenceNode):
            for item in node.value:
                walk(item, label)
            return
        here = next((v.value for k, v in node.value if isinstance(k, ScalarNode) and k.value == "id" and isinstance(v, ScalarNode)), label)
        for key_node, value_node in node.value:
            if isinstance(key_node, ScalarNode) and key_node.value in TEXT_KEYS and isinstance(value_node, ScalarNode):
                visit(key_node, value_node, here)
            else:
                walk(value_node, here)

    walk(root, "")
    result = text
    for start, end, new in sorted(edits, reverse=True):                       # from the end, so the positions before stay right
        result = result[:start] + new + result[end:]
    try:
        same = YAML(typ="safe").load(result) == YAML(typ="safe").load(text)
    except YAMLError:
        same = False
    if not same:
        raise PrettierError("the reformatted file does not read back the same as the original; nothing was written (please report this file)")
    return result, report
