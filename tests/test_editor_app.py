"""The Streamlit editor, driven with Streamlit's own test harness. Needs `pip install 'graflang[edit]'`; skipped without it."""
import json
import shutil
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest

APP = Path(__file__).parent.parent / "graphlang" / "grafv" / "app.py"
SELF_REFINE = Path(__file__).parent.parent / "cookbook" / "self_refine"


@pytest.fixture
def at(tmp_path, monkeypatch):
    dest = tmp_path / "self_refine"
    shutil.copytree(SELF_REFINE, dest, ignore=shutil.ignore_patterns("output"))
    monkeypatch.setenv("GRAF_EDIT_FILE", str(dest / "self_refine.graph.yaml"))
    monkeypatch.setenv("GRAF_PLAIN_EDITOR", "1")                  # the Source tab's code editor is a component AppTest cannot drive
    app = AppTest.from_file(str(APP), default_timeout=30)
    app.run()
    assert not app.exception, app.exception
    app.file = dest / "self_refine.graph.yaml"
    return app


def button(app, key):
    return next(b for b in app.button if b.key == key)


def send(at, scope, text):
    """Type `text` in the chat box of `scope` ("create" or "edit") and press Send."""
    boxes = [w for tree in (at, at.sidebar) for w in tree.text_area if w.key == f"{scope}_text"]
    boxes[0].set_value(text)
    [b for tree in (at, at.sidebar) for b in tree.button if b.key == f"{scope}_send"][0].click().run()


def pick(app, node):
    app.selectbox(key="node_pick").select(node).run()


def test_it_opens_and_shows_a_valid_graph(at):
    assert at.sidebar.markdown[0].value.startswith("### self_refine.graph.yaml")
    assert button(at, "save").disabled                                    # nothing to save yet
    assert any("valid: no errors" in s.value for s in at.success)


def test_a_config_edit_is_saved_with_the_comments_kept(at):
    pick(at, "draft")
    at.text_area(key="cfg_draft_llm").set_value("ollama:llama3").run()
    button(at, "set_draft_llm").click().run()
    assert not at.exception and not button(at, "save").disabled
    button(at, "save").click().run()
    text = at.file.read_text()
    assert "ollama:llama3" in text and "# Control flow" in text and "# Data flow" in text


def test_an_invalid_edit_cannot_be_saved(at):
    pick(at, "draft")
    at.text_area(key="cfg_draft_prompt_ref").set_value("prompts.nope").run()
    button(at, "set_draft_prompt_ref").click().run()
    assert button(at, "save").disabled and at.error                        # the problem is listed, Save is off
    assert "prompts.nope" not in at.file.read_text()


def test_undo_restores_the_edit(at):
    pick(at, "draft")
    at.text_area(key="cfg_draft_llm").set_value("ollama:x").run()
    button(at, "set_draft_llm").click().run()
    button(at, "undo").click().run()
    assert button(at, "save").disabled and at.text_area(key="cfg_draft_llm").value == "ollama:gemma3"


def test_a_node_is_added_from_the_form_and_saved(at):
    at.text_input(key="new_id").set_value("polish")
    at.text_input(key="new_ports").set_value("trigger, complete, in_essay, out_essay")
    at.text_area(key="new_config").set_value("prompt_inline: Polish the essay")
    button(at, "add_node_submit").click().run()
    assert not at.exception
    pick(at, "polish")
    assert at.text_area(key="cfg_polish_prompt_inline").value == "Polish the essay"
    button(at, "save").click().run()                                       # unwired is only a warning, so it saves
    assert "polish" in at.file.read_text()


def test_a_node_can_be_removed(at):
    pick(at, "critique")
    button(at, "rm_critique").click().run()
    assert "critique" not in [o for o in at.selectbox(key="node_pick").options]


def test_the_run_tab_runs_the_graph_as_it_is_with_the_mock(at):
    at.selectbox(key="run_adapter").select("mock").run()
    at.text_input(key="run_in_topic").set_value("ducks").run()
    button(at, "run_go").click().run()
    assert not at.exception and any("steps" in s.value for s in at.success)
    assert any("essay" in m.value for m in at.markdown) or any("essay" in c.value for c in at.code)      # the Logs tab shows the result
    assert "Logs" in [t.label for t in at.tabs] and not at.json


def test_clone_makes_a_copy_and_edits_that_one_not_the_original(at):
    original = at.file.read_text()
    at.sidebar.text_input(key="clone_name").set_value("trial").run()
    button(at, "clone").click().run()
    assert not at.exception
    assert (at.file.parent / "trial.graph.yaml").read_text() == original
    assert at.sidebar.markdown[0].value == "### trial.graph.yaml"
    pick(at, "draft")
    at.text_area(key="cfg_draft_llm").set_value("ollama:llama3").run()
    button(at, "set_draft_llm").click().run()
    button(at, "save").click().run()
    assert "llama3" in (at.file.parent / "trial.graph.yaml").read_text() and at.file.read_text() == original   # only the copy changed
    button(at, "back").click().run()
    assert at.sidebar.markdown[0].value == "### self_refine.graph.yaml"


def test_clone_is_off_while_there_are_unsaved_edits(at):
    pick(at, "draft")
    at.text_area(key="cfg_draft_llm").set_value("ollama:llama3").run()
    button(at, "set_draft_llm").click().run()
    assert button(at, "clone").disabled


# ── the chat on the Edit page ────────────────────────────────────────────────────────────────────

def stub_chat(monkeypatch, *replies):
    from graphlang.grafv import ui
    replies = list(replies)
    prompts = []

    class Meter:
        def generate(self, prompt, model=None, **kw):
            prompts.append(prompt)
            return replies.pop(0)
    monkeypatch.setattr(ui, "new_llm", lambda max_calls: (Meter(), "scripted", None))
    return prompts


def test_a_chat_request_changes_the_graph_and_a_prompt_file_but_only_save_writes_them(at, monkeypatch):
    prompts = stub_chat(monkeypatch, json.dumps({"say": "Made the draft terser.", "ops": [
        {"op": "set_config", "node": "draft", "key": "llm", "value": "ollama:llama3"},
        {"op": "write_file", "path": "prompts/draft.md", "text": "Write ONE terse paragraph about {{in_topic}}."}]}))
    original_prompt = (at.file.parent / "prompts" / "draft.md").read_text()
    send(at, "edit", "make the draft terser")
    assert not at.exception, at.exception
    assert "make the draft terser" in prompts[0] and "prompts/draft.md" in prompts[0]
    assert not button(at, "save").disabled and "ollama:llama3" not in at.file.read_text()           # a proposal, not a save
    assert (at.file.parent / "prompts" / "draft.md").read_text() == original_prompt
    button(at, "save").click().run()
    assert "ollama:llama3" in at.file.read_text() and "# Control flow" in at.file.read_text()
    assert (at.file.parent / "prompts" / "draft.md").read_text() == "Write ONE terse paragraph about {{in_topic}}."


def test_a_chat_edit_can_be_undone_and_its_prompt_changes_discarded(at, monkeypatch):
    stub_chat(monkeypatch, json.dumps({"say": "ok", "ops": [
        {"op": "set_config", "node": "draft", "key": "llm", "value": "ollama:llama3"},
        {"op": "write_file", "path": "prompts/draft.md", "text": "NEW"}]}))
    send(at, "edit", "change things")
    button(at, "undo").click().run()
    button(at, "discard_staged").click().run()
    assert button(at, "save").disabled and not at.session_state[f"staged_{at.session_state['file']}"]


def test_a_chat_reply_that_cannot_be_applied_changes_nothing_and_says_why(at, monkeypatch):
    stub_chat(monkeypatch, json.dumps({"say": "x", "ops": [
        {"op": "set_config", "node": "draft", "key": "llm", "value": "a:b"}, {"op": "remove_node", "id": "no_such_node"}]}))
    send(at, "edit", "do it")
    assert not at.exception and button(at, "save").disabled
    assert any("could not apply" in m["content"] for m in at.session_state[f"chat_edit_{at.session_state['file']}"])


def test_a_chat_reply_that_is_not_json_is_reported_not_crashed(at, monkeypatch):
    stub_chat(monkeypatch, "Sure, I will make it better!")
    send(at, "edit", "improve")
    assert not at.exception and any("JSON" in m["content"] for m in at.session_state[f"chat_edit_{at.session_state['file']}"])


def test_a_prompt_written_as_a_block_shows_as_text_and_is_written_back_as_a_block(tmp_path, monkeypatch):
    folder = tmp_path / "cot"
    shutil.copytree(Path(__file__).parent.parent / "cookbook" / "chain_of_thought", folder, ignore=shutil.ignore_patterns("output"))
    graph = next(folder.glob("*.graph.yaml"))
    before = graph.read_text()
    assert "|-" in before                                              # the recipe's prompts are block scalars
    monkeypatch.setenv("GRAF_EDIT_FILE", str(graph))
    app = AppTest.from_file(str(APP), default_timeout=30)
    app.run()
    assert not app.exception, app.exception                            # this used to be a RepresenterError
    node = next(n for n in app.session_state["editor"].node_ids() if n.startswith("gen"))
    pick(app, node)
    assert not app.exception, app.exception
    area = next(a for a in app.text_area if a.key and a.key.startswith(f"cfg_{node}_prompt"))
    assert "\n" in area.value and not area.value.startswith("|")       # the prompt itself, not quoted YAML
    area.set_value(area.value + "\nBe brief.").run()
    next(b for b in app.button if b.key and b.key.startswith(f"set_{node}_prompt")).click().run()
    button(app, "save").click().run()
    after = graph.read_text()
    assert "Be brief." in after and after.count("|-") >= before.count("|-")


def test_the_sidebar_shows_the_graph_the_editor_or_both_never_neither(at):
    assert at.sidebar.toggle(key="show_graph").value is True and at.sidebar.toggle(key="show_panel").value is True
    assert at.selectbox(key="node_pick") and at.tabs
    at.sidebar.toggle(key="show_panel").set_value(False).run()                      # the graph alone: the whole width
    assert not at.exception and not at.tabs and not [s for s in at.selectbox if s.key == "node_pick"]
    at.sidebar.toggle(key="show_panel").set_value(True).run()
    at.sidebar.toggle(key="show_graph").set_value(False).run()                      # the editor alone
    assert not at.exception and at.tabs and at.selectbox(key="node_pick")
    at.sidebar.toggle(key="show_panel").set_value(False).run()                      # neither: the graph comes back
    assert not at.exception and at.toggle(key="show_graph").value is True and not at.tabs


# ── the Source tab and the file browser ──────────────────────────────────────────────────────────

def test_the_source_tab_shows_the_file_and_apply_brings_typed_changes_into_the_editor(at):
    box = at.text_area(key="source_text")
    assert box.value == at.file.read_text()
    assert button(at, "source_apply").disabled
    box.set_value(box.value.replace("# Control flow", "# Control flow (hand edit)")).run()
    assert not button(at, "source_apply").disabled and "hand edit" not in at.file.read_text()
    button(at, "source_apply").click().run()
    assert not at.exception and not button(at, "save").disabled
    assert "hand edit" in at.text_area(key="source_text").value                              # the box shows the applied text
    button(at, "save").click().run()
    assert "hand edit" in at.file.read_text()


def test_the_source_tab_reports_bad_yaml_and_keeps_the_graph(at):
    at.text_area(key="source_text").set_value("a: [").run()
    button(at, "source_apply").click().run()
    assert not at.exception and any("not valid YAML" in e.value for e in at.error) and button(at, "save").disabled


def test_the_source_tab_follows_other_edits_and_undo(at):
    pick(at, "draft")
    at.text_area(key="cfg_draft_llm").set_value("ollama:llama3").run()
    button(at, "set_draft_llm").click().run()
    assert "ollama:llama3" in at.text_area(key="source_text").value
    button(at, "undo").click().run()
    assert "ollama:llama3" not in at.text_area(key="source_text").value


def test_a_typed_but_unapplied_source_can_be_reverted(at):
    at.text_area(key="source_text").set_value("anything").run()
    button(at, "source_revert").click().run()
    assert at.text_area(key="source_text").value == at.file.read_text()


def test_the_file_browser_lists_graphs_in_sub_folders_and_opens_one(tmp_path, monkeypatch):
    folder = tmp_path / "ed"
    shutil.copytree(Path(__file__).parent.parent / "cookbook" / "expand_demo", folder, ignore=shutil.ignore_patterns("output"))
    monkeypatch.setenv("GRAF_EDIT_FILE", str(folder / "sub_graph" / "explain.graph.yaml"))
    app = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not app.exception, app.exception
    assert app.sidebar.markdown[0].value == "### explain.graph.yaml"
    files = app.sidebar.selectbox(key="open_file")
    assert "sub_graph/explain.graph.yaml" in files.options and any(o.endswith("expand_demo.graph.yaml") for o in files.options)
    app.sidebar.selectbox(key="open_file").select(next(o for o in files.options if o.endswith("expand_demo.graph.yaml"))).run()
    next(b for b in app.sidebar.button if b.key == "open_go").click().run()
    assert not app.exception


def test_the_source_tab_renders_with_the_code_editor_when_it_is_installed(tmp_path, monkeypatch):
    pytest.importorskip("streamlit_ace")
    folder = tmp_path / "sr"
    shutil.copytree(SELF_REFINE, folder, ignore=shutil.ignore_patterns("output"))
    monkeypatch.setenv("GRAF_EDIT_FILE", str(folder / "self_refine.graph.yaml"))
    monkeypatch.delenv("GRAF_PLAIN_EDITOR", raising=False)
    app = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not app.exception, app.exception                                # st_ace accepted the arguments the page gives it
    assert not [t for t in app.text_area if t.key == "source_text"]        # the box was replaced by the component


# ── regressions found in the review of the app (docs/DEV/DESIGN/graflang-UI.md) ──────────────────────────────

def edit_page_module():
    import importlib.util
    path = Path(__file__).parent.parent / "graphlang" / "grafv" / "pages" / "02-edit.py"
    spec = importlib.util.spec_from_file_location("edit_page", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_invalid_yaml_typed_in_a_box_is_an_edit_error_not_a_parser_crash():
    from graphlang.grafv.editor import EditError
    module = edit_page_module()
    with pytest.raises(EditError, match="not valid YAML"):
        module.parse_value("[a, b")
    with pytest.raises(EditError, match="not valid YAML"):
        module.new_value(3, "{x: ")                                    # a value that is not text is read as YAML too
    assert module.parse_value("[a, b]") == ["a", "b"] and module.parse_value("  ") is None


def test_a_yaml_typo_in_the_add_node_form_shows_an_error_and_keeps_the_page(at):
    at.text_input(key="new_id").set_value("polish2")
    at.text_area(key="new_config").set_value("[a, b")
    next(b for b in at.button if b.key == "add_node_submit").click().run()
    assert not at.exception, at.exception
    assert any("not valid YAML" in e.value for e in at.error)
    assert "polish2" not in at.selectbox(key="node_pick").options


def test_a_real_model_run_is_capped_in_calls(at, monkeypatch):
    calls = []

    class Stub:
        name = adapter_name = "stub"

        def generate(self, prompt, model=None, **opts):
            calls.append(prompt)
            return "text"
    monkeypatch.setattr("graphlang.grafr.adapters.make_llm", lambda adapter, model=None: Stub())
    assert at.selectbox(key="run_adapter").value != "mock"                    # the real model is the default
    assert at.number_input(key="run_max_calls").value == 10                  # a real model always runs under a cap
    at.number_input(key="run_max_calls").set_value(1).run()
    at.text_input(key="run_in_topic").set_value("ducks").run()
    button(at, "run_go").click().run()
    assert not at.exception and len(calls) == 1
    assert any("LimitExceeded" in e.value for e in at.error), [e.value for e in at.error]


def test_the_mock_run_has_no_cap_box(at):
    at.selectbox(key="run_adapter").select("mock").run()
    assert not [n for n in at.number_input if n.key == "run_max_calls"]


def test_the_edge_lists_follow_the_type_at_once(at):
    assert "edge_kind" in {r.key for r in at.radio}                           # outside the form, so the lists below follow it
    at.radio(key="edge_kind").set_value("binds").run()
    sources = next(s for s in at.selectbox if s.label == "From").options
    assert sources and all(o.partition(".")[2].startswith("out_") for o in sources)


def test_opening_or_reloading_is_off_while_there_are_unsaved_edits(at):
    pick(at, "draft")
    assert not button(at, "open_go").disabled and not button(at, "reload").disabled
    at.text_area(key="cfg_draft_llm").set_value("ollama:llama3").run()
    button(at, "set_draft_llm").click().run()
    assert button(at, "open_go").disabled and button(at, "reload").disabled          # an edit is unsaved: nothing may drop it
    button(at, "save").click().run()
    assert not button(at, "open_go").disabled and not button(at, "reload").disabled


def test_running_a_graph_with_a_program_needs_an_acknowledgement(at):
    at.session_state["editor"].add_node("shell", "RUN", ["trigger", "complete"], {"executor": "python", "code": "print(1)"})
    at.run()
    assert not at.exception, at.exception
    assert any("runs programs on your computer" in w.value and "shell" in w.value for w in at.warning)
    assert at.checkbox(key="run_ack_code").value and not button(at, "run_go").disabled      # ticked by default
    at.checkbox(key="run_ack_code").uncheck().run()
    assert button(at, "run_go").disabled


def test_a_graph_without_programs_runs_without_the_acknowledgement(at):
    assert not [c for c in at.checkbox if c.key == "run_ack_code"] and not button(at, "run_go").disabled


def test_the_dry_run_is_not_called_mock_in_the_page(at):
    assert at.selectbox(key="run_adapter").options[1] == "dry run: placeholder answers, no model"


def test_the_node_dropdown_shows_the_pictures_labels_and_keeps_the_ids_as_values(at):
    from graphlang.grafv.model import display_label
    nodes = at.session_state["editor"].data()["nodes"]
    labels = [display_label(n) for n in nodes]
    assert at.selectbox(key="node_pick").options == [l if labels.count(l) == 1 else f"{l} ({n['id']})" for l, n in zip(labels, nodes)]
    pick(at, "draft")                                                   # selecting still works by id: the values are ids
    assert any(c.value.startswith("id **draft**") for c in at.caption)


def test_two_nodes_with_the_same_label_are_told_apart_by_their_id():
    module = edit_page_module()

    class Fake:
        def data(self):
            return {"nodes": [{"id": "a", "type": "GENERATE", "config": {"function": "analyze"}},
                              {"id": "b", "type": "GENERATE", "config": {"function": "analyze"}},
                              {"id": "c", "type": "INPUT", "config": {}}]}
    assert module.node_labels(Fake()) == {"a": "analyze (a)", "b": "analyze (b)", "c": "c"}


def test_a_real_run_is_saved_and_the_logs_tab_lists_past_runs(at, monkeypatch):
    from graphlang.grafv import runs
    from graphlang.grafv.editor import GraphEditor
    editor = GraphEditor(at.file)
    result = editor.run({"topic": "ducks"}, adapter="mock", save=True)             # `save` is what the Run tab passes for a real model
    assert result["ok"]
    [folder] = runs.run_folders(at.file)
    loaded = runs.load_run(folder)
    assert loaded["ok"] and loaded["inputs"] == {"topic": "ducks"} and loaded["outputs"] == result["outputs"]
    assert loaded["summary"]["steps"] == result["summary"]["steps"] and loaded["values"]
    assert "mock" in runs.label(folder)
    at.run()
    box = next(s for s in at.selectbox if s.key == "logs_pick")
    assert len(box.options) == 1 and "mock" in box.options[0]
    assert any("essay" in m.value for m in at.markdown) or any("essay" in c.value for c in at.code)


def test_a_failed_saved_run_is_listed_with_its_reason(at):
    from graphlang.grafv import runs
    from graphlang.grafv.editor import GraphEditor
    result = GraphEditor(at.file).run({"topic": "x"}, adapter="mock", max_steps=1, save=True)
    assert not result["ok"]
    [folder] = runs.run_folders(at.file)
    loaded = runs.load_run(folder)
    assert not loaded["ok"] and loaded["error"] and "failed" in runs.label(folder)
