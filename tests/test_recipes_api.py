"""graphlang.recipes (Recipe / run_recipe) and the runtime changes it needs: one-pass prompt filling, a GENERATE's output budget,
adapter options, `python3` as the running interpreter, and the error exit a run ended at."""
import json
import sys
import types

import pytest
import yaml

from graphlang.grafr.adapters import DefaultsLLM, make_llm
from graphlang.grafr.nodes.generate import fill_prompt
from graphlang.grafr.solver import own_python
from graphlang.recipes import Recipe, RecipeError, run_recipe


class Model:
    name = "scripted"

    def __init__(self, reply="ok"):
        self.reply, self.calls = reply, []

    def generate(self, prompt, model=None, **opts):
        self.calls.append((prompt, opts))
        return self.reply(prompt) if callable(self.reply) else self.reply


def recipe(tmp_path, steps, *, inputs=("text",), outputs=("result",), errors=(), extra=None):
    doc = {"version": "1.0-graph",
           "workflow": {"name": "probe", "description": "probe",
                        "inputs": [{"name": n, "type": "TEXT", "default": ""} for n in inputs],
                        "outputs": [{"name": n, "type": "TEXT"} for n in outputs],
                        **({"errors": [{"name": n, "code": c, "description": n} for n, c in errors]} if errors else {})},
           "steps": steps, **(extra or {})}
    path = tmp_path / "probe.graph.yaml"
    path.write_text(yaml.safe_dump(doc, sort_keys=False))
    if errors:
        (tmp_path / "graflang.errors.yaml").write_text(yaml.safe_dump(
            {"errors": [{"code": c, "description": n, "cause": "probe", "remedy": "probe"} for n, c in errors]}))
    return path


# ── prompt filling ────────────────────────────────────────────────────────────────────────────────────────────────────

def test_a_value_that_contains_a_placeholder_is_not_expanded_again():
    prompt = "A=[{{in_a}}] B=[{{in_b}}]"
    assert fill_prompt(prompt, {"in_a": "has {{in_b}}", "in_b": "has {{in_a}}"}) == "A=[has {{in_b}}] B=[has {{in_a}}]"
    assert fill_prompt(prompt, {"in_b": "has {{in_a}}", "in_a": "x"}) == "A=[x] B=[has {{in_a}}]"      # order no longer matters


def test_unknown_placeholders_and_templates_stay():
    assert fill_prompt("{{in_x}} {{ todo.title }} {{in_y}}", {"in_y": None}) == "{{in_x}} {{ todo.title }} "


def test_the_rendered_prompt_in_a_run(tmp_path):
    model = Model()
    path = recipe(tmp_path, [{"g": {"generate": "A={{in_a}} B={{in_b}}", "in": {"a": "$in.a", "b": "$in.b"}, "out": "result"}},
                             {"done": {"output": "g"}}], inputs=("a", "b"))
    run_recipe(path, {"a": "{{in_b}}", "b": "two"}, llm=model)
    assert model.calls[0][0] == "A={{in_b}} B=two"


# ── output budget ─────────────────────────────────────────────────────────────────────────────────────────────────────

def test_a_generate_can_set_max_tokens_and_the_run_a_default(tmp_path):
    model = Model()
    path = recipe(tmp_path, [{"a": {"generate": "one", "max_tokens": 300, "out": "result"}},
                             {"b": {"generate": "two", "out": "result"}},
                             {"done": {"output": "b"}}])
    run_recipe(path, {}, llm=model, max_tokens=16000)
    assert [o.get("max_tokens") for _, o in model.calls] == [300, 16000]
    model.calls.clear()
    run_recipe(path, {}, llm=model)
    assert [o.get("max_tokens") for _, o in model.calls] == [300, None]


def test_defaults_llm_keeps_what_a_call_sets():
    model = Model()
    DefaultsLLM(model, max_tokens=10, temperature=None).generate("p", max_tokens=5)
    DefaultsLLM(model, max_tokens=10).generate("p")
    assert [o["max_tokens"] for _, o in model.calls] == [5, 10] and "temperature" not in model.calls[0][1]


# ── adapter options ───────────────────────────────────────────────────────────────────────────────────────────────────

def test_adapter_options_reach_every_dd_llm_adapter(monkeypatch):
    made = []
    mod = types.ModuleType("dd_llm")
    mod.get_adapter = lambda name, **kw: made.append((name, kw)) or object()
    monkeypatch.setitem(sys.modules, "dd_llm", mod)
    llm = make_llm("claude_cli", None, timeout=900)
    llm._get_adapter("ollama")
    assert made == [("claude_cli", {"timeout": 900}), ("ollama", {"timeout": 900})]
    assert make_llm("mock", None, timeout=900).name == "mock"


# ── python3 ───────────────────────────────────────────────────────────────────────────────────────────────────────────

def test_python3_is_the_running_interpreter():
    assert own_python(["python3", "-I", "x.py"]) == [sys.executable, "-I", "x.py"]
    assert own_python(["python", "x.py"])[0] == sys.executable
    assert own_python(["node", "x.js"]) == ["node", "x.js"]


def test_a_solve_step_runs_in_this_python(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", "/usr/bin:/bin")                 # a python3 here (if any) is not this one
    path = recipe(tmp_path, [{"which": {"node": "SOLVE", "ports": ["trigger", "complete", "out_result"], "out": "result",
                                        "backend": "subprocess", "out_type": "JSON",
                                        "command": ["python3", "-c", "import json, sys; print(json.dumps({'exe': sys.executable}))"]}},
                             {"done": {"output": "which"}}])
    assert run_recipe(path, {}).outputs["result"]["exe"] == sys.executable


# ── exits, errors, loading once ───────────────────────────────────────────────────────────────────────────────────────

EXITS = [{"check": {"evaluate": "@in_text == 'bad'", "in": {"text": "$in.text"}}},
         {"why": {"solve": "'refused: ' + @in_text", "on": "check.pass", "in": {"text": "$in.text"}, "out": "result"}},
         {"refused": {"output": {"result": "why.result"}, "on": "why", "exit": "refused"}},
         {"fine": {"solve": "'fine'", "on": "check.fail", "out": "result"}},
         {"done": {"output": {"result": "fine.result"}, "on": "fine"}}]


def test_the_exit_a_run_ended_at(tmp_path):
    path = recipe(tmp_path, EXITS, errors=[("refused", "E_REFUSED")])
    good = run_recipe(path, {"text": "ok"})
    assert (good.outputs, good.exit, good.error_code) == ({"result": "fine"}, None, None)
    bad = run_recipe(path, {"text": "bad"})
    assert (bad.outputs, bad.exit, bad.error_code) == ({"result": "refused: bad"}, "refused", "E_REFUSED")


def test_load_once_run_many(tmp_path):
    rec = Recipe(recipe(tmp_path, EXITS, errors=[("refused", "E_REFUSED")]))
    assert [rec.run({"text": t}).exit for t in ("bad", "ok", "bad")] == ["refused", None, "refused"]
    assert rec.name == "probe" and len(rec.fingerprint()) == 16
    before = rec.fingerprint()
    (tmp_path / "notes.md").write_text("changed")
    assert Recipe(rec.path).fingerprint() != before


def test_limits_raise_recipe_error_with_the_summary(tmp_path):
    path = recipe(tmp_path, [{"a": {"generate": "one", "out": "result"}}, {"b": {"generate": "two", "out": "result"}},
                             {"done": {"output": "b"}}])
    with pytest.raises(RecipeError) as e:
        run_recipe(path, {}, llm=Model(), max_llm_calls=1)
    assert "max_llm_calls" in str(e.value) and e.value.summary["llm"]["calls"] == 1


class BackendLimit(RuntimeError):
    pass


def test_passthrough_errors_are_raised_as_they_are(tmp_path):
    def boom(prompt):
        raise BackendLimit("quota")
    path = recipe(tmp_path, [{"a": {"generate": "one", "out": "result"}}, {"done": {"output": "a"}}])
    with pytest.raises(RecipeError):
        run_recipe(path, {}, llm=Model(boom))
    with pytest.raises(BackendLimit):
        run_recipe(path, {}, llm=Model(boom), passthrough=(BackendLimit,))


def test_bindings_replace_a_prompt_without_loading_again(tmp_path):
    (tmp_path / "p.md").write_text("shipped {{in_text}}")
    (tmp_path / "mine.md").write_text("mine {{in_text}}")
    path = recipe(tmp_path, [{"g": {"generate": "prompts.p", "in": {"text": "$in.text"}, "out": "result"}}, {"done": {"output": "g"}}],
                  extra={"resources": {"prompts": {"p": "./p.md"}}})
    rec = Recipe(path)
    model = Model()
    rec.with_bindings({"resources": {"prompts": {"p": str(tmp_path / "mine.md")}}}).run({"text": "x"}, llm=model)
    rec.run({"text": "y"}, llm=model)
    assert [p for p, _ in model.calls] == ["mine x", "shipped y"]


def test_a_missing_recipe(tmp_path):
    with pytest.raises(RecipeError):
        Recipe(tmp_path / "nope.graph.yaml")


def test_nothing_is_written_beside_the_recipe(tmp_path):
    path = recipe(tmp_path, EXITS, errors=[("refused", "E_REFUSED")])
    before = sorted(p.name for p in tmp_path.iterdir())
    run_recipe(path, {"text": "ok"})
    assert sorted(p.name for p in tmp_path.iterdir()) == before
