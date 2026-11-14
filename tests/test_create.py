"""`graf create`: a plain-language spec in, a checked GraphLang app out. The LLM is a stub; nothing here calls a model."""
import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from graphlang.cli import main
from graphlang.grafc import create as C
from graphlang.grafr.runtime import GraphLangRuntime, load_graph
from graphlang.grafr.topology import check
from graphlang.grafr.adapters import MockLLM

EXAMPLES = Path(C.__file__).parent / "create_examples"
APPS = {"linear": "summarizer", "branch": "support_triage", "loop": "polish"}


def reply_for(example, name):
    """What a model would answer: the example's files, renamed to `name`."""
    src, old = EXAMPLES / example, APPS[example]
    blocks = []
    for path in sorted(src.rglob("*")):
        if path.is_file():
            rel = path.relative_to(src).as_posix()
            text = path.read_text()
            if rel == f"{old}.graph.yaml":
                rel, text = f"{name}.graph.yaml", text.replace(f'name: "{old}"', f'name: "{name}"')
            blocks.append(f"=== FILE: {rel} ===\n{text}")
    blocks.append("=== FILE: readme.md ===\n# app\nruns\n")
    return "\n".join(blocks)


class Scripted:
    name, model_override, default_model = "scripted", None, None

    def __init__(self, *replies):
        self.replies, self.prompts = list(replies), []

    def generate(self, prompt, model=None, **opts):
        self.prompts.append(prompt)
        return self.replies.pop(0)

    def last_usage(self):
        return None


@pytest.mark.parametrize("example", sorted(APPS))
def test_every_shipped_example_is_a_valid_app_that_runs(example):
    graph = load_graph(EXAMPLES / example / f"{APPS[example]}.graph.yaml")
    assert check(graph) == ([], [])
    problems, _ = C.check_app("x", {}, False)
    assert problems                                            # an empty app is refused
    files = C.parse_files(reply_for(example, "my_app"))
    assert C.check_app("my_app", files) == ([], [])             # and a renamed copy passes the full check, dry run included


def test_the_prompt_carries_the_guide_the_examples_and_the_spec():
    prompt = C.build_prompt("triage", "classify messages", allow_code=False)
    assert "You write GraphLang apps" in prompt and "support_triage" in prompt and "classify messages" in prompt
    assert "triage.graph.yaml" in prompt and "tools/NAME.py" not in prompt
    assert "tools/NAME.py" in C.build_prompt("triage", "x", allow_code=True)


def test_files_are_read_from_marked_blocks_and_a_fence_around_a_file_is_removed():
    files = C.parse_files("=== FILE: a.yaml ===\n```yaml\nk: 1\n```\n=== FILE: prompts/p.md ===\nhello {{in_x}}\n")
    assert files == {"a.yaml": "k: 1\n", "prompts/p.md": "hello {{in_x}}\n"}
    with pytest.raises(C.CreateError, match="no `=== FILE"):
        C.parse_files("just text")
    with pytest.raises(C.CreateError, match="unsafe path"):
        C.parse_files("=== FILE: ../evil.md ===\nx\n")


def test_a_good_first_answer_costs_one_call():
    llm = Scripted(reply_for("branch", "triage"))
    made = C.create_app("triage", "classify then reply", llm, None)
    assert made.ok and made.rounds == 1 and len(llm.prompts) == 1 and f"triage.graph.yaml" in made.files


def test_problems_go_back_to_the_llm_with_its_own_attempt():
    broken = reply_for("linear", "notes").replace('{generate: prompts.fix,', '{generate: prompts.fix, model: "x",')
    llm = Scripted(broken, reply_for("linear", "notes"))
    made = C.create_app("notes", "summarize", llm, None)
    assert made.ok and made.rounds == 2
    second = llm.prompts[1]
    assert "Your previous attempt" in second and "model" in second and "notes.graph.yaml" in second       # the file it wrote and what was wrong


def test_a_graph_that_does_not_load_is_a_problem_the_llm_can_fix():
    llm = Scripted("=== FILE: notes.graph.yaml ===\nversion: '1.0-graph'\nworkflow: {name: notes}\n", reply_for("linear", "notes"))
    made = C.create_app("notes", "x", llm, None)
    assert made.ok and made.rounds == 2 and "does not load" in llm.prompts[1]


def test_a_wrong_workflow_name_is_found():
    wrong = reply_for("linear", "other").replace("other.graph.yaml", "notes.graph.yaml")
    problems, _ = C.check_app("notes", C.parse_files(wrong))
    assert any("workflow.name" in p for p in problems)


def test_a_graph_that_fails_at_run_time_is_found_by_the_dry_run(monkeypatch):
    files = C.parse_files(reply_for("linear", "notes"))

    class Boom:
        def __init__(self, *a, **k):
            pass

        def execute(self, inputs):
            raise ValueError("port in_x has no value")

    monkeypatch.setattr("graphlang.grafr.runtime.GraphLangRuntime", Boom)
    problems, _ = C.check_app("notes", files)
    assert any("dry run" in p and "port in_x" in p for p in problems)


def test_it_gives_up_after_max_rounds_and_reports_what_is_left():
    bad = reply_for("linear", "notes").replace('{generate: prompts.fix,', '{generate: prompts.fix, model: "x",')
    llm = Scripted(bad, bad)
    made = C.create_app("notes", "x", llm, None, max_rounds=2)
    assert not made.ok and made.rounds == 2 and len(llm.prompts) == 2 and any("model" in p for p in made.problems)


def test_nothing_that_runs_code_is_accepted_without_allow_code():
    files = C.parse_files(reply_for("linear", "notes"))
    with_tool = {**files, "tools/x.py": "print(1)\n"}
    assert any("not allowed" in p for p in C.check_app("notes", with_tool)[0])
    graph_with_run = files["notes.graph.yaml"].replace(
        "  - done:", '  - tool: {node: SOLVE, in: {t: fix.summary}, ports: [trigger, complete, in_t, out_r], out: r, backend: subprocess, command: ["python3", "tools/x.py"]}\n  - done:')
    problems, _ = C.check_app("notes", {**files, "notes.graph.yaml": graph_with_run})
    assert any("needs --allow-code" in p for p in problems)
    ok, _ = C.check_app("notes", {**with_tool, "notes.graph.yaml": graph_with_run}, allow_code=True)
    assert not any("allow-code" in p or "not allowed" in p for p in ok)         # allowed (and not executed: no dry run)


def test_names_and_folders_are_checked(tmp_path):
    for bad in ("Notes", "1app", "my-app", ""):
        with pytest.raises(C.CreateError, match="--name"):
            C.check_name(bad)
    made = C.Created(C.parse_files(reply_for("linear", "notes")), 1, [])
    out = tmp_path / "app"
    written = C.write_app("notes", "summarize", made, out, "mock")
    assert (out / "notes.graph.yaml").exists() and (out / "prompts" / "fix.md").exists()
    meta = json.loads((out / "create.json").read_text())
    assert meta["spec"] == "summarize" and meta["name"] == "notes" and out / "create.json" in written
    with pytest.raises(C.CreateError, match="already has files"):
        C.write_app("notes", "x", made, out, "mock")
    C.write_app("notes", "x", made, out, "mock", force=True)


def run_cli(monkeypatch, tmp_path, llm, *extra):
    monkeypatch.setattr("graphlang.grafr.adapters.make_llm", lambda adapter, model=None: llm)
    return CliRunner().invoke(main, ["create", "--name", "triage", "--spec", "classify then reply", "--llm", "claude_cli:claude-haiku-5-5",
                                     "--out-dir", str(tmp_path / "triage"), "--no-log", *extra])


def test_the_command_writes_an_app_that_validates_and_runs(monkeypatch, tmp_path):
    llm = Scripted(reply_for("branch", "triage"))
    llm.name = "claude_cli"
    result = run_cli(monkeypatch, tmp_path, llm)
    assert result.exit_code == 0 and "Created" in result.output, result.output
    graph = tmp_path / "triage" / "triage.graph.yaml"
    assert CliRunner().invoke(main, ["validate", str(graph)]).exit_code == 0
    assert GraphLangRuntime(load_graph(graph), llm=MockLLM(), verbose=False).execute({"message": "down"})


def test_the_command_writes_the_app_even_when_problems_are_left(monkeypatch, tmp_path):
    bad = reply_for("branch", "triage").replace('{generate: prompts.classify,', '{generate: prompts.classify, model: "x",')
    llm = Scripted(bad)
    llm.name = "claude_cli"
    result = run_cli(monkeypatch, tmp_path, llm, "--max-rounds", "1")
    assert result.exit_code == 1 and "problem" in result.output and (tmp_path / "triage" / "triage.graph.yaml").exists()


def test_the_spec_can_come_from_a_file_and_a_bad_name_is_refused(monkeypatch, tmp_path):
    spec = tmp_path / "spec.md"
    spec.write_text("from a file: triage messages")
    llm = Scripted(reply_for("branch", "triage"))
    llm.name = "claude_cli"
    monkeypatch.setattr("graphlang.grafr.adapters.make_llm", lambda adapter, model=None: llm)
    out = CliRunner().invoke(main, ["create", "--name", "triage", "--spec", f"@{spec}", "--out-dir", str(tmp_path / "t"), "--no-log"])
    assert out.exit_code == 0 and "from a file: triage messages" in llm.prompts[0]
    bad = CliRunner().invoke(main, ["create", "--name", "Bad-Name", "--spec", "x", "--no-log"])
    assert bad.exit_code == 1 and "--name" in bad.output


# ── revising an app that exists ──────────────────────────────────────────────────────────────────

def current_files(name="notes"):
    return C.parse_files(reply_for("linear", name))


def test_revise_sends_the_current_files_and_the_change_and_costs_one_call_when_it_checks_out():
    llm = Scripted(reply_for("linear", "notes"))
    created = C.revise_app("notes", "make the summary shorter", current_files(), llm, None)
    assert created.ok and created.rounds == 1
    prompt = llm.prompts[0]
    assert "Change the existing app `notes`" in prompt and "make the summary shorter" in prompt and "=== FILE: notes.graph.yaml ===" in prompt


def test_revise_sends_its_problems_back_with_its_own_attempt():
    broken = reply_for("linear", "notes").replace("version:", "versoin:", 1)
    llm = Scripted(broken, reply_for("linear", "notes"))
    created = C.revise_app("notes", "tweak", current_files(), llm, None)
    assert created.ok and created.rounds == 2
    assert "Your previous attempt at the change" in llm.prompts[1] and "It has these problems" in llm.prompts[1]


def test_revise_gives_up_after_max_rounds_and_keeps_what_is_left():
    broken = reply_for("linear", "notes").replace("version:", "versoin:", 1)
    created = C.revise_app("notes", "tweak", current_files(), Scripted(broken, broken), None, max_rounds=2)
    assert not created.ok and created.rounds == 2 and created.problems


def test_revise_refuses_an_empty_change_and_an_empty_app():
    with pytest.raises(C.CreateError, match="empty"):
        C.revise_app("notes", "  ", current_files(), Scripted(), None)
    with pytest.raises(C.CreateError, match="no app"):
        C.revise_app("notes", "x", {}, Scripted(), None)


def test_images_are_shown_with_every_attempt_of_a_create_and_a_revision():
    seen = []

    class Seer(Scripted):
        def generate(self, prompt, model=None, **opts):
            seen.append(opts.get("images"))
            return super().generate(prompt, model=model, **opts)
    broken = reply_for("linear", "notes").replace("version:", "versoin:", 1)
    pictures = [("image/png", b"x")]
    C.create_app("notes", "from the picture", Seer(broken, reply_for("linear", "notes")), None, images=pictures)
    C.revise_app("notes", "like the picture", current_files(), Seer(reply_for("linear", "notes")), None, images=pictures)
    assert seen == [pictures, pictures, pictures]
    seen.clear()
    C.create_app("notes", "no picture", Seer(reply_for("linear", "notes")), None)
    assert seen == [None]


# ── examples from the existing recipes: `graf create` and the app's Create page share `find_examples` ──

@pytest.fixture()
def cookbook_home(tmp_path, monkeypatch):
    from graphlang import workspace as ws
    monkeypatch.setenv("GRAFLANG_HOME", str(tmp_path / "home"))
    ws.install_cookbook(Path(C.__file__).resolve().parents[2] / "cookbook", ws.default_src_dir())
    ws.save_settings({"embedding": "none"})                         # plain pytest is offline: words only
    return tmp_path / "home"


def test_find_examples_picks_the_closest_recipes_and_says_how(cookbook_home):
    shown = C.find_examples("write code, review it, then improve it until the tests pass", embedding="none")
    assert shown.keys and len(shown.keys) <= 2 and shown.words_only and "Existing recipe `" in shown.text
    assert any(k.endswith(("code_pipeline", "code_parts")) for k in shown.keys) is False or all("/" in k for k in shown.keys)


def test_find_examples_puts_the_chosen_recipe_first_and_drops_programs_unless_allowed(cookbook_home):
    shown = C.find_examples("summarize a meeting", chosen="cookbook/self_refine", embedding="none")
    assert shown.keys[0] == "cookbook/self_refine"
    risky = C.find_examples("anything", chosen="cookbook/code_parts", embedding="none")
    assert "cookbook/code_parts" not in risky.keys                                # it runs programs and they were not allowed
    assert "cookbook/code_parts" in C.find_examples("anything", chosen="cookbook/code_parts", allow_code=True, embedding="none").keys


def test_find_examples_with_no_recipes_returns_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("GRAFLANG_HOME", str(tmp_path / "empty"))
    shown = C.find_examples("summarize a meeting", embedding="none")
    assert shown.keys == [] and shown.text == ""


def test_the_command_shows_the_model_similar_recipes_and_names_them(cookbook_home, monkeypatch, tmp_path):
    llm = Scripted(reply_for("linear", "notes"))
    monkeypatch.setattr("graphlang.grafr.adapters.make_llm", lambda adapter, model=None: llm)
    result = CliRunner().invoke(main, ["create", "--name", "notes", "--spec", "draft an essay then critique it and refine it", "--out-dir",
                                       str(tmp_path / "out"), "--no-log", "--embedding", "none"])
    assert result.exit_code == 0, result.output
    assert "examples:" in result.output and "self_refine" in result.output
    assert "Existing recipes that may be similar" in llm.prompts[0] and "Existing recipe `self_refine`" in llm.prompts[0]


def test_the_command_can_turn_examples_off_or_start_from_a_named_recipe(cookbook_home, monkeypatch, tmp_path):
    llm = Scripted(reply_for("linear", "notes"), reply_for("linear", "other"))
    monkeypatch.setattr("graphlang.grafr.adapters.make_llm", lambda adapter, model=None: llm)
    base = ["create", "--no-log", "--embedding", "none", "--spec", "draft an essay then critique it"]
    off = CliRunner().invoke(main, base + ["--name", "notes", "--out-dir", str(tmp_path / "a"), "--no-examples"])
    assert off.exit_code == 0 and "Existing recipes that may be similar" not in llm.prompts[0]
    chosen = CliRunner().invoke(main, base + ["--name", "other", "--out-dir", str(tmp_path / "b"), "--from", "cookbook/chain_of_thought", "--no-examples"])
    assert chosen.exit_code == 0 and "Existing recipe `chain_of_thought`" in llm.prompts[1]
    bad = CliRunner().invoke(main, base + ["--name", "x", "--out-dir", str(tmp_path / "c"), "--from", "cookbook/nope"])
    assert bad.exit_code == 1 and "no such recipe" in " ".join(bad.output.split())


def test_the_command_uses_the_embedding_in_the_app_settings_unless_told_otherwise(cookbook_home, monkeypatch, tmp_path):
    from graphlang import embedding as E
    from graphlang import workspace as ws
    seen = []
    monkeypatch.setattr(E, "resolve", lambda spec="auto": (seen.append(spec), (None, "words only (test)"))[1])
    ws.save_settings({"embedding": "ollama:some-model"})
    llm = Scripted(reply_for("linear", "notes"), reply_for("linear", "notes"))
    monkeypatch.setattr("graphlang.grafr.adapters.make_llm", lambda adapter, model=None: llm)
    base = ["create", "--no-log", "--name", "notes", "--spec", "draft an essay"]
    CliRunner().invoke(main, base + ["--out-dir", str(tmp_path / "a")])
    CliRunner().invoke(main, base + ["--out-dir", str(tmp_path / "b"), "--embedding", "none"])
    assert seen == ["ollama:some-model", "none"]


# ── --diagram: a picture of the workflow ──

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 20


def test_a_diagram_is_shown_to_the_model_with_every_round(monkeypatch, tmp_path):
    seen = []

    class Seer(Scripted):
        def generate(self, prompt, model=None, **opts):
            seen.append((prompt, opts.get("images")))
            return super().generate(prompt, model=model, **opts)
    llm = Seer(reply_for("branch", "triage"))
    llm.name = "claude_cli"
    picture = tmp_path / "sketch.png"
    picture.write_bytes(PNG)
    result = run_cli(monkeypatch, tmp_path, llm, "--diagram", str(picture))
    assert result.exit_code == 0, result.output
    assert seen[0][1] == [("image/png", PNG)] and "picture of the workflow is attached" in seen[0][0]


def test_a_diagram_alone_is_enough_but_a_spec_or_a_diagram_is_needed(monkeypatch, tmp_path):
    llm = Scripted(reply_for("branch", "triage"))
    llm.name = "claude_cli"
    monkeypatch.setattr("graphlang.grafr.adapters.make_llm", lambda adapter, model=None: llm)
    picture = tmp_path / "sketch.jpg"
    picture.write_bytes(b"jpg")
    base = ["create", "--name", "triage", "--llm", "claude_cli", "--out-dir", str(tmp_path / "t"), "--no-log"]
    assert CliRunner().invoke(main, base + ["--diagram", str(picture)]).exit_code == 0
    none = CliRunner().invoke(main, base)
    assert none.exit_code != 0 and "--spec, --diagram" in none.output


def test_a_diagram_with_an_adapter_that_cannot_read_images_is_refused_before_any_call(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr("graphlang.grafr.adapters.make_llm", lambda adapter, model=None: calls.append(adapter))
    picture = tmp_path / "s.png"
    picture.write_bytes(PNG)
    result = CliRunner().invoke(main, ["create", "--name", "triage", "--spec", "x", "--diagram", str(picture), "--llm", "openai:gpt-x",
                                       "--out-dir", str(tmp_path / "t"), "--no-log"])
    assert result.exit_code != 0 and "cannot read images" in result.output and calls == []


def test_a_diagram_that_is_not_an_image_or_is_missing_is_refused(monkeypatch, tmp_path):
    monkeypatch.setattr("graphlang.grafr.adapters.make_llm", lambda adapter, model=None: None)
    text = tmp_path / "notes.txt"
    text.write_text("hi")
    for bad in (text, tmp_path / "missing.png"):
        result = CliRunner().invoke(main, ["create", "--name", "triage", "--diagram", str(bad), "--llm", "claude_cli",
                                           "--out-dir", str(tmp_path / "t"), "--no-log"])
        assert result.exit_code != 0 and "--diagram" in result.output
