"""The work area behind `graf vis --edit`: recipes, copies, zip import/export and the LLM settings file. No network, no LLM."""
import io
import os
import stat
import zipfile
from pathlib import Path

import pytest

from graphlang import workspace as ws

COOKBOOK = Path(__file__).parent.parent / "cookbook"


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("GRAFLANG_HOME", str(tmp_path / "home"))
    return tmp_path / "home"


def make_recipe(root: Path, name="r", graphs=("r",), extra=None):
    folder = root / name
    (folder / "prompts").mkdir(parents=True)
    for g in graphs:
        (folder / f"{g}.graph.yaml").write_text("version: 1.0-graph\nworkflow: {name: x}\nnodes: []\n")
    (folder / "prompts" / "p.md").write_text("hi")
    (folder / "output").mkdir()
    (folder / "output" / "run.txt").write_text("old run")
    for rel, text in (extra or {}).items():
        (folder / rel).parent.mkdir(parents=True, exist_ok=True)
        (folder / rel).write_text(text)
    return folder


def test_default_roots_are_apps_cookbook_solvers_pocketflow_and_only_apps_is_writable(home):
    roots = ws.Workspace().roots
    assert [(r.name, r.path, r.writable) for r in roots] == [("apps", home / "apps", True), ("cookbook", home / "cookbook", False), ("solvers", home / "solvers", False),
                                                                     ("pocketflow", home / "pocketflow", False)]
    assert ws.Workspace().write_root == home / "apps"


def test_an_explicit_src_dir_is_the_only_root_and_is_writable(tmp_path):
    w = ws.Workspace(tmp_path / "mine")
    assert [(r.name, r.writable) for r in w.roots] == [("src", True)] and w.write_root == tmp_path / "mine"


def test_recipes_lists_each_graph_in_a_folder_under_a_root(home):
    make_recipe(home / "cookbook", "pocket", graphs=("a", "b"))
    make_recipe(home / "apps", "mine", graphs=("mine",))
    (home / "cookbook" / "empty").mkdir()
    labels = [r.label for r in ws.Workspace().recipes()]
    assert labels == ["apps/mine/mine", "cookbook/pocket/a", "cookbook/pocket/b"]


def test_a_cookbook_recipe_is_read_only_and_an_app_is_editable(home):
    make_recipe(home / "cookbook", "c")
    make_recipe(home / "apps", "a")
    w = ws.Workspace()
    assert not w.writable_for(home / "cookbook" / "c" / "r.graph.yaml") and w.writable_for(home / "apps" / "a" / "r.graph.yaml")


def test_clone_recipe_copies_the_folder_without_run_output_and_never_overwrites(home):
    src = make_recipe(home / "cookbook", "c")
    new = ws.clone_recipe(src, home / "apps")
    assert (new / "r.graph.yaml").is_file() and (new / "prompts" / "p.md").read_text() == "hi" and not (new / "output").exists()
    with pytest.raises(ws.WorkspaceError, match="already exists"):
        ws.clone_recipe(src, home / "apps")
    assert ws.clone_recipe(src, home / "apps", "c2").name == "c2"
    assert ws.free_name(home / "apps", "c") == "c-2"


@pytest.mark.parametrize("name", ["../x", "a/b", ".hid", "output"])
def test_clone_recipe_refuses_unusable_names(home, name):
    src = make_recipe(home / "cookbook", "c")
    with pytest.raises(ws.WorkspaceError):
        ws.clone_recipe(src, home / "apps", name)


def test_install_cookbook_copies_new_recipes_and_skips_ones_already_there(home):
    make_recipe(home / "source", "one")
    make_recipe(home / "source", "two")
    (home / "source" / "notarecipe").mkdir()
    assert ws.install_cookbook(home / "source", home / "cookbook") == (["one", "two"], [])
    (home / "cookbook" / "one" / "mine.txt").write_text("my edit")
    assert ws.install_cookbook(home / "source", home / "cookbook") == ([], ["one", "two"])
    assert (home / "cookbook" / "one" / "mine.txt").read_text() == "my edit"           # nothing was overwritten


def test_install_the_real_cookbook_of_this_checkout(home):
    copied, _ = ws.install_cookbook(COOKBOOK, home / "cookbook")
    assert "self_refine" in copied and "compliance_audit" in copied
    assert not list((home / "cookbook").rglob("output"))


def test_export_then_import_round_trips_a_recipe_and_leaves_out_run_output(home):
    src = make_recipe(home / "apps", "mine")
    data = ws.export_zip(src)
    names = zipfile.ZipFile(io.BytesIO(data)).namelist()
    assert "mine/r.graph.yaml" in names and "mine/prompts/p.md" in names and not any("output" in n for n in names)
    [new] = ws.import_zip(data, home / "elsewhere")
    assert (new / "r.graph.yaml").is_file() and new.name == "mine"
    with pytest.raises(ws.WorkspaceError, match="already"):
        ws.import_zip(data, home / "elsewhere")


def test_import_zip_accepts_a_whole_cookbook_and_a_single_recipe_at_the_top(home):
    cook = io.BytesIO()
    with zipfile.ZipFile(cook, "w") as z:
        for n in ("a", "b"):
            z.writestr(f"{n}/{n}.graph.yaml", "workflow: {}")
    assert sorted(p.name for p in ws.import_zip(cook.getvalue(), home / "apps")) == ["a", "b"]
    flat = io.BytesIO()
    with zipfile.ZipFile(flat, "w") as z:
        z.writestr("solo.graph.yaml", "workflow: {}")
        z.writestr("prompts/x.md", "p")
    [one] = ws.import_zip(flat.getvalue(), home / "apps", name="solo_copy")
    assert one.name == "solo_copy" and (one / "prompts" / "x.md").is_file()


@pytest.mark.parametrize("member", ["../evil.txt", "/abs/evil.txt", "a/../../evil.txt"])
def test_import_zip_refuses_paths_that_climb_out(home, member):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(member, "x")
        z.writestr("ok/ok.graph.yaml", "workflow: {}")
    with pytest.raises(ws.WorkspaceError, match="unsafe"):
        ws.import_zip(buf.getvalue(), home / "apps")
    assert not (home / "evil.txt").exists() and not (home / "apps").exists()


def test_import_zip_refuses_a_non_zip_and_an_archive_without_a_recipe(home):
    with pytest.raises(ws.WorkspaceError, match="not a zip"):
        ws.import_zip(b"nope", home / "apps")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("readme.txt", "x")
    with pytest.raises(ws.WorkspaceError, match="no recipe"):
        ws.import_zip(buf.getvalue(), home / "apps")


def test_import_graph_file_writes_a_new_folder_and_checks_it_is_a_workflow(home):
    path = ws.import_graph_file("workflow: {name: w}\nnodes: []\n", "shared.graph.yaml", home / "apps")
    assert path == home / "apps" / "shared" / "shared.graph.yaml"
    with pytest.raises(ws.WorkspaceError, match="already exists"):
        ws.import_graph_file("workflow: {}", "shared.graph.yaml", home / "apps")
    with pytest.raises(ws.WorkspaceError, match="workflow"):
        ws.import_graph_file("just: text", "x.graph.yaml", home / "apps")
    with pytest.raises(ws.WorkspaceError, match="YAML"):
        ws.import_graph_file("a: [", "x.graph.yaml", home / "apps")


def test_scan_for_code_flags_programs_in_an_imported_recipe(home):
    safe = make_recipe(home / "apps", "safe")
    assert ws.scan_for_code(safe) == []
    risky = make_recipe(home / "apps", "risky", extra={
        "risky.graph.yaml": "workflow: {name: x}\nnodes:\n- {id: t, type: SOLVE, config: {backend: kernel, code: 'x=1'}}\n- {id: r, type: RUN, config: {}}\n",
        "tools/go.py": "print(1)"})
    notes = ws.scan_for_code(risky)
    assert any("node t runs a program" in n for n in notes) and any("node r runs a program" in n for n in notes) and any("go.py" in n for n in notes)


def test_settings_file_is_private_and_round_trips(home):
    path = ws.save_settings({"provider": "openai", "model": "m", "keys": {"OPENAI_API_KEY": "sk-secret-1234", "EMPTY": ""}})
    assert stat.S_IMODE(path.stat().st_mode) == 0o600 and not list(home.glob(".settings.*"))
    s = ws.load_settings()
    assert s == {"provider": "openai", "model": "m", "keys": {"OPENAI_API_KEY": "sk-secret-1234"}, "canvas_height": 800, "embedding": "auto"}
    assert ws.llm_spec(s) == "openai:m" and ws.llm_spec({"provider": "claude_cli"}) == "claude_cli"


def test_settings_default_when_missing_or_broken(home):
    assert ws.load_settings()["provider"] == "claude_cli"
    ws.settings_path().parent.mkdir(parents=True)
    ws.settings_path().write_text("{ not json")
    assert ws.load_settings() == ws.DEFAULT_SETTINGS | {"keys": {}}


def test_apply_settings_never_overrides_the_real_environment():
    env = {"OPENAI_API_KEY": "from-env"}
    applied = ws.apply_settings({"keys": {"OPENAI_API_KEY": "from-file", "GEMINI_API_KEY": "g"}}, env)
    assert env == {"OPENAI_API_KEY": "from-env", "GEMINI_API_KEY": "g"} and applied == ["GEMINI_API_KEY"]


def test_mask_shows_only_the_end_of_a_key():
    assert ws.mask("sk-abcdef123456") == "••••••••3456" and ws.mask("") == "" and ws.mask("abc") == "•••"
    assert ws.is_secret("OPENAI_API_KEY") and not ws.is_secret("OLLAMA_HOST")


def test_providers_include_the_ones_with_keys():
    assert {"claude_cli", "openai", "ollama", "gemini"} <= set(ws.providers())


def test_find_secrets_flags_files_that_look_like_they_hold_a_key(home):
    folder = make_recipe(home / "apps", "leaky", extra={
        "notes.md": "my key is sk-abcdefghijklmnop1234", "cfg.txt": "api_key = abcdef1234567890xyz", "fine.md": "no secrets here"})
    assert ws.find_secrets(folder) == ["cfg.txt", "notes.md"]
    assert ws.find_secrets(make_recipe(home / "apps", "clean")) == []


def test_long_form_copy_of_a_compact_file_is_written_beside_it_once(home):
    folder = home / "apps" / "app"
    shutil_src = Path(__file__).parent.parent / "graphlang" / "grafc" / "create_examples" / "linear"
    import shutil
    shutil.copytree(shutil_src, folder)
    compact = folder / "summarizer.graph.yaml"
    long = ws.long_form_copy(compact)
    assert long.name == "summarizer.long.graph.yaml" and "nodes:" in long.read_text() and "steps:" not in long.read_text()
    from graphlang.grafv.editor import GraphEditor
    GraphEditor(long)                                                       # the editor accepts it
    assert ws.long_form_copy(compact) == long
    with pytest.raises(ws.WorkspaceError, match="not in the compact"):
        ws.long_form_copy(long)


def test_canvas_height_is_kept_within_limits_and_defaults_when_bad(home):
    for given, expected in ((1100, 1100), (50, 400), (5000, 1600), ("700", 700), ("tall", 800), (None, 800)):
        ws.save_settings({"canvas_height": given})
        assert ws.load_settings()["canvas_height"] == expected


def test_graphs_in_lists_the_graphs_of_a_recipe_including_sub_folders_but_not_run_output(home):
    folder = make_recipe(home / "cookbook", "demo", graphs=("demo",), extra={
        "sub_graph/explain.graph.yaml": "workflow: {}", "sub_graph/deep/inner.graph.yaml": "workflow: {}", "output/run/old.graph.yaml": "workflow: {}",
        ".hidden/x.graph.yaml": "workflow: {}"})
    assert [p.relative_to(folder).as_posix() for p in ws.graphs_in(folder)] == ["demo.graph.yaml", "sub_graph/explain.graph.yaml", "sub_graph/deep/inner.graph.yaml"]


def test_a_graph_in_a_sub_folder_belongs_to_its_recipe(home):
    folder = make_recipe(home / "cookbook", "demo", extra={"sub_graph/x.graph.yaml": "workflow: {}"})
    w = ws.Workspace()
    assert w.recipe_folder(folder / "sub_graph" / "x.graph.yaml") == folder.resolve() and w.recipe_folder(folder / "r.graph.yaml") == folder.resolve()
    outside = home / "elsewhere" / "g.graph.yaml"
    assert w.recipe_folder(outside) == outside.parent.resolve()
    nested = home / "elsewhere" / "sub" / "deep.graph.yaml"                       # outside every root: up to the folder that holds a graph
    (home / "elsewhere").mkdir(parents=True, exist_ok=True)
    (home / "elsewhere" / "top.graph.yaml").write_text("workflow: {}")
    nested.parent.mkdir(); nested.write_text("workflow: {}")
    assert w.recipe_folder(nested) == (home / "elsewhere").resolve()


def test_every_shipped_recipe_validates_from_a_copy_elsewhere(tmp_path):
    """An installed or cloned recipe lives outside the repository: nothing it names may be a path out of its own folder (the Edit page showed
    `../../graphlang/policies/...` does not exist for code_pipeline)."""
    from click.testing import CliRunner
    from graphlang.cli import main
    root = Path(__file__).parent.parent / "cookbook"
    copied, _ = ws.install_cookbook(root, tmp_path / "elsewhere")
    assert copied
    for folder in sorted((tmp_path / "elsewhere").iterdir()):
        for graph in ws.graphs_in(folder):
            result = CliRunner().invoke(main, ["validate", str(graph)])
            assert "does not exist" not in result.output, f"{graph}: {result.output}"


def test_the_solvers_folder_is_a_third_read_only_root(home):
    w = ws.Workspace()
    assert [(r.name, r.writable) for r in w.roots] == [("apps", True), ("cookbook", False), ("solvers", False), ("pocketflow", False)]
    assert ws.solvers_dir() == home / "solvers" and ws.pocketflow_dir() == home / "pocketflow" and w.write_root == home / "apps"
    graph = home / "solvers" / "z3_compliance" / "z3_compliance.graph.yaml"
    graph.parent.mkdir(parents=True)
    graph.write_text("version: 1.0-graph\nworkflow: {name: z, inputs: [], outputs: []}\nnodes: []\nedges: []\n")
    assert [r.label for r in w.recipes()] == ["solvers/z3_compliance/z3_compliance"]
    assert w.is_shipped(graph) and not w.writable_for(graph)                    # like the cookbook: copy it to your apps to edit
    assert w.recipe_folder(graph) == (home / "solvers" / "z3_compliance").resolve()


def test_a_src_dir_replaces_all_three_roots(tmp_path):
    assert [r.name for r in ws.Workspace(tmp_path).roots] == ["src"]


def test_a_pocketflow_recipe_is_found_by_the_app_and_by_a_part_reference(home):
    from graphlang.grafr.parts import named_part
    graph = home / "pocketflow" / "rag" / "rag.graph.yaml"
    graph.parent.mkdir(parents=True)
    graph.write_text((Path(__file__).resolve().parent.parent / "cookbook" / "self_refine" / "self_refine.graph.yaml").read_text())
    assert [r.label for r in ws.Workspace().recipes() if r.root == "pocketflow"] == ["pocketflow/rag/rag"]
    assert named_part("pocketflow:rag") == graph


# ---- Capture: the canvas sends a PDF, the app saves it under ~/.graflang/images ----------------------------------------
def test_save_capture_writes_a_pdf_and_refuses_anything_else(tmp_path, monkeypatch):
    import base64
    from graphlang import workspace as ws
    monkeypatch.setenv("GRAFLANG_HOME", str(tmp_path))
    pdf = base64.b64encode(b"%PDF-1.4\nx").decode()
    path = ws.save_capture("hello world/../x.pdf", pdf)
    assert path.parent == tmp_path / "images" and path.name.startswith("hello_world_x-") and path.read_bytes().startswith(b"%PDF-")
    assert ws.save_capture("hello world/../x.pdf", pdf) != path                   # never overwrites
    with pytest.raises(ws.WorkspaceError, match="not a PDF"):
        ws.save_capture("x", base64.b64encode(b"<html>").decode())
    with pytest.raises(ws.WorkspaceError, match="base64"):
        ws.save_capture("x", "%%%")


def test_the_picture_starts_on_dot_and_has_a_capture_button():
    from graphlang.grafv import ui
    html = ui._graph_html('{"version": "1.0-graph", "workflow": {"name": "w", "inputs": [], "outputs": []}, "nodes": [{"id": "a", "type": "SOLVE", "ports": ["trigger", "complete"], "config": {"expression": "1"}}], "edges": []}')
    assert ui.PICTURE_LAYOUT == "dot"
    assert 'id="capture"' in html and html.index('id="reset"') < html.index('id="capture"')
