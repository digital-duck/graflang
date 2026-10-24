"""procedure_ref nodes run SPL.py workflows through SPL.py's own executor. Uses SPL.py's `echo` adapter
(returns the prompt, no LLM), so it needs SPL.py importable and skips otherwise."""
from pathlib import Path

import pytest

pytest.importorskip("spl3.executor")

from graphlang.grafr.adapters import make_llm
from graphlang.grafr.procedures import declared_inputs, run_procedure
from graphlang.grafr.runtime import GraphLangRuntime, load_graph

CODE = Path(__file__).parent.parent / "cookbook" / "code_pipeline"


def test_declared_inputs_come_from_the_spl_file():
    assert declared_inputs(CODE / "00_analyze_spec.spl") == ["spec", "analyze_model", "log_dir"]
    assert declared_inputs(CODE / "07_spec_judge.spl") == ["spec", "out_spec", "judge_model", "log_dir"]


def test_a_workflow_runs_and_its_output_comes_back(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)                                     # the .spl would otherwise write under ./cookbook/...
    out = run_procedure(CODE / "00_analyze_spec.spl", {"spec": "add two numbers", "ignored": "x"}, "echo",
                        log_dir=tmp_path / "logs")
    assert "SPEC:\nadd two numbers" in out                          # echo returns the prompt the workflow built
    assert (tmp_path / "logs" / "spec" / "analysis.md").exists()    # side files went where we said
    assert not (tmp_path / "cookbook").exists()


def test_spl_failures_surface_as_errors(tmp_path):
    bad = tmp_path / "bad.spl"
    bad.write_text("-- no workflow here\nCREATE FUNCTION f(x TEXT)\nRETURN TEXT\nAS $$\nhi {x}\n$$;\n")
    with pytest.raises(ValueError, match="defines no WORKFLOW"):
        run_procedure(bad, {}, "echo")


def graph_with_procedure(params=None):
    cfg = {"procedure_ref": "procedures.spec_judge"}
    if params:
        cfg["params"] = params
    return {"version": "1.0-graph", "_source_dir": str(CODE),
            "resources": {"procedures": {"spec_judge": "./07_spec_judge.spl"}},
            "workflow": {"name": "t", "inputs": [{"name": "a", "type": "TEXT"}, {"name": "b", "type": "TEXT"}],
                         "outputs": [{"name": "r", "type": "TEXT"}]},
            "nodes": [{"id": "s", "type": "INPUT", "ports": ["entry", "out_a", "out_b"]},
                      {"id": "j", "type": "GENERATE", "config": cfg,
                       "ports": ["trigger", "complete", "in_orig", "in_derived", "out_report"]},
                      {"id": "e", "type": "OUTPUT", "ports": ["trigger", "exit", "in_result"]}],
            "edges": [{"source": "s.entry", "target": "j.trigger", "type": "triggers"},
                      {"source": "j.complete", "target": "e.trigger", "type": "triggers"},
                      {"source": "s.out_a", "target": "j.in_orig", "type": "binds"},
                      {"source": "s.out_b", "target": "j.in_derived", "type": "binds"},
                      {"source": "j.out_report", "target": "e.in_result", "type": "binds"}]}


def test_a_node_maps_ports_to_spl_parameters_and_runs_the_procedure(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rt = GraphLangRuntime(graph_with_procedure({"spec": "in_orig", "out_spec": "in_derived"}),
                          llm=make_llm("echo"), verbose=False)
    out = rt.execute({"a": "ORIGINAL-SPEC", "b": "DERIVED-SPEC"})
    assert "ORIGINAL-SPEC" in out["r"] and "DERIVED-SPEC" in out["r"]
    assert (CODE / ".grafr" / "logs").exists()                       # side files land beside the graph...
    import shutil
    shutil.rmtree(CODE / ".grafr")                                    # ...(git-ignored); clean up after the test


def test_a_bad_params_mapping_is_an_error():
    rt = GraphLangRuntime(graph_with_procedure({"spec": "in_missing"}), llm=make_llm("echo"), verbose=False)
    with pytest.raises(ValueError, match="maps 'spec' to 'in_missing'"):
        rt.execute({"a": "x", "b": "y"})


def test_under_mock_a_procedure_node_is_not_run_but_reports_its_inputs():
    rt = GraphLangRuntime(graph_with_procedure(), verbose=False)
    out = rt.execute({"a": "AAA", "b": "BBB"})
    assert out["r"].startswith("[Mock procedure procedures.spec_judge]") and "in_orig=AAA" in out["r"]


def test_flagship_runs_end_to_end_with_echo_procedures(tmp_path, monkeypatch):
    """Every procedure in the flagship actually executes (echo adapter): the spec gate sees the analysis text,
    so the contains('[READY]') check is real. The echo prompt includes the string '[READY]' (the prompt lists the
    verdict tokens), so the gate passes and the whole pipeline runs."""
    monkeypatch.chdir(tmp_path)
    data = load_graph(CODE / "code_pipeline.graph.yaml")
    rt = GraphLangRuntime(data, llm=make_llm("echo"), verbose=False)
    out = rt.execute({"spec": "add two numbers", "max_cycles": 1, "check_closure": True})
    assert rt.fired["analyze"] == 1 and rt.fired["judge"] == 1 and "docs" in out
    import shutil
    shutil.rmtree(CODE / ".grafr", ignore_errors=True)


def test_a_tools_py_next_to_the_procedure_is_loaded_for_its_call_statements(tmp_path):
    (tmp_path / "tools.py").write_text(
        "from spl.tools import spl_tool\n\n@spl_tool\ndef shout(text: str) -> str:\n    return text.upper() + '!'\n")
    (tmp_path / "p.spl").write_text(
        'WORKFLOW p\n  INPUT: @word TEXT := "hi"\n  OUTPUT: @out TEXT\nDO\n  CALL shout(@word) INTO @out;\n'
        '  COMMIT @out WITH status = \'complete\'\nEND\n')
    assert run_procedure(tmp_path / "p.spl", {"word": "go"}, "echo") == "GO!"
