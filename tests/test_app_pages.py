"""The pages of `graf vis --edit` besides the editor itself: Create, Settings, Import/Export, and the command line that starts them.
The LLM is a stub; nothing here calls a model."""
import io
import json
import shutil
import stat
import sys
import zipfile
from pathlib import Path

import pytest
from click.testing import CliRunner

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest

from graphlang import workspace as ws
from graphlang.cli import main as graf
from graphlang.grafv import ui
sys.path.insert(0, str(Path(__file__).parent))
from test_create import Scripted, reply_for      # noqa: E402

ROOT = Path(__file__).parent.parent
APP = ROOT / "graphlang" / "grafv" / "app.py"


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("GRAFLANG_HOME", str(tmp_path / "home"))
    for var in ("GRAF_EDIT_FILE", "GRAF_SRC_DIR", "OPENAI_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    ws.save_settings({"embedding": "none"})                    # plain pytest is offline: the search uses words only unless a test says otherwise
    return tmp_path / "home"


def load_page(stem):
    """The module of `pages/NN-<stem>.py` (the file names start with a number, so they cannot be imported by name)."""
    import importlib.util
    path = next((ROOT / "graphlang" / "grafv" / "pages").glob(f"[0-9]*-{stem}.py"))
    spec = importlib.util.spec_from_file_location(f"page_{stem}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def page(name):
    """An AppTest that runs one page function with a fresh work area."""
    def script(which):
        import streamlit as st
        from graphlang import workspace as w
        import importlib.util
        from pathlib import Path
        folder = Path(w.__file__).parent / "grafv" / "pages"
        path = next(folder.glob(f"[0-9]*-{which}.py"))
        spec = importlib.util.spec_from_file_location(f"page_{which}", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        st.session_state.setdefault("workspace", w.Workspace())
        st.session_state.setdefault("pages", {"edit": "edit"})
        getattr(module, f"{which}_page")()
    return AppTest.from_function(script, args=(name,), default_timeout=30)


def button(at, key):
    return next(b for b in at.button if b.key == key)


def send(at, scope, text):
    """Type `text` in the chat box of `scope` ("create" or "edit") and press Send."""
    boxes = [w for tree in (at, at.sidebar) for w in tree.text_area if w.key == f"{scope}_text"]
    boxes[0].set_value(text)
    [b for tree in (at, at.sidebar) for b in tree.button if b.key == f"{scope}_send"][0].click().run()


# ── Settings ─────────────────────────────────────────────────────────────────────────────────────

def test_settings_save_provider_model_and_a_key_privately(home, monkeypatch):
    at = page("settings").run()
    assert not at.exception
    at.selectbox(key="set_provider").select("openai").run()
    at.text_input(key="set_model_openai").set_value("some-model").run()
    at.text_input(key="set_OPENAI_API_KEY").set_value("sk-test-1234567890abcd").run()
    button(at, "set_save").click().run()
    assert not at.exception
    saved = ws.settings_path()
    assert stat.S_IMODE(saved.stat().st_mode) == 0o600
    assert json.loads(saved.read_text()) == {"provider": "openai", "model": "some-model", "keys": {"OPENAI_API_KEY": "sk-test-1234567890abcd"}, "canvas_height": 800, "embedding": "none"}
    import os
    assert os.environ["OPENAI_API_KEY"] == "sk-test-1234567890abcd"
    monkeypatch.delenv("OPENAI_API_KEY")


def test_settings_never_show_a_saved_key_in_full(home, monkeypatch):
    ws.save_settings({"provider": "openai", "model": "", "keys": {"OPENAI_API_KEY": "sk-test-1234567890abcd"}})
    at = page("settings").run()
    box = at.text_input(key="set_OPENAI_API_KEY")
    assert box.value == "" and "sk-test" not in str(box.placeholder) and box.placeholder.endswith("abcd")
    button(at, "rm_OPENAI_API_KEY").click().run()
    assert json.loads(ws.settings_path().read_text())["keys"] == {}
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


def test_a_provider_with_its_own_login_asks_for_no_key(home):
    at = page("settings").run()
    assert at.selectbox(key="set_provider").value == "claude_cli" and any("own login" in i.value for i in at.info)


def test_the_connection_test_reports_a_failure_instead_of_crashing(home, monkeypatch):
    def broken(max_calls):
        raise RuntimeError("no network")
    monkeypatch.setattr(ui, "new_llm", broken)
    at = page("settings").run()
    button(at, "set_test").click().run()
    assert not at.exception and any("no network" in e.value for e in at.error)


# ── Import / Export ──────────────────────────────────────────────────────────────────────────────

def test_install_the_cookbook_from_a_folder_and_keep_what_is_there(home):
    at = page("transfer").run()
    at.text_input(key="cookbook_source").set_value(str(ROOT / "cookbook")).run()
    button(at, "cookbook_install").click().run()
    assert not at.exception and (home / "cookbook" / "self_refine" / "self_refine.graph.yaml").is_file()
    assert any("installed" in s.value for s in at.success)
    button(at, "cookbook_install").click().run()
    assert any("kept" in s.value for s in at.success)


def test_install_from_a_folder_with_no_recipes_says_so(home, tmp_path):
    (tmp_path / "empty").mkdir()
    at = page("transfer").run()
    at.text_input(key="cookbook_source").set_value(str(tmp_path / "empty")).run()
    button(at, "cookbook_install").click().run()
    assert any("no recipe" in e.value for e in at.error)


def test_export_offers_the_recipe_as_a_zip_without_run_output(home):
    shutil.copytree(ROOT / "cookbook" / "self_refine", home / "apps" / "mine", ignore=shutil.ignore_patterns("output"))
    (home / "apps" / "mine" / "output").mkdir()
    (home / "apps" / "mine" / "output" / "old.txt").write_text("run")
    at = page("transfer").run()
    assert not at.exception
    zipped = ws.export_zip(home / "apps" / "mine")
    assert "mine/self_refine.graph.yaml" in zipfile.ZipFile(io.BytesIO(zipped)).namelist() and b"old.txt" not in zipped


# ── Create ───────────────────────────────────────────────────────────────────────────────────────

def stub_llm(monkeypatch, *replies):
    llm = Scripted(*replies)

    class Meter:
        def generate(self, prompt, model=None, **kw):
            return llm.generate(prompt, model=model)

        def snapshot(self):
            return {"input_tokens": 10, "output_tokens": 5, "calls": len(llm.prompts)}
    monkeypatch.setattr(ui, "new_llm", lambda max_calls: (Meter(), "scripted", None))
    return llm


def test_create_makes_a_draft_from_the_first_message_and_nothing_is_written(home, monkeypatch):
    llm = stub_llm(monkeypatch, reply_for("linear", "notes"))
    at = page("create").run()
    at.sidebar.text_input(key="create_name").set_value("notes").run()
    send(at, "create", "summarize a meeting")
    assert not at.exception, at.exception
    assert "summarize a meeting" in llm.prompts[0]
    assert at.session_state["draft"]["name"] == "notes" and at.session_state["draft"]["created"].ok
    assert not (home / "apps").exists()                                                  # not saved yet
    assert any("checks out" in s.value for s in at.success)


def test_create_revises_the_draft_with_the_next_message_and_can_undo_it(home, monkeypatch):
    llm = stub_llm(monkeypatch, reply_for("linear", "notes"), reply_for("linear", "notes").replace("Summarize", "Shorten", 1))
    at = page("create").run()
    at.sidebar.text_input(key="create_name").set_value("notes").run()
    send(at, "create", "summarize a meeting")
    first = dict(at.session_state["draft"]["files"])
    send(at, "create", "make it shorter")
    assert "Change the existing app `notes`" in llm.prompts[1] and "make it shorter" in llm.prompts[1]
    assert at.session_state["draft"]["files"] != first
    button(at, "create_undo").click().run()
    assert at.session_state["draft"]["files"] == first


def test_create_saves_into_apps_and_refuses_to_overwrite(home, monkeypatch):
    stub_llm(monkeypatch, reply_for("linear", "notes"), reply_for("linear", "notes"))
    at = page("create").run()
    at.sidebar.text_input(key="create_name").set_value("notes").run()
    send(at, "create", "summarize")
    button(at, "create_save").click().run()
    assert (home / "apps" / "notes" / "notes.graph.yaml").is_file() and (home / "apps" / "notes" / "create.json").is_file()
    # a different draft with a taken name does not replace what is there
    button(at, "create_reset").click().run()
    at.sidebar.text_input(key="create_name").set_value("notes").run()
    send(at, "create", "summarize again")
    button(at, "create_save").click().run()
    assert any("already has files" in e.value for e in at.error)


def test_a_draft_can_be_saved_again_after_a_revision_and_undo_takes_its_spec_back(home, monkeypatch):
    stub_llm(monkeypatch, reply_for("linear", "notes"), reply_for("linear", "notes").replace("Summarize", "Shorten", 1))
    at = page("create").run()
    at.sidebar.text_input(key="create_name").set_value("notes").run()
    send(at, "create", "summarize a meeting")
    button(at, "create_save").click().run()
    folder = home / "apps" / "notes"
    before = dict(at.session_state["draft"]["files"])
    send(at, "create", "make it shorter")
    changed = next(k for k, v in at.session_state["draft"]["files"].items() if before.get(k) != v)
    assert (folder / changed).read_text() == before[changed]
    assert "make it shorter" in at.session_state["draft"]["spec"]
    assert button(at, "create_save").label.startswith("Save again")             # the draft's own folder may be replaced
    button(at, "create_save").click().run()
    assert not at.error and (folder / changed).read_text() == at.session_state["draft"]["files"][changed] != before[changed]
    assert "make it shorter" in json.loads((home / "apps" / "notes" / "create.json").read_text())["spec"]
    button(at, "create_undo").click().run()
    assert "make it shorter" not in at.session_state["draft"]["spec"]


def test_open_in_edit_after_saving_shows_the_saved_app_even_if_edit_was_never_opened(home, monkeypatch):
    stub_llm(monkeypatch, reply_for("linear", "notes"))
    at = page("create").run()
    at.sidebar.text_input(key="create_name").set_value("notes").run()
    send(at, "create", "summarize")
    button(at, "create_save").click().run()
    assert "opened" not in at.session_state
    button(at, "create_open_edit").click().run()
    assert at.session_state["opened"] == str(home / "apps" / "notes" / "notes.graph.yaml")


def test_create_reports_a_bad_name_and_a_failing_model_in_the_chat(home, monkeypatch):
    stub_llm(monkeypatch, reply_for("linear", "notes"))
    at = page("create").run()
    at.sidebar.text_input(key="create_name").set_value("1 Bad Name").run()
    send(at, "create", "x")
    assert not at.exception and "draft" not in at.session_state and any("not a usable name" in m["content"] for m in at.session_state["chat_create"])


def test_create_shows_problems_that_are_left(home, monkeypatch):
    broken = reply_for("linear", "notes").replace("version:", "versoin:", 1)
    stub_llm(monkeypatch, broken, broken, broken)
    at = page("create").run()
    at.sidebar.text_input(key="create_name").set_value("notes").run()
    send(at, "create", "x")
    assert not at.exception and at.error and not at.session_state["draft"]["created"].ok


# ── the app as a whole and the command line ──────────────────────────────────────────────────────

def test_the_app_opens_on_the_welcome_page_and_says_what_graphlang_is(home, monkeypatch):
    shutil.copytree(ROOT / "cookbook" / "self_refine", home / "cookbook" / "self_refine", ignore=shutil.ignore_patterns("output"))
    at = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not at.exception, at.exception
    assert at.title[0].value == "GraphLang" and any("graph is the program" in m.value for m in at.markdown)
    assert [m.label for m in at.metric][:2] == ["Recipes", "Your apps"] and at.metric[0].value == "1"
    assert not at.info                                                                   # there are recipes, so no "install the cookbook" hint


def test_the_welcome_page_points_to_the_cookbook_when_there_are_no_recipes(home):
    at = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not at.exception and any("no recipes yet" in i.value for i in at.info)


def test_a_file_given_on_the_command_line_opens_straight_on_the_edit_page(home, monkeypatch):
    shutil.copytree(ROOT / "cookbook" / "self_refine", home / "apps" / "self_refine", ignore=shutil.ignore_patterns("output"))
    monkeypatch.setenv("GRAF_EDIT_FILE", str(home / "apps" / "self_refine" / "self_refine.graph.yaml"))
    at = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not at.exception and at.sidebar.markdown[0].value == "### self_refine.graph.yaml"


def test_the_edit_page_with_nothing_open_asks_for_a_recipe(home):
    def script():
        import streamlit as st
        from graphlang import workspace as w
        import importlib.util
        from pathlib import Path
        path = next((Path(w.__file__).parent / "grafv" / "pages").glob("02-edit.py"))
        spec = importlib.util.spec_from_file_location("page_edit", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        st.session_state.setdefault("workspace", w.Workspace())
        module.edit_page()
    at = AppTest.from_function(script, default_timeout=30).run()
    assert not at.exception and any("Open a recipe" in i.value for i in at.info)


def test_a_shipped_recipe_is_read_only_until_it_is_copied_to_my_apps(home, monkeypatch):
    shutil.copytree(ROOT / "cookbook" / "self_refine", home / "cookbook" / "self_refine", ignore=shutil.ignore_patterns("output"))
    monkeypatch.setenv("GRAF_EDIT_FILE", str(home / "cookbook" / "self_refine" / "self_refine.graph.yaml"))
    at = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not at.exception and any("read-only" in i.value for i in at.info)
    assert not [b for b in at.button if b.key == "save"]                                  # no editor on a shipped recipe
    button(at, "copy_shipped").click().run()
    assert not at.exception
    assert (home / "apps" / "self_refine" / "self_refine.graph.yaml").is_file()
    assert at.sidebar.markdown[0].value == "### self_refine.graph.yaml"                   # now editing the copy
    assert (home / "cookbook" / "self_refine" / "self_refine.graph.yaml").read_bytes() == (ROOT / "cookbook" / "self_refine" / "self_refine.graph.yaml").read_bytes()


def test_a_compact_graph_of_your_own_is_converted_in_place_to_edit(home, monkeypatch):
    folder = home / "apps" / "app"
    shutil.copytree(ROOT / "graphlang" / "grafc" / "create_examples" / "linear", folder)
    monkeypatch.setenv("GRAF_EDIT_FILE", str(folder / "summarizer.graph.yaml"))
    at = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not at.exception and at.sidebar.markdown[0].value == "### summarizer.graph.yaml"
    assert "steps:" not in (folder / "summarizer.graph.yaml").read_text() and not (folder / "summarizer.long.graph.yaml").exists()


def test_vis_edit_with_no_graph_and_a_src_dir_starts_the_app_there(tmp_path, monkeypatch):
    seen = {}

    def fake_run(cmd, env=None, check=False):
        seen["cmd"], seen["env"] = cmd, env
    monkeypatch.setattr("subprocess.run", fake_run)
    (tmp_path / "recipes").mkdir()
    result = CliRunner().invoke(graf, ["vis", "--edit", "--src-dir", str(tmp_path / "recipes")])
    assert result.exit_code == 0, result.output
    assert seen["env"]["GRAF_SRC_DIR"] == str((tmp_path / "recipes").resolve()) and "GRAF_EDIT_FILE" not in seen["env"]
    assert seen["cmd"][-3].endswith("app.py") or any(c.endswith("app.py") for c in seen["cmd"])


def test_vis_src_dir_needs_edit_and_an_existing_folder(tmp_path):
    assert CliRunner().invoke(graf, ["vis", "--src-dir", str(tmp_path)]).exit_code != 0
    result = CliRunner().invoke(graf, ["vis", "--edit", "--src-dir", str(tmp_path / "nope")])
    assert result.exit_code == 1 and "not a folder" in " ".join(result.output.split())


def test_the_picture_height_is_set_on_the_settings_page_and_used_by_the_pages(home, monkeypatch):
    seen = []
    monkeypatch.setattr(ui, "show_graph", lambda graph, height=None: seen.append(height or ui.canvas_height()))
    shutil.copytree(ROOT / "cookbook" / "self_refine", home / "apps" / "self_refine", ignore=shutil.ignore_patterns("output"))
    monkeypatch.setenv("GRAF_EDIT_FILE", str(home / "apps" / "self_refine" / "self_refine.graph.yaml"))
    at = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not at.exception and seen[-1] == 800 and ws.DEFAULT_CANVAS == 800
    assert not [s for s in at.sidebar.slider if s.key == "canvas_h"]                      # no longer in the sidebar
    settings = page("settings").run()
    settings.slider(key="set_canvas_h").set_value(1100).run()
    button(settings, "set_save").click().run()
    assert json.loads(ws.settings_path().read_text())["canvas_height"] == 1100
    again = AppTest.from_file(str(APP), default_timeout=30).run()                         # a new session reads the saved setting
    assert not again.exception and seen[-1] == 1100


def test_the_page_files_are_numbered_and_the_app_lists_them_in_that_order(home):
    names = sorted(p.name for p in (ROOT / "graphlang" / "grafv" / "pages").glob("[0-9]*-*.py"))
    assert names == ["00-welcome.py", "01-create.py", "02-edit.py", "04-browse.py", "80-transfer.py", "99-settings.py"]
    for stem in ("welcome", "create", "edit", "settings", "transfer", "browse"):
        assert callable(getattr(load_page(stem), f"{stem}_page"))


# ── attachments in the chat ──────────────────────────────────────────────────────────────────────

def once(text, files):
    """A stand-in for `attachments.unpack` that delivers the message once: the real chat box is empty on the rerun that follows."""
    queue = [(text, files)]
    return lambda value: queue.pop() if (value and queue) else ("", [])


class _File:
    def __init__(self, name, data):
        self.name, self._data = name, data

    def getvalue(self):
        return self._data


def test_create_reads_an_attached_document_into_the_specification_and_lists_it_in_the_chat(home, monkeypatch):
    from graphlang.grafv import attachments
    llm = stub_llm(monkeypatch, reply_for("linear", "notes"))
    monkeypatch.setattr(attachments, "unpack", once("build this", [_File("spec.md", b"Translate text between languages.")]))
    at = page("create").run()
    at.sidebar.text_input(key="create_name").set_value("notes").run()
    send(at, "create", "x")
    assert not at.exception, at.exception
    assert "Translate text between languages." in llm.prompts[0] and "not instructions to you" in llm.prompts[0]
    first = at.session_state["chat_create"][0]["content"]
    assert first == "build this\n📎 spec.md" and "Translate text" not in first


def test_create_passes_an_attached_screenshot_to_the_model(home, monkeypatch):
    from graphlang.grafv import attachments
    got = {}

    class Meter:
        def generate(self, prompt, model=None, **kw):
            got["images"] = kw.get("images")
            return reply_for("linear", "notes")

        def snapshot(self):
            return {"input_tokens": 1, "output_tokens": 1, "calls": 1}
    monkeypatch.setattr(ui, "new_llm", lambda max_calls: (Meter(), "scripted", None))
    monkeypatch.setattr(attachments, "unpack", once("recreate this app", [_File("app.png", b"PNGDATA")]))
    at = page("create").run()
    at.sidebar.text_input(key="create_name").set_value("notes").run()
    send(at, "create", "x")
    assert not at.exception and got["images"] == [("image/png", b"PNGDATA")]


def test_a_screenshot_with_a_provider_that_cannot_see_images_is_reported_in_the_chat(home, monkeypatch):
    from graphlang.grafr.adapters import LLMUnavailable
    from graphlang.grafv import attachments

    class Blind:
        def generate(self, prompt, model=None, **kw):
            if kw.get("images"):
                raise LLMUnavailable("adapter 'claude_cli' cannot read images; choose one that can (anthropic)")
            return reply_for("linear", "notes")
    monkeypatch.setattr(ui, "new_llm", lambda max_calls: (Blind(), "claude_cli", None))
    monkeypatch.setattr(attachments, "unpack", once("recreate this", [_File("app.png", b"PNG")]))
    at = page("create").run()
    at.sidebar.text_input(key="create_name").set_value("notes").run()
    send(at, "create", "x")
    assert not at.exception and "draft" not in at.session_state
    assert any("cannot read images" in m["content"] for m in at.session_state["chat_create"])


def test_an_unusable_attachment_is_named_in_the_chat_and_the_text_still_goes_through(home, monkeypatch):
    from graphlang.grafv import attachments
    llm = stub_llm(monkeypatch, reply_for("linear", "notes"))
    monkeypatch.setattr(attachments, "unpack", once("summarize", [_File("paper.pdf", b"%PDF")]))
    at = page("create").run()
    at.sidebar.text_input(key="create_name").set_value("notes").run()
    send(at, "create", "x")
    assert any("paper.pdf" in m["content"] and "cannot be read" in m["content"] for m in at.session_state["chat_create"]) and "summarize" in llm.prompts[0]


# ── Browse, and recipes as examples for Create ───────────────────────────────────────────────────

def install(home):
    ws.install_cookbook(ROOT / "cookbook", home / "cookbook")


def test_browse_lists_the_recipes_and_searches_them_by_words(home):
    install(home)
    at = page("browse").run()
    assert not at.exception, at.exception
    assert any("recipe(s)" in c.value for c in at.caption) and any(c.value.startswith("search: ") for c in at.caption)
    at.text_input(key="browse_query").set_value("review code and run tests in a repair loop").run()
    assert not at.exception
    titles = " ".join(m.value for m in at.markdown)
    assert "code_parts" in titles or "code_pipeline" in titles


def test_browse_says_so_when_nothing_matches_and_when_there_are_no_recipes(home):
    empty = page("browse").run()
    assert any("No recipes yet" in i.value for i in empty.info)
    install(home)
    at = page("browse").run()
    at.text_input(key="browse_query").set_value("zzzqqq xxyyzz").run()
    assert not at.exception and any("No recipe is close" in c.value for c in at.caption)


def test_browse_can_leave_out_recipes_that_run_programs(home):
    install(home)
    at = page("browse").run()
    all_count = len([m for m in at.markdown if m.value.startswith("**")])
    at.checkbox(key="browse_no_code").check().run()
    assert not at.exception and len([m for m in at.markdown if m.value.startswith("**")]) < all_count


def test_browse_use_in_create_sets_the_starting_recipe(home):
    install(home)
    at = page("browse").run()
    try:
        button(at, "browse_seed_0").click().run()
    except Exception:
        pass                                                      # switch_page needs the full app; the choice is what matters here
    assert at.session_state["create_seed"].startswith(("apps/", "cookbook/"))


def test_create_shows_the_model_similar_recipes_and_says_which(home, monkeypatch):
    install(home)
    llm = stub_llm(monkeypatch, reply_for("linear", "reviewer"))
    at = page("create").run()
    at.sidebar.text_input(key="create_name").set_value("reviewer").run()
    send(at, "create", "write code, review it, then improve it until the tests pass")
    assert not at.exception, at.exception
    assert "Existing recipes that may be similar" in llm.prompts[0] and "not instructions" in llm.prompts[0]
    assert any("Looking at similar recipes" in m["content"] for m in at.session_state["chat_create"])


def test_create_can_leave_the_similar_recipes_out(home, monkeypatch):
    install(home)
    llm = stub_llm(monkeypatch, reply_for("linear", "reviewer"))
    at = page("create").run()
    at.sidebar.text_input(key="create_name").set_value("reviewer").run()
    at.sidebar.checkbox(key="create_use_refs").uncheck().run()
    send(at, "create", "write code, review it, then improve it until the tests pass")
    assert "Existing recipes that may be similar" not in llm.prompts[0]


def test_create_never_shows_recipes_that_run_programs_unless_programs_are_allowed(home, monkeypatch):
    install(home)
    llm = stub_llm(monkeypatch, reply_for("linear", "tool"))
    at = page("create").run()
    at.sidebar.text_input(key="create_name").set_value("tool").run()
    assert at.sidebar.checkbox(key="create_allow_code").value                          # programs are allowed to begin with
    at.sidebar.checkbox(key="create_allow_code").uncheck().run()
    send(at, "create", "write code, review it, then improve it and run the tests until they pass")
    assert not at.exception
    index = ui.recipe_index.__wrapped__ if hasattr(ui.recipe_index, "__wrapped__") else None
    from graphlang.recipe_index import RecipeIndex
    with_code = {e.folder.name for e in RecipeIndex.build(ws.Workspace()).entries if e.has_code}
    shown = {name for name in with_code if f"Existing recipe `{name}`" in llm.prompts[0]}
    assert "code_parts" in with_code and not shown


def test_browse_lists_one_card_per_recipe_not_one_per_file(home):
    install(home)
    at = page("browse").run()
    cards = [m.value for m in at.markdown if m.value.startswith("**") and "·" in m.value]
    keys = [c.split("`")[1] for c in cards]
    assert len(keys) == len(set(keys)) and "cookbook/compliance_audit" in keys and not any(k.endswith(".yaml") for k in keys)
    at.text_input(key="browse_query").set_value("compliance audit personal data").run()
    found = [m.value.split("`")[1] for m in at.markdown if m.value.startswith("**") and "·" in m.value]
    assert found.count("cookbook/compliance_audit") == 1


def test_browse_says_which_signals_the_search_uses_and_the_embedding_setting_is_on_the_settings_page(home):
    install(home)
    at = page("browse").run()
    assert any("words only" in c.value for c in at.caption if c.value.startswith("search:"))
    settings = page("settings").run()
    assert settings.text_input(key="set_embedding").value == "none"
    settings.text_input(key="set_embedding").set_value("ollama:qwen3-embedding:0.6b").run()
    button(settings, "set_save").click().run()
    assert json.loads(ws.settings_path().read_text())["embedding"] == "ollama:qwen3-embedding:0.6b"


def test_create_says_when_it_could_only_match_examples_by_words(home, monkeypatch):
    install(home)
    stub_llm(monkeypatch, reply_for("linear", "reviewer"))
    at = page("create").run()
    at.sidebar.text_input(key="create_name").set_value("reviewer").run()
    send(at, "create", "write code, review it, then improve it until the tests pass")
    assert any("chosen by words only" in m["content"] for m in at.session_state["chat_create"])


def test_create_asks_for_a_name_before_calling_the_model(home, monkeypatch):
    llm = stub_llm(monkeypatch, reply_for("linear", "notes"))
    at = page("create").run()
    send(at, "create", "summarize a meeting")
    assert not at.exception and not llm.prompts and "draft" not in at.session_state
    chat = at.session_state["chat_create"]
    assert chat[0]["content"] == "summarize a meeting" and "no name yet" in chat[-1]["content"]


def test_removing_a_saved_key_does_not_save_the_other_unsaved_edits(home):
    ws.save_settings({"provider": "openai", "model": "kept-model", "keys": {"OPENAI_API_KEY": "sk-test-1234567890abcd"}, "canvas_height": 800, "embedding": "none"})
    at = page("settings").run()
    at.text_input(key="set_model_openai").set_value("typed-but-not-saved").run()
    button(at, "rm_OPENAI_API_KEY").click().run()
    saved = json.loads(ws.settings_path().read_text())
    assert saved["model"] == "kept-model" and saved["keys"] == {}


def test_changing_the_provider_does_not_carry_the_old_model_name_over(home):
    ws.save_settings({"provider": "openai", "model": "gpt-x", "keys": {}, "canvas_height": 800, "embedding": "none"})
    at = page("settings").run()
    assert at.text_input(key="set_model_openai").value == "gpt-x"
    at.selectbox(key="set_provider").select("ollama").run()
    assert at.text_input(key="set_model_ollama").value == ""


# ── the app listens on this computer only; the pages guard unsaved edits; pictures are made on request ─────────────

def test_the_app_listens_on_this_computer_unless_told_otherwise(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr("subprocess.run", lambda cmd, env=None, check=False: seen.append(cmd))
    (tmp_path / "r").mkdir()
    base = ["vis", "--edit", "--src-dir", str(tmp_path / "r")]
    plain = CliRunner().invoke(graf, base)
    assert plain.exit_code == 0 and seen[-1][-2:] == ["--server.address", "127.0.0.1"] and "Warning" not in plain.output
    wide = CliRunner().invoke(graf, base + ["--host", "0.0.0.0"])
    assert wide.exit_code == 0 and seen[-1][-2:] == ["--server.address", "0.0.0.0"] and "no login" in " ".join(wide.output.split())


class Dirty:
    changed = True


def test_browse_and_create_do_not_open_another_file_over_unsaved_edits(home, monkeypatch):
    shutil.copytree(ROOT / "cookbook" / "self_refine", home / "cookbook" / "self_refine", ignore=shutil.ignore_patterns("output"))
    at = page("browse")
    at.session_state["editor"], at.session_state["file"] = Dirty(), "some.graph.yaml"
    at.run()
    assert not at.exception and button(at, "browse_open_0").disabled
    clean = page("browse").run()
    assert not button(clean, "browse_open_0").disabled


def test_a_staged_prompt_change_counts_as_unsaved():
    import streamlit as st
    from streamlit.testing.v1 import AppTest as App

    def script():
        import streamlit as st
        from graphlang.grafv import ui

        class Clean:
            changed = False
        st.session_state.setdefault("editor", Clean())
        st.session_state.setdefault("file", "f")
        st.write(str(ui.unsaved()))
        st.session_state["staged_f"] = {"prompts/a.md": "x"}
    app = App.from_function(script).run()
    assert app.markdown[0].value == "False"
    app.run()
    assert app.markdown[0].value == "True"


def test_browse_draws_a_picture_only_when_asked(home, monkeypatch):
    shutil.copytree(ROOT / "cookbook" / "self_refine", home / "cookbook" / "self_refine", ignore=shutil.ignore_patterns("output"))
    drawn = []
    monkeypatch.setattr(ui, "show_graph", lambda graph, height=None: drawn.append(height))
    at = page("browse").run()
    assert not at.exception and drawn == []
    at.toggle(key="browse_pic_0").set_value(True).run()
    assert drawn == [420]


def test_a_picture_is_made_once_per_graph_not_on_every_rerun(monkeypatch):
    made = []
    real = ui.render

    def counting(graph, path, engine, **kw):
        made.append(1)
        return real(graph, path, engine, **kw)
    monkeypatch.setattr(ui, "render", counting)
    ui._graph_html.clear()

    def script():
        from graphlang.grafv import ui as u
        g = {"version": "1.0-graph", "workflow": {"name": "t", "inputs": [], "outputs": []},
             "nodes": [{"id": "a", "type": "INPUT", "ports": ["out_x"]}], "edges": []}
        u.show_graph(g, 300)
    at = AppTest.from_function(script, default_timeout=30).run()
    at.run()
    assert not at.exception and len(made) == 1


def test_a_picture_that_cannot_be_drawn_is_a_warning_even_for_a_missing_program(monkeypatch):
    def broken(graph, path, engine, **kw):
        raise FileNotFoundError("dot")
    monkeypatch.setattr(ui, "render", broken)
    ui._graph_html.clear()

    def script():
        from graphlang.grafv import ui as u
        u.show_graph({"nodes": [], "edges": []}, 300)
    at = AppTest.from_function(script, default_timeout=30).run()
    assert not at.exception and any("cannot draw the graph" in w.value for w in at.warning)


def test_the_browse_files_box_can_be_filtered_by_folder(home):
    for root in ("apps", "cookbook", "solvers"):
        shutil.copytree(ROOT / "cookbook" / "self_refine", home / root / f"{root}_refine", ignore=shutil.ignore_patterns("output"))
    at = page("edit").run()
    assert not at.exception, at.exception
    assert at.sidebar.multiselect(key="open_roots").value == ["apps", "cookbook", "solvers"]        # all of them to begin with
    assert [o.split("/")[0] for o in at.sidebar.selectbox(key="open_pick").options] == ["apps", "cookbook", "solvers"]
    at.sidebar.multiselect(key="open_roots").set_value(["solvers"]).run()
    assert [o.split("/")[0] for o in at.sidebar.selectbox(key="open_pick").options] == ["solvers"]
    at.sidebar.multiselect(key="open_roots").set_value(["apps", "solvers"]).run()
    assert [o.split("/")[0] for o in at.sidebar.selectbox(key="open_pick").options] == ["apps", "solvers"]
    at.sidebar.multiselect(key="open_roots").set_value([]).run()
    assert not at.exception and not [s for s in at.sidebar.selectbox if s.key == "open_pick"]
    assert any("No recipe in the folders chosen" in c.value for c in at.sidebar.caption)


def test_the_create_settings_start_with_programs_allowed_and_three_attempts_of_up_to_ten(home):
    at = page("create").run()
    slider = at.sidebar.slider(key="create_rounds")
    assert at.sidebar.checkbox(key="create_allow_code").value is True
    assert (slider.min, slider.max, slider.value) == (1, 10, 3)


def test_the_chat_box_is_a_two_line_text_area_with_a_send_button(home):
    at = page("create").run()
    box = at.sidebar.text_area(key="create_text")
    assert box.value == "" and not at.chat_input                                       # a text area, not the one-line chat input
    assert any(b.key == "create_send" for b in at.sidebar.button)


def test_a_name_with_a_hyphen_is_saved_with_an_underscore_and_the_message_is_sent(home, monkeypatch):
    llm = stub_llm(monkeypatch, reply_for("linear", "portfolio_outlook"))
    at = page("create").run()
    at.sidebar.text_input(key="create_name").set_value("Portfolio-Outlook").run()
    assert any("portfolio_outlook" in c.value for c in at.sidebar.caption)             # it says what the name becomes
    send(at, "create", "summarize a meeting")
    assert not at.exception, at.exception
    assert llm.prompts and at.session_state["draft"]["name"] == "portfolio_outlook"


def test_an_unusable_name_is_named_in_the_reply_not_just_called_missing(home):
    at = page("create").run()
    at.sidebar.text_input(key="create_name").set_value("1st app").run()
    assert at.sidebar.error                                                           # shown next to the field at once
    send(at, "create", "summarize a meeting")
    reply = [m for m in at.session_state["chat_create"] if m["role"] == "assistant"][-1]["content"]
    assert "`1st app` is not a usable name" in reply


def test_the_picture_starts_on_the_grid_arrangement(tmp_path):
    from graphlang.grafv.engines import render
    g = {"version": "1.0-graph", "workflow": {"name": "t", "inputs": [], "outputs": []},
         "nodes": [{"id": "a", "type": "INPUT", "ports": ["out_x"]}], "edges": []}
    html = render(g, tmp_path / "a.html", "cytoscape", default_layout=ui.PICTURE_LAYOUT)[0].read_text()
    assert "<option selected>grid</option>" in html
    assert "<option selected>" not in render(g, tmp_path / "b.html", "cytoscape")[0].read_text()      # `graf vis` keeps its own default


def test_the_chat_is_scrollable_clearable_and_the_buttons_share_a_row(home, monkeypatch):
    stub_llm(monkeypatch, reply_for("linear", "notes"))
    at = page("create").run()
    at.sidebar.text_input(key="create_name").set_value("notes").run()
    send(at, "create", "summarize a meeting")
    assert at.session_state["chat_create"]                                                  # shown in a fixed-height, scrolling box (ui.CHAT_HEIGHT)
    keys = [b.key for b in at.sidebar.button]
    assert keys.index("create_send") + 1 == keys.index("create_clear")                      # Send and Clear side by side
    [b for b in at.sidebar.button if b.key == "create_clear"][0].click().run()
    assert at.session_state["chat_create"] == [] and at.session_state["draft"]["name"] == "notes"      # only the chat is emptied


def test_a_draft_shows_readme_first_then_the_workflow_tab(home, monkeypatch):
    stub_llm(monkeypatch, reply_for("linear", "notes"))
    at = page("create").run()
    at.sidebar.text_input(key="create_name").set_value("notes").run()
    send(at, "create", "summarize a meeting")
    labels = [t.label for t in at.tabs]
    assert labels[:2] == ["readme.md", "Workflow"] and "Picture" not in labels and "notes.graph.yaml" in labels


def test_the_create_sidebar_order_and_the_primary_send_button(home):
    at = page("create").run()
    assert [e.label for e in at.sidebar.expander] == ["Settings for this chat"]
    assert any(c.value.startswith("model: ") for c in at.sidebar.expander[0].caption)       # the model line sits inside the settings
    send_button = next(b for b in at.sidebar.button if b.key == "create_send")
    assert send_button.proto.type == "primary"
