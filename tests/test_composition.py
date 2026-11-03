"""Recipes as building blocks: a workflow file used as a node of another (grafr/parts.py).

Two things made most recipes unusable as parts, and are tested here: a part may now end in several OUTPUT nodes (each branch of a
branching recipe has its own), and the `file` of a QUERY or EMIT inside a part is read from the part's folder, not the using graph's."""
import json
import shutil
from pathlib import Path

import pytest
import yaml

from graphlang.grafr.parts import PartError
from graphlang.grafr.runtime import GraphLangRuntime, load_graph
from graphlang.grafr.topology import check

COOKBOOK = Path(__file__).resolve().parent.parent / "cookbook"


class Scripted:
    name, adapter_name, model_override = "scripted", "echo", None

    def __init__(self, *rules):
        self.rules, self.calls = list(rules), []

    def generate(self, prompt, model=None, **opts):
        for needle, reply in self.rules:
            if needle in prompt:
                self.calls.append(needle)
                if isinstance(reply, list):
                    return reply.pop(0) if len(reply) > 1 else reply[0]
                return reply
        raise AssertionError(f"no rule for prompt: {prompt[:100]!r}")


def wrap(tmp_path: Path, recipe: str, inputs, outputs, defaults=None) -> Path:
    """A parent graph, in a folder of its own, that is nothing but the recipe (copied under parts/) used as one node."""
    parts = tmp_path / "parts"
    parts.mkdir(exist_ok=True)
    shutil.copytree(COOKBOOK / recipe, parts / recipe, ignore=shutil.ignore_patterns("output"))
    graph = {"version": "1.0-graph",
             "workflow": {"name": f"use_{recipe}", "inputs": [{"name": i, "type": "TEXT", **({"default": defaults[i]} if defaults and i in defaults else {})} for i in inputs],
                          "outputs": [{"name": o, "type": "TEXT"} for o in outputs]},
             "resources": {"parts": {recipe: f"./parts/{recipe}/{recipe}.graph.yaml"}},
             "nodes": [{"id": "wf_entry", "type": "INPUT", "ports": ["entry"] + [f"out_{i}" for i in inputs]},
                       {"id": "use", "type": "SUBGRAPH", "config": {"part": f"parts.{recipe}"}, "ports": ["trigger", "complete"] + [f"in_{i}" for i in inputs] + [f"out_{o}" for o in outputs]},
                       {"id": "wf_exit", "type": "OUTPUT", "ports": ["trigger", "exit"] + [f"in_{o}" for o in outputs]}],
             "edges": [{"source": "wf_entry.entry", "target": "use.trigger", "type": "triggers"},
                       {"source": "use.complete", "target": "wf_exit.trigger", "type": "triggers"}]
             + [{"source": f"wf_entry.out_{i}", "target": f"use.in_{i}", "type": "binds"} for i in inputs]
             + [{"source": f"use.out_{o}", "target": f"wf_exit.in_{o}", "type": "binds"} for o in outputs]}
    path = tmp_path / f"use_{recipe}.graph.yaml"
    path.write_text(yaml.safe_dump(graph, sort_keys=False))
    return path


def run(path, llm, **params):
    graph = load_graph(path)
    errors, _ = check(graph)
    assert errors == [], errors
    return GraphLangRuntime(graph, llm=llm, verbose=False, effects=True).execute(params)


# ---- a part with several exits -----------------------------------------------------------------------------------
def test_a_branching_recipe_is_a_part_and_each_branch_reaches_the_parent(tmp_path):
    path = wrap(tmp_path, "guardrail", ["question"], ["reply"])
    on = Scripted(("guardrail for a travel advisor", "YES"), ("You are a travel advisor", "Pack layers."))
    assert run(path, on, question="Iceland?") == {"reply": "Pack layers."}
    off = Scripted(("guardrail for a travel advisor", "NO"), ("not about travel", "Travel only."))
    assert run(path, off, question="linked list?") == {"reply": "Travel only."}
    assert "You are a travel advisor" not in off.calls


def test_two_exits_that_write_the_same_output_are_not_a_race(tmp_path):
    graph = load_graph(wrap(tmp_path, "guardrail", ["question"], ["reply"]))
    errors, _ = check(graph)
    assert not any("race" in m for m in errors)
    assert {n["id"] for n in graph["nodes"]} >= {"use__check", "use__advise", "use__decline"}        # one flat graph, the part's nodes prefixed


def test_a_part_with_two_outputs_and_two_exits(tmp_path):
    path = wrap(tmp_path, "supervisor", ["question"], ["answer", "status"])
    llm = Scripted(("Answer the question", "Rayleigh scattering."), ("You supervise", "APPROVED"))
    assert run(path, llm, question="Why is the sky blue?") == {"answer": "Rayleigh scattering.", "status": "approved by the supervisor"}
    llm = Scripted(("Answer the question", "meh"), ("You supervise", "No."))
    out = run(path, llm, question="Why?")
    assert out["answer"] == "meh" and out["status"].startswith("not approved after 3 rounds")


def test_a_looping_recipe_with_two_exits_is_a_part(tmp_path):
    path = wrap(tmp_path, "self_heal", ["text"], ["record", "status"])
    good = json.dumps({"name": "Tom", "email": "unknown"})
    llm = Scripted(("Extract the contact", "```bad```"), ("earlier reply was checked", good))
    assert run(path, llm, text="Tom") == {"record": good, "status": "valid"}


def test_a_part_without_an_output_node_is_refused(tmp_path):
    path = wrap(tmp_path, "guardrail", ["question"], ["reply"])
    part = tmp_path / "parts" / "guardrail" / "guardrail.graph.yaml"
    data = yaml.safe_load(part.read_text())
    data = __import__("graphlang.grafr.compact", fromlist=["expand"]).expand(data)
    data["nodes"] = [n for n in data["nodes"] if n["type"] != "OUTPUT"]
    part.write_text(yaml.safe_dump(data, sort_keys=False))
    with pytest.raises(PartError, match="at least one OUTPUT"):
        load_graph(path)


# ---- paths belong to the part that wrote them -------------------------------------------------------------------
def test_a_part_reads_and_writes_in_its_own_folder(tmp_path):
    path = wrap(tmp_path, "notes_digest", [], ["digest"])
    llm = Scripted(("Summarise the notes", "Digest: disk fixed."))
    assert run(path, llm) == {"digest": "Digest: disk fixed."}
    part_dir = tmp_path / "parts" / "notes_digest"
    assert (part_dir / "output" / "digest.md").read_text() == "Digest: disk fixed."          # written beside the part, read from its input/
    assert not (tmp_path / "output").exists()                                                  # not in the using graph's folder


def test_a_path_passed_in_is_the_using_graphs_business(tmp_path):
    path = wrap(tmp_path, "chat_memory", ["message"], ["reply"])

    class Llm(Scripted):
        def generate(self, prompt, model=None, **opts):
            return "Noted."
    run(path, Llm(), message="My name is Wen.")
    assert (tmp_path / "output" / "memory.md").read_text() == "You: My name is Wen.\nAssistant: Noted.\n"      # the memory lives with the user
    assert not (tmp_path / "parts" / "chat_memory" / "output").exists()


def test_a_part_cannot_reach_outside_its_folder(tmp_path):
    (tmp_path / "secret.txt").write_text("no")
    path = wrap(tmp_path, "notes_digest", [], ["digest"])
    part = tmp_path / "parts" / "notes_digest" / "notes_digest.graph.yaml"
    data = yaml.safe_load(part.read_text())
    next(n for n in data["nodes"] if n["id"] == "read_notes")["config"]["file"] = "../../../secret.txt"      # out of the part, and out of the parent's folder too
    part.write_text(yaml.safe_dump(data, sort_keys=False))
    errors, _ = check(load_graph(path))
    assert any("outside the graph's folder" in m for m in errors)


def test_a_graph_file_cannot_ask_for_a_folder_through_a_hidden_key(tmp_path):
    """allow_dirs in a plain graph is the author's own choice, but a part's folder is added only by the expansion: nothing in the file can name it."""
    path = wrap(tmp_path, "notes_digest", [], ["digest"])
    graph = load_graph(path)
    read = next(n for n in graph["nodes"] if n["id"] == "use__read_notes")
    assert Path(read["config"]["file"]).is_absolute() and str(tmp_path / "parts" / "notes_digest") in read["config"]["allow_dirs"]


# ---- parts of parts ---------------------------------------------------------------------------------------------
def test_a_part_may_use_a_part(tmp_path):
    inner = wrap(tmp_path, "guardrail", ["question"], ["reply"])           # use_guardrail.graph.yaml is itself a one-node wrapper
    outer_dir = tmp_path / "outer"
    outer_dir.mkdir()
    shutil.copytree(tmp_path / "parts", outer_dir / "parts")
    shutil.copy(inner, outer_dir / "parts" / "use_guardrail.graph.yaml")
    graph = yaml.safe_load(inner.read_text())
    graph["workflow"]["name"] = "outer"
    graph["resources"]["parts"] = {"guardrail": "./parts/use_guardrail.graph.yaml"}
    graph["nodes"][1]["config"]["part"] = "parts.guardrail"
    outer = outer_dir / "outer.graph.yaml"
    outer.write_text(yaml.safe_dump(graph, sort_keys=False))
    # the middle file refers to parts/guardrail relative to itself
    middle = yaml.safe_load((outer_dir / "parts" / "use_guardrail.graph.yaml").read_text())
    middle["resources"]["parts"] = {"guardrail": "./guardrail/guardrail.graph.yaml"}
    (outer_dir / "parts" / "use_guardrail.graph.yaml").write_text(yaml.safe_dump(middle, sort_keys=False))
    llm = Scripted(("guardrail for a travel advisor", "YES"), ("You are a travel advisor", "Pack layers."))
    assert run(outer, llm, question="Iceland?") == {"reply": "Pack layers."}


# ---- step 6: a composite made only of existing recipes (the acceptance test of the part interface) -----------------
def test_recipe_chain_is_built_from_untouched_recipes(tmp_path):
    """guardrail -> agent_notes -> supervisor, joined by `use` in cookbook/recipe_chain. If this needs a recipe changed, the part interface is wrong."""
    for name in ("recipe_chain", "guardrail", "agent_notes", "supervisor"):
        shutil.copytree(COOKBOOK / name, tmp_path / name, ignore=shutil.ignore_patterns("output"))
    llm = Scripted(
        ("guardrail for a travel advisor", "YES"),
        ("You are a travel advisor", "What does the Team plan cost?"),            # the guardrail's reply becomes the agent's question
        ("You answer a question using a small set of notes", ['{"action": "read", "file": "pricing.md"}', '{"action": "answer", "text": "29 euro per user."}']),
        ("Answer the question in at most three sentences", "29 euro per user per month."),
        ("You supervise", "APPROVED"),
    )
    out = run(tmp_path / "recipe_chain" / "recipe_chain.graph.yaml", llm, question="Team plan price?")
    assert out["answer"] == "29 euro per user per month." and out["status"] == "approved by the supervisor"
    assert llm.calls.index("guardrail for a travel advisor") < llm.calls.index("You answer a question using a small set of notes") < llm.calls.index("You supervise")


def test_recipe_chain_refusal_still_flows_to_the_end(tmp_path):
    for name in ("recipe_chain", "guardrail", "agent_notes", "supervisor"):
        shutil.copytree(COOKBOOK / name, tmp_path / name, ignore=shutil.ignore_patterns("output"))
    llm = Scripted(
        ("guardrail for a travel advisor", "NO"),
        ("not about travel", "Travel only."),
        ("You answer a question using a small set of notes", '{"action": "answer", "text": "nothing to read"}'),
        ("Answer the question in at most three sentences", "ok"),
        ("You supervise", "APPROVED"),
    )
    out = run(tmp_path / "recipe_chain" / "recipe_chain.graph.yaml", llm, question="linked list?")
    assert out["status"] == "approved by the supervisor"


# ---- step 3: parts by name, pinned -------------------------------------------------------------------------------
def _named(tmp_path, monkeypatch, ref):
    home = tmp_path / "home"
    (home / "cookbook").mkdir(parents=True)
    shutil.copytree(COOKBOOK / "guardrail", home / "cookbook" / "guardrail", ignore=shutil.ignore_patterns("output"))
    monkeypatch.setenv("GRAFLANG_HOME", str(home))
    path = wrap(tmp_path, "guardrail", ["question"], ["reply"])
    g = yaml.safe_load(path.read_text())
    g["resources"]["parts"]["guardrail"] = ref
    path.write_text(yaml.safe_dump(g, sort_keys=False))
    return path


def test_a_part_can_be_named_by_recipe(tmp_path, monkeypatch):
    path = _named(tmp_path, monkeypatch, "cookbook:guardrail")
    on = Scripted(("guardrail for a travel advisor", "YES"), ("You are a travel advisor", "Pack layers."))
    assert run(path, on, question="Iceland?") == {"reply": "Pack layers."}


def test_a_pinned_part_runs_and_a_changed_one_is_refused(tmp_path, monkeypatch):
    from graphlang.grafr.parts import folder_hash
    home = tmp_path / "home" / "cookbook" / "guardrail"
    pin = folder_hash(COOKBOOK / "guardrail")
    path = _named(tmp_path, monkeypatch, f"cookbook:guardrail@{pin}")
    assert run(path, Scripted(("guardrail for a travel advisor", "YES"), ("You are a travel advisor", "ok")), question="x") == {"reply": "ok"}
    (home / "prompts" / "answer.md").write_text((home / "prompts" / "answer.md").read_text() + "\nBe brief.")
    with pytest.raises(PartError, match="changed since it was pinned"):
        load_graph(path)


def test_an_unknown_named_part_says_where_it_looked(tmp_path, monkeypatch):
    path = _named(tmp_path, monkeypatch, "cookbook:nonesuch")
    with pytest.raises(PartError, match="no recipe 'nonesuch'"):
        load_graph(path)


# ---- steps 4 and 5: capabilities and cost at the boundary, descriptions and promised shapes ------------------------
def _with_header(path, **header):
    g = yaml.safe_load(path.read_text())
    g["workflow"].update(header)
    path.write_text(yaml.safe_dump(g, sort_keys=False))


def test_capabilities_of_recipes():
    from graphlang.grafr.partinfo import capabilities
    gr = capabilities(load_graph(COOKBOOK / "guardrail" / "guardrail.graph.yaml")["nodes"])
    assert gr["llm_calls"] == 3 and gr["read"] == [] and gr["program"] == []
    nd = capabilities(load_graph(COOKBOOK / "notes_digest" / "notes_digest.graph.yaml")["nodes"])
    assert nd["read"] and nd["write"] and nd["stdout"]


def test_parent_can_forbid_what_a_part_does(tmp_path):
    path = wrap(tmp_path, "agent_notes", ["question"], ["answer"], {})
    _with_header(path, parts_policy={"forbid": ["read"]})
    with pytest.raises(PartError, match="forbids \\['read'\\]"):
        load_graph(path)
    _with_header(path, parts_policy={"forbid": ["email", "program"]})
    load_graph(path)


def test_parts_together_are_held_to_the_call_cap(tmp_path):
    path = wrap(tmp_path, "guardrail", ["question"], ["reply"])
    _with_header(path, parts_policy={"max_llm_calls": 2})
    with pytest.raises(PartError, match="over parts_policy.max_llm_calls 2"):
        load_graph(path)
    _with_header(path, parts_policy={"max_llm_calls": 3})
    load_graph(path)


def test_a_bad_policy_is_refused(tmp_path):
    path = wrap(tmp_path, "guardrail", ["question"], ["reply"])
    _with_header(path, parts_policy={"forbid": ["telepathy"]})
    with pytest.raises(PartError, match="telepathy"):
        load_graph(path)


def test_graf_parts_lists_the_uses(tmp_path):
    from click.testing import CliRunner
    from graphlang.cli import main
    path = wrap(tmp_path, "guardrail", ["question"], ["reply"])
    res = CliRunner().invoke(main, ["parts", str(path)])
    assert res.exit_code == 0, res.output
    assert "use: guardrail" in res.output and "hash " in res.output and "what the user asks" in res.output and "up to 3 model calls" in res.output


def _shape_part(tmp_path, schema):
    folder = tmp_path / "parts" / "shape"
    folder.mkdir(parents=True)
    (folder / "prompts").mkdir()
    (folder / "prompts" / "make.md").write_text("make json for {{in_topic}}")
    out = {"name": "data", "type": "TEXT", "description": "a record"}
    if schema:
        out["schema"] = schema
    part = {"version": "1.0-graph", "workflow": {"name": "shape", "inputs": [{"name": "topic", "type": "TEXT"}], "outputs": [out]},
            "resources": {"prompts": {"make": "./prompts/make.md"}},
            "steps": [{"make": {"generate": "prompts.make", "in": {"topic": "$in.topic"}, "out": "data"}}, {"done": {"output": "make.data"}}]}
    (folder / "shape.graph.yaml").write_text(yaml.safe_dump(part, sort_keys=False))
    parent = {"version": "1.0-graph", "workflow": {"name": "p", "inputs": [{"name": "topic", "type": "TEXT"}], "outputs": [{"name": "data", "type": "TEXT"}]},
              "resources": {"parts": {"shape": "./parts/shape/shape.graph.yaml"}},
              "steps": [{"s": {"use": "parts.shape", "in": {"topic": "$in.topic"}, "out": "data"}}, {"done": {"output": "s.data"}}]}
    path = tmp_path / "p.graph.yaml"
    path.write_text(yaml.safe_dump(parent, sort_keys=False))
    return path


def test_an_output_schema_is_enforced_where_the_part_makes_it(tmp_path):
    from graphlang.grafr.lifecycle import InvalidOutput
    schema = {"type": "object", "required": ["name"]}
    path = _shape_part(tmp_path, schema)
    good = run(path, Scripted(("make json", '{"name": "Ada"}')), topic="x")
    assert good["data"] == {"name": "Ada"}
    with pytest.raises(Exception) as err:
        run(path, Scripted(("make json", '{"age": 3}')), topic="x")
    assert "name" in str(err.value) or isinstance(err.value, InvalidOutput)


def test_a_part_without_a_schema_returns_text_as_before(tmp_path):
    path = _shape_part(tmp_path, None)
    assert run(path, Scripted(("make json", '{"age": 3}')), topic="x")["data"] == '{"age": 3}'
