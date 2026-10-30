"""The Streamlit editor, driven with Streamlit's own test harness. Needs `pip install 'graflang[edit]'`; skipped without it."""
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
    app = AppTest.from_file(str(APP), default_timeout=30)
    app.run()
    assert not app.exception, app.exception
    app.file = dest / "self_refine.graph.yaml"
    return app


def button(app, key):
    return next(b for b in app.button if b.key == key)


def pick(app, node):
    app.selectbox(key="node_pick").select(node).run()


def test_it_opens_and_shows_a_valid_graph(at):
    assert at.sidebar.markdown[0].value.startswith("### self_refine.graph.yaml")
    assert button(at, "save").disabled                                    # nothing to save yet
    assert any("valid: no errors" in s.value for s in at.success)


def test_a_config_edit_is_saved_with_the_comments_kept(at):
    pick(at, "draft")
    at.text_area(key="cfg_draft_model").set_value("ollama/llama3").run()
    button(at, "set_draft_model").click().run()
    assert not at.exception and not button(at, "save").disabled
    button(at, "save").click().run()
    text = at.file.read_text()
    assert "ollama/llama3" in text and "# Control flow" in text and "# Data flow" in text


def test_an_invalid_edit_cannot_be_saved(at):
    pick(at, "draft")
    at.text_area(key="cfg_draft_prompt_ref").set_value("prompts.nope").run()
    button(at, "set_draft_prompt_ref").click().run()
    assert button(at, "save").disabled and at.error                        # the problem is listed, Save is off
    assert "prompts.nope" not in at.file.read_text()


def test_undo_restores_the_edit(at):
    pick(at, "draft")
    at.text_area(key="cfg_draft_model").set_value("x/y").run()
    button(at, "set_draft_model").click().run()
    button(at, "undo").click().run()
    assert button(at, "save").disabled and at.text_area(key="cfg_draft_model").value == "ollama/gemma3"


def test_a_node_is_added_from_the_form_and_saved(at):
    at.text_input(key="new_id").set_value("polish")
    at.text_input(key="new_ports").set_value("trigger, complete, in_essay, out_essay")
    at.text_area(key="new_config").set_value("prompt_inline: Polish {{in_essay}}")
    button(at, "add_node_submit").click().run()
    assert not at.exception
    pick(at, "polish")
    assert at.text_area(key="cfg_polish_prompt_inline").value == "Polish {{in_essay}}"
    button(at, "save").click().run()                                       # unwired is only a warning, so it saves
    assert "polish" in at.file.read_text()


def test_a_node_can_be_removed(at):
    pick(at, "critique")
    button(at, "rm_critique").click().run()
    assert "critique" not in [o for o in at.selectbox(key="node_pick").options]
