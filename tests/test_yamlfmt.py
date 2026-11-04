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
