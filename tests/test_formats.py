"""GraphLang workflows and zinet graphs are told apart by content, never by file name."""
import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from graphlang.cli import main
from graphlang.formats import CONCEPTBOOK, GRAPHLANG, UNKNOWN, ZINET, detect

ROOT = Path(__file__).resolve().parent.parent
SELF_REFINE = ROOT / "cookbook" / "self_refine" / "self_refine.graph.yaml"
ZINET_GRAPH = """version: "1.0"
primitives:
  - id: x
concepts:
  - id: c
    deps: [x]
applications:
  - id: app
    deps: [c]
"""


@pytest.mark.parametrize("data, kind", [
    ({"version": "1.0-graph", "workflow": {"name": "w"}, "nodes": [], "edges": []}, GRAPHLANG),
    ({"nodes": [], "edges": []}, GRAPHLANG),
    ({"version": "1.0", "primitives": [], "concepts": []}, ZINET),
    ({"applications": [{"id": "a"}]}, ZINET),
    ({"domain": "x", "primitives": {"p": {"tier": 0}}, "concepts": {"a": {"composed_of": ["p"]}}}, CONCEPTBOOK),
    ({"primitives": None, "concepts": []}, ZINET),
    ({}, UNKNOWN), ({"hello": 1}, UNKNOWN), ([1, 2], UNKNOWN), (None, UNKNOWN),
])
def test_detect(data, kind):
    assert detect(data) == kind


@pytest.mark.parametrize("name", ["graph.yaml", "knowledge.yaml", "x.graph.yaml"])
@pytest.mark.parametrize("cmd", [["validate"], ["info"], ["vis", "--no-open"], ["check"]])
def test_every_command_explains_a_zinet_file_whatever_it_is_called(tmp_path, name, cmd):
    f = tmp_path / name
    f.write_text(ZINET_GRAPH)
    args = [*cmd, str(f)] + (["-o", str(tmp_path / "o.html")] if cmd[0] == "vis" else [])
    result = CliRunner().invoke(main, args)
    assert result.exit_code == 1, result.output
    assert "zinet graph" in result.output and "zinet validate" in result.output and "Traceback" not in result.output


def test_run_explains_a_zinet_file(tmp_path):
    f = tmp_path / "graph.yaml"
    f.write_text(ZINET_GRAPH)
    result = CliRunner().invoke(main, ["run", str(f), "--adapter", "mock", "--no-log", "--no-output"])
    assert result.exit_code == 1 and "is a zinet graph" in result.output


def test_a_graphlang_workflow_named_plain_graph_yaml_works(tmp_path):
    shutil.copytree(SELF_REFINE.parent / "prompts", tmp_path / "prompts")
    f = tmp_path / "graph.yaml"
    f.write_text(SELF_REFINE.read_text())
    assert CliRunner().invoke(main, ["validate", str(f)]).exit_code == 0
    result = CliRunner().invoke(main, ["run", str(f), "--adapter", "mock", "--param", "topic=ducks",
                                       "--log-dir", str(tmp_path / "logs"), "--output-dir", str(tmp_path / "out")])
    assert result.exit_code == 0, result.output
    assert next((tmp_path / "logs").glob("graph-mock-*.log"))                 # the run is named after the file stem


CONCEPTBOOK_GRAPH = """domain: demo
primitives:
  p: {tier: 0}
concepts:
  a: {composed_of: [p], tier: 1}
"""


@pytest.mark.parametrize("cmd", [["validate"], ["info"], ["check"]])
def test_a_conceptbook_graph_is_not_called_a_zinet_graph(tmp_path, cmd):
    f = tmp_path / "graph.yaml"
    f.write_text(CONCEPTBOOK_GRAPH)
    result = CliRunner().invoke(main, [*cmd, str(f)])
    assert result.exit_code == 1
    assert "ConceptBook / graph-code graph" in result.output and "grafcode validate" in result.output
    assert "is a zinet graph" not in result.output
