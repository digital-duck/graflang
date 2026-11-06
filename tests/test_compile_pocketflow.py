"""`graf compile --lang pocketflow`: what it writes, what it refuses, and that the program it writes behaves like the graph."""
import importlib.util
import sys
import textwrap
from pathlib import Path

import pytest
from click.testing import CliRunner

from graphlang.cli import main
from graphlang.grafe.graph2pocketflow import GraphToPocketFlowError, graph_to_pocketflow
from graphlang.grafr.runtime import GraphLangRuntime, load_graph

ROOT = Path(__file__).resolve().parent.parent

GRAPH = '''
version: "1.0-graph"
workflow:
  name: refine_t
  inputs: [{name: topic, type: TEXT, default: ducks}]
  outputs: [{name: essay, type: TEXT}, {name: note, type: TEXT}]
resources: {prompts: {draft: ./draft.md, crit: ./crit.md}}
steps:
  - draft: {generate: prompts.draft, in: {topic: $in.topic}, out: essay}
  - ok: {evaluate: "len(@in_text) > 10 AND NOT contains(@in_text, 'TODO')", in: {text: draft}}
  - crit: {generate: prompts.crit, on: ok.fail, in: {essay: draft}, out: feedback}
  - redo: {generate: prompts.draft, in: {topic: crit}, out: essay}
  - note: {solve: "'checked: ' + upper(@in_text)", in: {text: redo}, out: note}
  - bad: {output: {essay: redo, note: note}, on: note}
  - good: {output: {essay: draft, note: draft}, on: ok.pass}
'''


@pytest.fixture
def graph_file(tmp_path):
    (tmp_path / "draft.md").write_text("Write about {{in_topic}}.\n")
    (tmp_path / "crit.md").write_text("Critique {{in_essay}}\n")
    p = tmp_path / "refine_t.graph.yaml"
    p.write_text(textwrap.dedent(GRAPH))
    return p


def compile_text(path):
    text, warnings = graph_to_pocketflow(load_graph(path))
    return text, warnings


def test_the_program_wires_control_flow_with_actions_and_starts_at_the_entry(graph_file):
    text, warnings = compile_text(graph_file)
    compile(text, "generated.py", "exec")
    for wire in ("n_draft - 'complete' >> n_ok", "n_ok - 'fail' >> n_crit", "n_ok - 'pass' >> n_good", "n_crit - 'complete' >> n_redo"):
        assert wire in text
    assert "Flow(start=n_draft)" in text and "graflang" not in text.split('"""', 2)[2] and "import graphlang" not in text


def test_the_command_prints_writes_and_dry_runs(graph_file, tmp_path):
    runner = CliRunner()
    out = runner.invoke(main, ["compile", str(graph_file), "--lang", "pocketflow"])
    assert out.exit_code == 0 and "class Draft(Node)" in out.output
    dest = tmp_path / "p.py"
    assert runner.invoke(main, ["compile", str(graph_file), "--lang", "pocketflow", "-o", str(dest)]).exit_code == 0 and dest.is_file()
    dry = runner.invoke(main, ["compile", str(graph_file), "--lang", "pocketflow", "--dry-run"])
    assert dry.exit_code == 0 and "compiles to PocketFlow" in dry.output


@pytest.mark.parametrize("recipe,ids", [("compliance_audit/compliance_audit.graph.yaml", ["release_guard (GUARD)"]),
                                         ("pocketflow/majority_vote.graph.yaml", ["(FORK)"]), ("self_refine/self_refine.graph.yaml", None)])
def test_what_pocketflow_cannot_say_is_refused_with_the_node_ids(recipe, ids):
    graph = load_graph(ROOT / "cookbook" / recipe)
    if ids is None:
        text, warnings = graph_to_pocketflow(graph)                      # three GENERATE nodes in a line: fine, with the per-node llm dropped
        assert "n_draft - 'complete' >> n_critique" in text and any("llm choice" in w for w in warnings)
        return
    with pytest.raises(GraphToPocketFlowError) as e:
        graph_to_pocketflow(graph)
    assert all(i in str(e.value) for i in ids)


def test_a_port_that_triggers_two_nodes_and_an_unsupported_function_are_refused(graph_file, tmp_path):
    graph = load_graph(graph_file)
    graph["edges"].append({"source": "draft.complete", "target": "crit.trigger", "type": "triggers"})
    with pytest.raises(GraphToPocketFlowError, match="one successor per action"):
        graph_to_pocketflow(graph)
    graph = load_graph(graph_file)
    next(n for n in graph["nodes"] if n["id"] == "ok")["config"]["condition"] = "has_pii(@in_text)"
    with pytest.raises(GraphToPocketFlowError, match="has_pii"):
        graph_to_pocketflow(graph)


def _load_program(text, tmp_path):
    pytest.importorskip("pocketflow")
    pytest.importorskip("openai")
    path = tmp_path / "program.py"
    path.write_text(text)
    spec = importlib.util.spec_from_file_location("program_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["program_under_test"] = mod
    spec.loader.exec_module(mod)
    return mod


class Replies:
    """Plays the model for both the runtime and the generated program: the same replies in the same order."""
    name, adapter_name, model_override = "stub", "echo", None

    def __init__(self, replies):
        self.replies, self.prompts = list(replies), []

    def generate(self, prompt, model=None, **opts):
        self.prompts.append(prompt)
        return self.replies.pop(0)

    __call__ = generate


@pytest.mark.parametrize("replies,expect_path", [(["a long enough draft about ducks"], "pass"), (["TODO", "critique text", "a redone long essay"], "fail")])
def test_the_generated_program_gives_the_same_outputs_and_prompts_as_the_graph(graph_file, tmp_path, replies, expect_path):
    graph_llm = Replies(replies)
    expected = GraphLangRuntime(load_graph(graph_file), llm=graph_llm, verbose=False).execute({"topic": "ducks"})
    mod = _load_program(compile_text(graph_file)[0], tmp_path)
    program_llm = Replies(replies)
    mod.call_llm = program_llm
    got = mod.run({"topic": "ducks"})
    assert got == expected and set(got) == {"essay", "note"}
    assert program_llm.prompts == graph_llm.prompts                      # the same prompts, filled the same way, in the same order
    assert (len(replies) == 1) == (expect_path == "pass")
