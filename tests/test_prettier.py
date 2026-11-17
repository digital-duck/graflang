"""`graf prettier`: text attributes (code, prompts, expressions) as YAML block scalars, with every value unchanged. No model, no network."""
import re
from pathlib import Path

import pytest
from click.testing import CliRunner
from ruamel.yaml import YAML

from graphlang.cli import main as graf
from graphlang.grafc.prettier import PrettierError, prettify

ROOT = Path(__file__).parent.parent


def load(text):
    return YAML(typ="safe").load(text)


def graph(*nodes_yaml):
    return "# the header comment\nworkflow:\n  name: t\nnodes:\n" + "".join(nodes_yaml) + "edges: []\n"


QUOTED = r"""- id: set_4
  type: CONTEXT
  config:
    action: set
    expression: '@in_all_drafts + ''## '' + @in_section_title + ''\n'' + @in_section_draft
      + ''\n'''
"""


def test_a_quoted_expression_becomes_a_block_and_keeps_its_value():
    text = graph(QUOTED)
    out, report = prettify(text)
    assert load(out) == load(text)
    assert "expression: |-\n" in out and "'## '" in out and "''## ''" not in out           # no doubled quotes left
    assert report.rewritten == ["set_4.expression (literal)"] and not report.kept


def test_a_long_one_line_text_is_folded_at_spaces():
    text = graph(r"""- id: a
  type: CONTEXT
  config:
    action: set
    expression: '@in_context + ''\nSEARCH: '' + @in_search_query + ''\nRESULTS: '' + @in_search_results + ''\n'''
""")
    out, report = prettify(text)
    assert load(out) == load(text) and report.rewritten == ["a.expression (folded)"]
    block = out.split("expression: >-\n")[1].split("edges:")[0].splitlines()
    assert len(block) == 2 and all(len(line) < 80 for line in block)                     # wrapped, and still the one text


def test_short_texts_stay_and_quoted_string_literals_get_double_quotes():
    text = graph("""- id: a
  type: CONTEXT
  config:
    action: set
    expression: '@in_i + 1'
    condition: contains(@in_subject, 'parse_error')
- id: b
  type: CONTEXT
  config:
    action: set
    expression: '''false'''
- id: c
  type: CONTEXT
  config:
    action: set
    expression: ''''''
""")
    out, _ = prettify(text)
    assert load(out) == load(text)
    assert "expression: '@in_i + 1'" in out and "condition: contains(@in_subject, 'parse_error')" in out      # nothing to gain: untouched
    assert """expression: "'false'\"""" in out and """expression: "''\"""" in out


def test_a_text_with_line_breaks_is_a_literal_block_and_a_second_run_changes_nothing():
    text = graph("""- id: tool
  type: SOLVE
  config:
    backend: kernel
    code: "import re\\n\\ndef f(x):\\n    return re.sub('a', 'b', x)\\n_spl_result = f(t)"
    result: _spl_result
    prompt_inline: "Line one\\nLine two: with a colon\\n"
""")
    out, report = prettify(text)
    assert load(out) == load(text)
    assert "code: |-\n" in out and "prompt_inline: |\n" in out                       # |- no final newline, | one
    assert len(report.rewritten) == 2
    again, second = prettify(out)
    assert again == out and not second.rewritten                                       # idempotent


def test_comments_order_and_other_quotes_are_kept():
    text = graph("""- id: a            # the first node
  type: SOLVE
  # why this code
  config:
    description: "stays in double quotes, with 'single' inside"
    code: |
      x = 1
    expression: '@in_all + ''## '' + @in_title + ''\\n'' + @in_draft + ''\\n'' + @in_more'
""")
    out, _ = prettify(text)
    assert load(out) == load(text)
    comments = lambda t: [l for l in t.splitlines() if re.search(r"(^|\s)# ", l)]
    assert comments(out) == comments(text)                                                           # every comment, in place
    assert out.index("description") < out.index("code:") < out.index("expression")
    assert 'description: "stays in double quotes' in out


def test_what_cannot_be_a_block_is_kept_and_listed():
    text = graph("""- id: a
  type: SOLVE
  config:
    code: "x = 1\\ny = '\\x01'"
    result: x
""")                                                                                   # a control character: YAML cannot write it in a block
    out, report = prettify(text)
    assert load(out) == load(text)
    assert [k for k in report.kept if k.startswith("a.code")] and not report.rewritten and "\\x01" in out


def test_a_comment_next_to_the_value_keeps_it_as_it_was():
    text = graph("""- id: a
  type: CONTEXT
  config:
    action: set
    expression: '@in_all + ''## '' + @in_title + ''\\n'' + @in_draft + ''\\n'''  # joins them
""")
    out, report = prettify(text)
    assert load(out) == load(text) and "# joins them" in out and report.kept and not report.rewritten


def test_text_inside_flow_style_is_left_alone():
    text = r"""workflow: {name: t}
steps:
  - wants_read: {evaluate: "json_get(@in_decision, 'action') == 'read' AND json_get(@in_decision, 'file') in ['pricing.md', 'holidays.md']", on: ask.complete}
"""
    out, report = prettify(text)
    assert load(out) == load(text) and "\x07" not in out and not report.rewritten


@pytest.mark.parametrize("text", ["", "- just\n- a list\n", "a: [unclosed\n"])
def test_a_file_that_is_not_a_graph_is_refused(text):
    with pytest.raises(PrettierError):
        prettify(text)


def test_the_command_writes_the_new_file_and_leaves_the_old_one(tmp_path):
    source = tmp_path / "w.graph.yaml"
    source.write_text(graph(QUOTED))
    target = tmp_path / "w-v2.graph.yaml"
    result = CliRunner().invoke(graf, ["prettier", str(source), "-o", str(target)])
    assert result.exit_code == 0, result.output
    assert source.read_text() == graph(QUOTED) and "expression: |-" in target.read_text()
    assert load(target.read_text()) == load(source.read_text())
    assert "1 attribute(s) rewritten" in result.output


def test_the_command_prints_without_o_and_can_replace_the_file_itself(tmp_path):
    source = tmp_path / "w.graph.yaml"
    source.write_text(graph(QUOTED))
    printed = CliRunner().invoke(graf, ["prettier", str(source)])
    assert printed.exit_code == 0 and "expression: |-" in printed.output and source.read_text() == graph(QUOTED)
    assert CliRunner().invoke(graf, ["prettier", str(source), "-o", str(source)]).exit_code == 0
    assert "expression: |-" in source.read_text()


def test_the_command_reports_a_bad_file_and_writes_nothing(tmp_path):
    source = tmp_path / "bad.graph.yaml"
    source.write_text("a: [unclosed\n")
    target = tmp_path / "out.graph.yaml"
    result = CliRunner().invoke(graf, ["prettier", str(source), "-o", str(target)])
    assert result.exit_code == 1 and "not valid YAML" in " ".join(result.output.split()) and not target.exists()
    assert CliRunner().invoke(graf, ["prettier", str(tmp_path / "missing.graph.yaml")]).exit_code != 0


@pytest.mark.parametrize("path", [
    "cookbook/self_refine/self_refine.graph.yaml",
    "cookbook/solver_check/solver_check.graph.yaml",
    "cookbook/agent_notes/agent_notes.graph.yaml",                 # steps written in flow style: once corrupted a value
    "cookbook_pocketflow/writer_workflow/article_writer.graph.yaml",
])
def test_the_shipped_recipes_reformat_to_the_same_values_and_stay_put_when_run_again(path):
    text = (ROOT / path).read_text(encoding="utf-8")
    out, _ = prettify(text)
    assert load(out) == load(text)
    assert prettify(out)[0] == out
    assert [l for l in text.splitlines() if l.lstrip().startswith("#")] == [l for l in out.splitlines() if l.lstrip().startswith("#")]


def test_everything_but_the_target_attributes_stays_byte_for_byte():
    """A long value wrapped by whoever generated the file, odd spacing and CRLF line ends are not touched: only the target text is replaced."""
    body = graph("""- id: a
  type: CONTEXT
  config:
    action: set
    expression: '''false'''
  note:   "spacing   kept"
inputs:
- name: text
  default: Machine learning is a branch of artificial intelligence that enables
    computers to learn from data without being explicitly programmed.
""")
    for text in (body, body.replace("\n", "\r\n")):
        out, report = prettify(text)
        assert load(out) == load(text) and len(report.rewritten) == 1
        nl = "\r\n" if "\r\n" in text else "\n"
        assert out == text.replace("""expression: '''false'''""", """expression: "'false'\"""")          # that one span, nothing else
        assert f"enables{nl}    computers" in out and "note:   \"spacing   kept\"" in out
