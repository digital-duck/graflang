"""cookbook_v2/problem_solver: a model picks a solver from the catalogue, the problem is bound to its inputs, MUTATE adds the solver and it runs. Offline: a
scripted model answers by what the prompt asks (the sql_verifier solver really runs, on SQLite); the other solvers need their libraries, so only their interface is checked."""
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from graphlang.grafr.parts import part_file
from graphlang.grafr.runtime import GraphLangRuntime, load_graph
from graphlang.grafr.topology import check

ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / "cookbook_v2" / "problem_solver"
GRAPH = RECIPE / "problem_solver.graph.yaml"
TOOL = RECIPE / "tools" / "solver_tool.py"
MANIFEST = json.loads((RECIPE / "tools" / "solvers.json").read_text())
QUESTION = "What is the average salary in the Engineering department?"
SQL = "SELECT AVG(salary) AS avg_salary FROM employees WHERE department = 'Engineering';"


class Keyed:
    """A model that answers by the prompt: the first rule whose key is in the prompt, its replies one after the other (the last one repeats)."""
    name, adapter_name = "keyed", "echo"

    def __init__(self, **rules):
        self.rules, self.calls = {k: list(v) if isinstance(v, list) else [v] for k, v in rules.items()}, []

    def generate(self, prompt, model=None, **opts):
        for key, replies in self.rules.items():
            if key in prompt:
                self.calls.append(key)
                return replies.pop(0) if len(replies) > 1 else replies[0]
        self.calls.append("sql")
        return SQL


def solver(name, reason="fits"):
    return json.dumps({"solver": name, "reason": reason})


def run(monkeypatch, llm, problem=QUESTION):
    monkeypatch.chdir(RECIPE)
    return GraphLangRuntime(load_graph(GRAPH), llm=llm, verbose=False).execute({"problem": problem})["report"]


def tool(**job):
    done = subprocess.run([sys.executable, "-I", str(TOOL)], input=json.dumps(job), capture_output=True, text=True, check=True)
    return json.loads(done.stdout)


def test_the_recipe_validates_with_no_errors_and_no_warnings():
    assert check(load_graph(GRAPH)) == ([], [])


def test_the_top_level_reads_as_a_handful_of_boxes():
    from graphlang.grafv.model import build
    top, _ = build(load_graph(GRAPH), 0)
    assert top.number_of_nodes() <= 16 and {"choose", "bind", "fields", "pick"} <= {n.split("/")[-1] for n in top.nodes}


# ---- the catalogue is one list: the manifest, the graph's catalogue and the solver recipes must agree ---------------------------------------------------------

def test_the_graphs_catalogue_and_the_manifest_name_the_same_solvers_and_files():
    pick = next(n for n in load_graph(GRAPH)["nodes"] if n["type"] == "MUTATE")
    assert {k: part_file(v, RECIPE).resolve() for k, v in pick["config"]["catalogue"].items()} == {k: (RECIPE / v["part"]).resolve() for k, v in MANIFEST.items()}


@pytest.mark.parametrize("name", sorted(MANIFEST))
def test_each_solvers_declared_inputs_and_output_exist_in_its_recipe(name):
    spec = MANIFEST[name]
    wf = yaml.safe_load((RECIPE / spec["part"]).read_text())["workflow"]
    inputs = {i["name"] for i in wf["inputs"]}
    assert set(spec["inputs"]) <= inputs, f"{name}: {sorted(set(spec['inputs']) - inputs)} are not inputs of its recipe"
    # "required" here means the problem must supply the value (the recipes carry a demo default that must not be used silently), not that the recipe has none
    assert spec["output"] in {o["name"] for o in wf["outputs"]}
    text = (RECIPE / "fields" / "fields.graph.yaml").read_text()
    for k in spec["inputs"]:
        assert f"{k}:" in text, f"fields has no node for {k}"            # the delta wires fields__<k>


# ---- the check of what the model proposed ------------------------------------------------------------------------------------------------------------------------

def test_the_check_accepts_inputs_and_builds_the_delta_itself():
    out = tool(mode="check", solver="symbolic_math", reply='```json\n{"problem": "d/dx x^3"}\n```')
    delta = json.loads(out["delta"])
    assert out["ok"] and delta["payload"]["binds"] == {"problem": "fields__problem.out_value"} and delta["payload"]["feeds"] == {"explanation": ["report.in_answer"]}


@pytest.mark.parametrize("reply, words", [("no json at all", "no JSON"), ('{"colour": "red", "problem": "x"}', "not an input"), ('{"problem": ""}', "required"),
                                           ('{"problem": ["a"]}', "plain value")])
def test_the_check_refuses_bad_inputs_in_words_a_model_can_act_on(reply, words):
    out = tool(mode="check", solver="symbolic_math", reply=reply)
    assert not out["ok"] and words in out["error"]


def test_an_unknown_solver_is_none_and_a_required_input_is_enforced():
    assert tool(mode="choice", reply='{"solver": "dowsing", "reason": "x"}')["solver"] == "none"
    assert not tool(mode="check", solver="z3_compliance", reply="{}")["ok"]


# ---- the paths of a run -----------------------------------------------------------------------------------------------------------------------------------------------

def test_a_fitting_solver_is_added_and_runs_and_the_report_says_so(monkeypatch):
    llm = Keyed(**{"You choose ONE solver": solver("sql_verifier"), "You prepare the inputs": json.dumps({"question": QUESTION, "ground_truth_sql": SQL})})
    report = run(monkeypatch, llm)
    assert report.startswith("SOLVED BY THE CATALOGUE SOLVER sql_verifier") and "Round-trip check (row diff):** `match`" in report and "UNVERIFIED" not in report
    assert "fallback" not in llm.calls and llm.calls.count("You prepare the inputs") == 1


def test_a_refused_input_is_repaired_once_with_the_reason(monkeypatch):
    llm = Keyed(**{"You choose ONE solver": solver("sql_verifier"), "You prepare the inputs": "I think so",
                   "were refused": json.dumps({"question": QUESTION, "ground_truth_sql": SQL})})
    report = run(monkeypatch, llm)
    assert report.startswith("SOLVED BY THE CATALOGUE SOLVER") and "were refused" in llm.calls


def test_inputs_that_stay_wrong_end_in_the_models_own_answer_marked_unverified(monkeypatch):
    llm = Keyed(**{"You choose ONE solver": solver("sql_verifier"), "You prepare the inputs": "nope", "were refused": "still nope",
                   "Answer the problem below yourself": "About 97 thousand."})
    report = run(monkeypatch, llm)
    assert report.startswith("UNVERIFIED") and "could not be bound" in report and "About 97 thousand." in report


def test_when_no_solver_fits_the_model_answers_alone_and_the_report_says_so(monkeypatch):
    llm = Keyed(**{"You choose ONE solver": solver("none", "this is a poem, not a computation"), "Answer the problem below yourself": "Roses are red."})
    report = run(monkeypatch, llm, "Write a poem about spring")
    assert report.startswith("UNVERIFIED") and "No catalogue solver fits" in report and "this is a poem" in report and "Roses are red." in report
    assert "You prepare the inputs" not in llm.calls                      # nothing was bound or added
