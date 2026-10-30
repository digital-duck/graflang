"""`graf import-spl`: lifting SPL.py workflows into graphs. Needs SPL.py importable (the `spl` extra)."""
import os
from pathlib import Path

import pytest
from click.testing import CliRunner

pytest.importorskip("spl3.parser")

from graphlang.cli import main
from graphlang.grafi.spl2graph import NoWorkflowError, graph_to_yaml, spl_to_graph
from graphlang.grafr.runtime import GraphLangRuntime, load_graph
from graphlang.grafr.topology import check

CHAIN = """
CREATE FUNCTION research(topic TEXT)
RETURNS TEXT
AS $$
Research {topic}.
$$;

CREATE FUNCTION analyze(research TEXT, depth TEXT)
RETURNS TEXT
AS $$
Analyze at {depth} depth: {research}
$$;

WORKFLOW chain
    INPUT: @topic TEXT DEFAULT 'sails'
    OUTPUT: @out TEXT
DO
    GENERATE research(@topic) INTO @research
    GENERATE analyze(@research, 'shallow') INTO @out
    RETURN @out
END
"""


def lift(source, tmp_path, **kw):
    graph, warnings = spl_to_graph(source, **kw)
    path = tmp_path / "x.graph.yaml"
    path.write_text(graph_to_yaml(graph))
    loaded = load_graph(path)
    return graph, warnings, loaded, check(loaded)


def node(graph, nid):
    return next(n for n in graph["nodes"] if n["id"] == nid)


def test_a_function_body_becomes_the_prompt_and_arguments_become_ports(tmp_path):
    graph, warnings, loaded, (errors, _) = lift(CHAIN, tmp_path)
    assert errors == [] and warnings == []
    assert node(graph, "gen_1")["config"]["prompt_inline"] == "Research {{in_topic}}."
    assert node(graph, "gen_2")["config"]["prompt_inline"] == "Analyze at shallow depth: {{in_research}}"   # literal inlined
    assert graph["workflow"]["inputs"][0]["default"] == "sails"                                             # not 'sails' in quotes


class Echo:
    name, model_override = "echo", None

    def __init__(self):
        self.prompts = []

    def generate(self, prompt, model=None, **opts):
        self.prompts.append(prompt)
        return f"R{len(self.prompts)}"


def test_the_lifted_chain_runs_and_each_step_sees_the_previous_answer(tmp_path):
    _, _, loaded, _ = lift(CHAIN, tmp_path)
    llm = Echo()
    out = GraphLangRuntime(loaded, llm=llm, verbose=False).execute({"topic": "tides"})
    assert llm.prompts == ["Research tides.", "Analyze at shallow depth: R1"] and out == {"out": "R2"}


def test_a_tool_call_in_an_assert_becomes_a_solve_node_that_runs_first(tmp_path):
    src = """
WORKFLOW w
    INPUT: @x TEXT
    OUTPUT: @x TEXT
DO
    ASSERT known(@x);
    RETURN @x
END
"""
    graph, _, _, (errors, _) = lift(src, tmp_path)
    assert errors == []
    tool = node(graph, "tool_1")
    assert tool["type"] == "SOLVE" and tool["config"]["expression"] == "known(@in_x)"
    assert node(graph, "assert_1")["config"]["condition"] == "@in_tool_1"


def test_while_in_condition_and_parallel_function_branches(tmp_path):
    src = """
CREATE FUNCTION pro(claim TEXT) RETURNS TEXT AS $$ For: {claim} $$;
CREATE FUNCTION con(claim TEXT) RETURNS TEXT AS $$ Against: {claim} $$;

WORKFLOW w
    INPUT: @claim TEXT, @items LIST
    OUTPUT: @a TEXT
DO
    CALL PARALLEL
        pro(@claim) INTO @a,
        con(@claim) INTO @b
    END
    @i := 0
    WHILE @i IN @items DO
        @i := @i + 1
    END
    RETURN @a
END
"""
    graph, _, _, (errors, _) = lift(src, tmp_path)
    assert errors == []
    assert {n["config"]["function"] for n in graph["nodes"] if n["type"] == "GENERATE"} == {"pro", "con"}


def test_a_file_without_a_workflow_is_reported_not_crashed():
    with pytest.raises(NoWorkflowError):
        spl_to_graph("CREATE FUNCTION f(x TEXT) RETURNS TEXT AS $$ hi {x} $$;")


def test_the_cli_writes_a_graph_next_to_the_input(tmp_path):
    src = tmp_path / "chain.spl"
    src.write_text(CHAIN)
    result = CliRunner().invoke(main, ["import-spl", str(src)])
    assert result.exit_code == 0, result.output
    assert check(load_graph(tmp_path / "chain.graph.yaml"))[0] == []


def _spl_cookbook():
    for base in (os.environ.get("SPL_PY_PATH"), Path(__file__).resolve().parents[2] / "SPL.py"):
        if base and (Path(base) / "cookbook").is_dir():
            return Path(base)


@pytest.mark.skipif(_spl_cookbook() is None, reason="needs a checkout of SPL.py (SPL_PY_PATH or ../SPL.py)")
def test_almost_every_cookbook_workflow_lifts_and_validates(tmp_path):
    root = _spl_cookbook()
    files = [p for d in ("cookbook", "cookbook-pocketflow") for p in sorted((root / d).rglob("*.spl"))
             if p.is_file() and not any(w in str(p) for w in ("generated", "/logs", ".spl/"))]
    ok = bad = 0
    for p in files:
        try:
            graph, _ = spl_to_graph(p.read_text(), source_name=p.name, source_dir=p.parent)
        except NoWorkflowError:
            continue                                                  # a tools or functions file, no workflow to lift
        except Exception:
            bad += 1
            continue
        f = tmp_path / "x.graph.yaml"
        f.write_text(graph_to_yaml(graph))
        loaded = load_graph(f)
        loaded["_source_dir"] = str(p.parent)
        errors, _ = check(loaded)
        ok, bad = ok + (not errors), bad + bool(errors)
    assert ok >= 250 and bad <= 0.05 * (ok + bad), (ok, bad)


@pytest.mark.llm
def test_real_llm_runs_a_lifted_chain(tmp_path):
    """claude_cli (claude-sonnet-5-5): two short calls."""
    _, _, loaded, _ = lift(CHAIN.replace("Research {topic}.", "In one sentence, what is {topic}?")
                           .replace("Analyze at {depth} depth: {research}", "Reply with one short sentence about this: {research}"),
                           tmp_path)
    out = GraphLangRuntime(loaded, adapter="claude_cli", verbose=False).execute({"topic": "a tide"})
    assert len(out["out"].strip()) > 10
