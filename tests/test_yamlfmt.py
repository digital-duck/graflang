"""Readable YAML (quotes in a `|` block) and the picture page's script (a syntax error there blanks the canvas)."""
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from graphlang.yamlfmt import dump_readable, readable

TEXT = """nodes:
- id: gate
  config:
    condition: '@in_mode == ''solver'''
    plain: just words
    expression: json_get(@in_result, 'program')
    list: ['a b', "it's"]
"""


def test_a_quoted_condition_becomes_a_block_and_means_the_same():
    out = readable(TEXT)
    assert "condition: |-\n      @in_mode == 'solver'" in out
    assert "plain: just words" in out and "['a b', \"it's\"]" in out            # a flow list keeps its quotes
    assert YAML(typ="safe").load(out) == YAML(typ="safe").load(TEXT)


def test_text_that_is_not_yaml_is_returned_untouched():
    assert readable("a: [unclosed") == "a: [unclosed"


def test_dump_readable():
    out = dump_readable({"c": "@in_mode == 'solver'", "d": "plain", "e": "two\nlines"})
    assert "c: |-\n  @in_mode == 'solver'" in out and "d: plain" in out and "e: |-\n  two\n  lines" in out


def test_long_form_conversion_writes_readable_conditions(tmp_path):
    from graphlang import workspace as ws
    f = tmp_path / "x.graph.yaml"
    f.write_text("version: 1.0-graph\nworkflow: {name: x, inputs: [{name: m, type: TEXT}], outputs: [{name: o, type: TEXT}]}\n"
                 "steps:\n  - g: {evaluate: \"@in_m == 'a'\", in: {m: $in.m}}\n  - o: {output: g}\n")
    ws.long_form_in_place(f)
    assert "condition: |-\n      @in_m == 'a'" in f.read_text()


@pytest.mark.skipif(shutil.which("node") is None, reason="node is needed to check the page's script")
def test_the_picture_pages_script_has_no_syntax_error(tmp_path):
    """A stray newline in a JS string (a Python escape mistake) once blanked the canvas; check the script as a browser would parse it."""
    from zinet.vis.cytoscape import CYTOSCAPE_PAGE
    start = CYTOSCAPE_PAGE.index("<script>\nconst data")
    body = CYTOSCAPE_PAGE[start + 8:CYTOSCAPE_PAGE.index("</script>", start)].replace("__DATA__", "[]").replace("__OPTS__", "{}")
    js = tmp_path / "page.js"
    js.write_text("(function(){" + body + "})")
    res = subprocess.run(["node", "--check", str(js)], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr


def test_a_long_quoted_string_with_escapes_is_never_folded_inside_an_escape():
    """A code string over 4096 characters used to be folded by the emitter at a width of 4096, and a fold inside `\\n` read back as `\\ n`."""
    from graphlang.yamlfmt import dump_readable
    import yaml
    code = "x = f'a\\n\\n{b}\\n\\n── c ──'\n" * 400
    doc = {"steps": [{"s": {"node": "SOLVE", "code": code.replace("\n", "\\n") + "\\n\\n── end"}}]}
    assert yaml.safe_load(dump_readable(doc)) == doc
    doc = {"nodes": [{"id": "a", "config": {"code": "return f'{x}\\n\\n── Business Explanation ──' + '\\n'" * 300}}]}
    assert yaml.safe_load(dump_readable(doc)) == doc


def test_graf_compact_writes_the_code_of_every_tool_back_exactly(tmp_path):
    """The code of a SOLVE node holds `\\n` inside an f-string. `graf compact` wrote long quoted strings folded at the emitter's default width,
    and a fold could land inside the escape: `\\n` read back as `\\ n`, so the compact file ran differently from the long form (found porting
    cookbook_solvers/pandera_schema: the report lost its blank line)."""
    from pathlib import Path
    from click.testing import CliRunner
    from ruamel.yaml import YAML
    from graphlang.grafr.cli import cmd_compact
    src = Path(__file__).resolve().parents[1] / "cookbook_solvers" / "pandera_schema" / "pandera_schema.graph.yaml"
    out = tmp_path / "c.graph.yaml"
    r = CliRunner().invoke(cmd_compact, [str(src), "-o", str(out)])
    assert r.exit_code == 0, r.output
    before = {n["config"]["tool"]: n["config"]["code"] for n in YAML(typ="safe").load(src.read_text())["nodes"] if n["type"] == "SOLVE"}
    after = {v["tool"]: v["code"] for s in YAML(typ="safe").load(out.read_text())["steps"] for v in s.values() if isinstance(v, dict) and "code" in v}
    assert after == before
