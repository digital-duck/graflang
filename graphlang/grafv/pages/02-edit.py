"""The Edit page of `graf vis --edit` (see app.py for the pages).

The picture is the same cytoscape view `graf vis` writes. Editing goes through `GraphEditor`: nothing is written until Save, Save
refuses while `graf validate` reports errors, comments in the file are kept, and every edit can be undone; the chat on the left changes
the graph through the same methods. `graf vis --edit` sets GRAF_EDIT_FILE (the file to open, optional) and GRAF_SRC_DIR (the work area
instead of ~/.graflang/cookbook, solvers, pocketflow and apps, optional).
"""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path

import streamlit as st
import yaml
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError
from ruamel.yaml.scalarstring import LiteralScalarString

from graphlang import workspace as ws
from graphlang.grafr.runtime import SCHEMA_PATH, load_graph
from graphlang.grafv import attachments, chat_ops, runs, ui
from graphlang.grafv.editor import EditError, GraphEditor
from graphlang.grafv.model import display_label

NODE_TYPES = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))["properties"]["nodes"]["items"]["properties"]["type"]["enum"]
_yaml = YAML(typ="safe")


def parse_value(text: str):
    """What a person typed in a config box: YAML, so 3 is a number, [a, b] a list, plain words a string."""
    try:
        return _yaml.load(text) if text.strip() else None
    except YAMLError as e:                                     # a typo in a box is a message, not a traceback
        raise EditError(f"that is not valid YAML: {getattr(e, 'problem', None) or str(e).splitlines()[0]}") from e


def show_value(value) -> str:
    """What a config box shows: a text as it is (a prompt reads as the prompt, not as quoted YAML), anything else as YAML."""
    if isinstance(value, str):
        return str(value)
    buf = io.StringIO()
    _yaml.dump(value, buf)
    return buf.getvalue().rstrip()


def new_value(original, text: str):
    """The value for what was typed: a text stays a text (a multi-line one is written back as a `|` block), anything else is read as YAML."""
    if isinstance(original, str):
        return LiteralScalarString(text) if "\n" in text else text
    return parse_value(text)


forget_widgets = ui.forget_widgets


def attempt(action, success: str = "") -> bool:
    try:
        action()
    except (EditError, ValueError) as e:
        st.session_state["flash"] = ("error", str(e))
        st.rerun()                                             # show the reason now, not at the next click
        return False
    forget_widgets()
    if success:
        st.session_state["flash"] = ("success", success)
    return True


def picture(editor: GraphEditor) -> None:
    ui.show_graph(editor.data())


def node_labels(editor: GraphEditor) -> dict:
    """id -> the name the picture shows for the node (its function, prompt or condition); `label (id)` when two nodes would read the same."""
    labels = {str(n["id"]): display_label(n) for n in editor.data()["nodes"]}
    counts = {}
    for label in labels.values():
        counts[label] = counts.get(label, 0) + 1
    return {i: (f"{label} ({i})" if counts[label] > 1 else label) for i, label in labels.items()}


def node_tab(editor: GraphEditor) -> None:
    ids = editor.node_ids()
    if not ids:
        st.info("no nodes yet")
        return
    labels = node_labels(editor)
    node_id = str(st.selectbox("Node", ids, key="node_pick", format_func=lambda i: labels.get(str(i), str(i))))
    node = editor.node(node_id)
    st.caption(f"id **{node_id}** · type **{node['type']}**")
    ports = st.text_input("Ports (comma separated)", ", ".join(node["ports"]), key=f"ports_{node_id}")
    if ports != ", ".join(node["ports"]) and st.button("Set ports", key=f"setports_{node_id}"):
        if attempt(lambda: editor.set_ports(node_id, [p.strip() for p in ports.split(",") if p.strip()]), "ports changed"):
            st.rerun()
    st.markdown("**Config**")
    for key, value in (node.get("config") or {}).items():
        text = st.text_area(key, show_value(value), key=f"cfg_{node_id}_{key}", height=68 if "\n" not in show_value(value) else 160)
        left, right = st.columns(2)
        if text != show_value(value) and left.button("Set", key=f"set_{node_id}_{key}"):
            if attempt(lambda: editor.set_config(node_id, key, new_value(value, text)), f"{key} changed"):
                st.rerun()
        if right.button("Delete", key=f"del_{node_id}_{key}"):
            if attempt(lambda: editor.delete_config(node_id, key), f"{key} deleted"):
                st.rerun()
    with st.form(f"newkey_{node_id}", clear_on_submit=True):
        key, value = st.text_input("New config key"), st.text_area("Value (YAML)", height=68)
        if st.form_submit_button("Add key") and key:
            if attempt(lambda: editor.set_config(node_id, key.strip(), parse_value(value)), f"{key} added"):
                st.rerun()
    new_id = st.text_input("Rename to", "", key=f"rename_{node_id}")
    cols = st.columns(2)
    if new_id and cols[0].button("Rename", key=f"renamebtn_{node_id}"):
        if attempt(lambda: editor.rename_node(node_id, new_id.strip()), f"renamed to {new_id}"):
            st.rerun()
    if cols[1].button("Remove node", key=f"rm_{node_id}"):
        if attempt(lambda: editor.remove_node(node_id), f"{node_id} removed"):
            st.rerun()


def source_height() -> int:
    """The source box follows the Settings picture height, less the tabs, file chooser and buttons around it, so the two panes end together."""
    return max(300, ui.canvas_height() - 250)


def source_box(key: str, value: str, language: str = "yaml") -> str:
    """An IDE-style editor (Ace, with syntax highlighting) when `streamlit-ace` is installed, else a plain monospace text area."""
    try:
        if os.environ.get("GRAF_PLAIN_EDITOR"):                  # a plain box on request (and in tests, which cannot drive a component)
            raise ImportError
        from streamlit_ace import st_ace
    except ImportError:
        return st.text_area("Source", value, key=key, height=source_height(), label_visibility="collapsed")
    # The component keeps its own text under its key (clearing session state does not reach it), so a new file, an Apply or an undo
    # would show the old text. A key that follows the text mounts a fresh editor whenever the graph in the editor changes; typing
    # does not change it (the key follows the applied text, not what is typed).
    return st_ace(value=value, language=language, theme="github", key=f"{key}_{hashlib.md5(value.encode()).hexdigest()[:12]}", height=source_height(),
                  tab_size=2, wrap=False, show_gutter=True,
                  auto_update=True) or value        # no Ace "Apply" button of its own: ours below is the only one


def recipe_files(folder: Path) -> list[str]:
    """The text files of the recipe folder (and its sub-folders), relative to it: what the Source tab can show. Run output, caches and hidden
    files are left out, and so is anything large."""
    found = []
    for here, dirs, names in os.walk(folder):
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in ws.SKIP_DIRS)
        for name in sorted(names):
            path = Path(here, name)
            if (not name.startswith(".") and path.suffix.lower() in chat_ops.EDITABLE_SUFFIXES and not path.is_symlink()
                    and path.stat().st_size <= chat_ops.MAX_EDITABLE_BYTES):
                found.append(path.relative_to(folder).as_posix())
    return sorted(found, key=lambda r: (r.count("/"), r))


def source_tab(editor: GraphEditor) -> None:
    """Browse and edit the files of the recipe. The graph file as text: edit it, Apply to bring it into the editor (undoable), then Save as
    usual. Any other file: Stage the change, and Save writes it together with the graph."""
    target = st.session_state.get("file")
    staged = st.session_state.setdefault(f"staged_{target}", {})
    folder = editor.path.resolve().parent
    graph_rel = editor.path.name
    files = [graph_rel] + [r for r in recipe_files(folder) if r != graph_rel]          # the graph first: it is what opens
    key = f"browse_{target}"
    if st.session_state.get(key) not in files:
        st.session_state.pop(key, None)
    rel = str(st.selectbox("File", files, key=key, format_func=lambda r: r + ("  (the graph)" if r == graph_rel else "") + ("  ● staged" if r in staged else ""),
                           help="the files of this recipe: the graph, its prompts, procedures, policies and notes"))
    st.caption(f"📄 `{folder / rel}`")                    # the file this text belongs to, so a mix-up cannot go unseen
    if rel == graph_rel:
        graph_source(editor)
    else:
        other_file(folder, rel, staged)


def graph_source(editor: GraphEditor) -> None:
    current = editor.source()
    text = source_box("source_text", current)
    changed = text != current
    left, right = st.columns(2)
    if left.button("Apply", key="source_apply", type="primary", disabled=not changed,
                   help="Replace the graph in the editor with this text. Nothing is written to the file until Save."):
        if attempt(lambda: editor.set_source(text), "source applied"):
            st.rerun()
    if right.button("Revert the text", key="source_revert", disabled=not changed, help="Throw away what you typed here and show the graph as it is now."):
        forget_widgets()
        st.rerun()
    st.caption("Apply checks that this is YAML in the long `nodes:`/`edges:` form; the Problems tab then says what `graf validate` finds, and Save "
               "stays off until there are no errors. Apply can be undone.")


def other_file(folder: Path, rel: str, staged: dict) -> None:
    path = folder / rel
    try:
        on_disk = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        st.warning(f"cannot read {rel}: {e}")
        return
    current = staged.get(rel, on_disk)
    language = chat_ops.EDITABLE_SUFFIXES.get(path.suffix.lower(), "text")
    text = source_box(f"source_file_{rel}", current, language)
    changed = text != current
    left, middle, right = st.columns(3)
    if left.button("Stage", key="file_stage", type="primary", disabled=not changed,
                   help="Keep this change with the graph's unsaved edits. Nothing is written until Save."):
        if text == on_disk:
            staged.pop(rel, None)
        else:
            staged[rel] = text
        forget_widgets()
        st.rerun()
    if middle.button("Revert the text", key="file_revert", disabled=not changed, help="Throw away what you typed here."):
        forget_widgets()
        st.rerun()
    if right.button("Drop the staged change", key="file_drop", disabled=rel not in staged, help="Go back to the file as it is on disk."):
        staged.pop(rel, None)
        forget_widgets()
        st.rerun()
    st.caption("A change here is staged, not written: Save (left) writes it together with the graph. Undo does not cover staged files.")


def add_tab(editor: GraphEditor) -> None:
    with st.form("addnode", clear_on_submit=True):
        node_id = st.text_input("Id", key="new_id")
        node_type = str(st.selectbox("Type", NODE_TYPES, index=NODE_TYPES.index("GENERATE"), key="new_type"))
        ports = st.text_input("Ports (comma separated)", "trigger, complete, in_input, out_output", key="new_ports")
        config = st.text_area("Config (YAML mapping, optional)", height=100, key="new_config")
        if st.form_submit_button("Add node", key="add_node_submit"):
            def add():
                cfg = parse_value(config)
                if cfg is not None and not isinstance(cfg, dict):
                    raise EditError("config must be a mapping, e.g. prompt_inline: Say hi")
                editor.add_node(node_id.strip(), node_type, [p.strip() for p in ports.split(",") if p.strip()], cfg)
            if attempt(add, f"{node_id} added"):
                st.rerun()


def edge_tab(editor: GraphEditor) -> None:
    graph = editor.data()
    ports = {n["id"]: n["ports"] for n in graph["nodes"]}
    refs = [f"{n}.{p}" for n, ps in ports.items() for p in ps]
    edges = graph["edges"]
    if edges:
        labels = [f"{e['source']} -> {e['target']}  ({e['type']})" for e in edges]
        picked = st.selectbox("Edge", labels, key="edge_pick")
        if st.button("Remove edge", key="rm_edge"):
            e = edges[labels.index(str(picked))]
            if attempt(lambda: editor.remove_edge(e["source"], e["target"], e["type"]), "edge removed"):
                st.rerun()
    st.markdown("**Add an edge**")
    kind = st.radio("Type", ["triggers", "binds"], horizontal=True, key="edge_kind")      # outside the form so From and To follow it at once
    with st.form("addedge"):
        source = str(st.selectbox("From", [r for r in refs if (kind == "binds") == split_out(r)] or refs))
        target = str(st.selectbox("To", [r for r in refs if (kind == "binds") == split_in(r) or (kind == "triggers" and r.endswith(".trigger"))] or refs))
        if st.form_submit_button("Add edge"):
            if attempt(lambda: editor.add_edge(source, str(target), str(kind)), "edge added"):
                st.rerun()


def split_out(ref: str) -> bool:
    return ref.partition(".")[2].startswith("out_")


def split_in(ref: str) -> bool:
    return ref.partition(".")[2].startswith("in_")


def problems_tab(editor: GraphEditor) -> None:
    errors, warnings = editor.problems()
    if not errors:
        st.success("valid: no errors" + (f", {len(warnings)} warning(s)" if warnings else ""))
    for e in errors:
        st.error(e)
    for w in warnings:
        st.warning(w)


def run_tab(editor: GraphEditor) -> None:
    inputs = editor.data()["workflow"].get("inputs", [])
    spec = ws.llm_spec(ui.settings())
    # the model from Settings comes first (a real run is always capped below); the dry run is the other choice
    adapter = str(st.selectbox("LLM", [spec, "mock"], key="run_adapter", format_func=lambda a: "dry run: placeholder answers, no model" if a == "mock" else a,
                               help=f"a dry run answers every model step with placeholder text; {spec} (from Settings) makes real, billed model calls"))
    max_calls = None
    if adapter != "mock":
        max_calls = int(st.number_input("Most model calls", 1, 200, 10, key="run_max_calls",
                                        help="the run stops with an error when it would make more calls than this; every GENERATE node is a call, and a loop repeats it"))
        st.caption("This runs the graph as it is now with a real model: billed calls, at most the number above.")
    params = {}
    for p in inputs:
        default = p.get("default")
        params[p["name"]] = st.text_input(f"{p['name']} ({p.get('type', 'TEXT')})", "" if default is None else str(default), key=f"run_in_{p['name']}")
    programs = ws.program_nodes(editor.data())
    acknowledged = True
    if programs:
        st.warning("Running this graph runs programs on your computer, whichever model you choose:\n\n" + "\n".join(f"- {p}" for p in programs)
                   + "\n\nRead them first (the Source tab, and the files next to the graph).")
        acknowledged = st.checkbox("I have read them: run anyway", value=True, key="run_ack_code")     # ticked by default: the warning above stays, one click less
    if st.button("Run", key="run_go", disabled=not acknowledged):
        with st.spinner("running"):
            name, _, model = adapter.partition(":")
            st.session_state["run_result"] = editor.run({k: v for k, v in params.items() if v != ""}, adapter=name, model=model or None, max_calls=max_calls, save=adapter != "mock")     # real runs are kept in output/; a dry run is not
            st.session_state.pop("logs_pick", None)
    result = st.session_state.get("run_result")
    if not result:
        return
    if not result["ok"]:
        st.error(result["error"])
        return
    st.success(f"{result['summary']['steps']} steps; the result is in the Logs tab")


def show_result(value) -> None:
    """Text is shown as text (markdown renders it); anything structured is shown as YAML, which reads better than JSON."""
    if isinstance(value, str):
        st.markdown(value)
    else:
        st.code(yaml.safe_dump(value, sort_keys=False, allow_unicode=True, default_flow_style=False), language="yaml")


def logs_tab(editor: GraphEditor) -> None:
    """The last run, made readable: inputs, outputs, what each node produced, the time per node and the model's usage."""
    past = runs.run_folders(editor.path)
    latest = st.session_state.get("run_result")
    options = (["latest"] if latest else []) + [str(f) for f in past]
    if not options:
        st.caption("Nothing has run yet. Use the Run tab; real runs are kept in the `output/` folder beside the graph and listed here.")
        return
    pick = st.selectbox("Run", options, key="logs_pick", format_func=lambda o: "Latest run (this session)" if o == "latest" else runs.label(Path(o)),
                        help="runs saved in the output folder beside this graph, newest first (dry runs are not saved)")
    result = latest if pick == "latest" else runs.load_run(Path(pick))
    if not result["ok"]:
        st.error(result["error"])
        return
    summary = result["summary"] or {"steps": "?", "nodes": {}}
    st.success(f"{summary['steps']} steps")
    if result.get("inputs"):
        with st.expander("Inputs"):
            show_result(result["inputs"])
    st.markdown("#### Output")
    for name, value in (result["outputs"] or {}).items():
        st.markdown(f"**{name}**")
        show_result(value)
    produced = result.get("values") or {}
    if produced:
        st.markdown("#### Step by step")
        for node, ports in produced.items():
            with st.expander(node):
                for port, value in ports.items():
                    st.caption(port)
                    show_result(value)
    st.markdown("#### Time per node")
    st.dataframe([{"node": k, "fired": v["n"], "ms": v["ms"]} for k, v in summary["nodes"].items()], hide_index=True)
    if summary.get("llm"):
        with st.expander("Model usage"):
            show_result(summary["llm"])


def clone_box(editor: GraphEditor, original: str, dirty: bool) -> None:
    """Edit a copy instead of the file itself: the copy is made from the saved file, in the same folder, and never overwrites anything."""
    cloned = editor.path.resolve() != Path(original).resolve()
    if cloned:
        st.caption(f"editing a copy of {Path(original).name}")
        if st.button(f"Back to {Path(original).name}", key="back", disabled=dirty):
            st.session_state.pop("target", None)
            forget_widgets()
            st.rerun()
    with st.expander("Clone"):
        stem = editor.path.name.removesuffix(".graph.yaml").removesuffix(".yaml")
        name = st.text_input("Name of the copy", f"{stem}-copy.graph.yaml", key="clone_name")
        if dirty:
            st.caption("Save or undo your edits first: the copy is made from the saved file.")
        if st.button("Clone and edit the copy", key="clone", disabled=dirty):
            try:
                new = editor.clone(name)
            except (EditError, OSError) as e:
                st.session_state["flash"] = ("error", str(e))
            else:
                st.session_state["target"] = str(new)
                st.session_state["flash"] = ("success", f"now editing {new.name}; {editor.path.name} is untouched")
                forget_widgets()
            st.rerun()


def open_box(workspace: ws.Workspace, current: "Path | None" = None) -> None:
    """Browse the work area: pick a recipe, then any `*.graph.yaml` in it, including those in sub-folders (parts, sub-graphs)."""
    with st.expander("Browse files", expanded=False):
        folders = {}
        for r in workspace.recipes():
            folders.setdefault(r.folder, r)
        here = workspace.recipe_folder(current) if current is not None else None
        if here is not None and here not in folders and here.is_dir() and ws.graphs_in(here):
            folders[here] = ws.Recipe("here", here, ws.graphs_in(here)[0], True)
        if not folders:
            st.caption("No recipes yet: create one, import one, or install the cookbook (Import / Export page).")
            return
        order = [r.name for r in workspace.roots] + ["here"]                    # "here": the open file's own folder when it is outside the work area
        present = [n for n in order if any(x.root == n for x in folders.values())]
        shown = st.multiselect("Folders", present, default=present, key="open_roots", help="show only the recipes of these folders")
        names = {f"{r.root}/{folder.name}" + ("" if r.writable else "  (shipped, read-only)"): folder for folder, r in folders.items() if r.root in shown}
        if not names:
            st.caption("No recipe in the folders chosen.")
            return
        labels = list(names)
        start = next((i for i, f in enumerate(names.values()) if f == here), 0)
        folder = names[str(st.selectbox("Recipe", labels, index=start, key="open_pick"))]
        graphs = ws.graphs_in(folder)
        files = {g.relative_to(folder).as_posix(): g for g in graphs}
        file_start = next((i for i, g in enumerate(files.values()) if current is not None and g.resolve() == Path(current).resolve()), 0)
        picked = files[str(st.selectbox("File", list(files), index=file_start, key="open_file",
                                        help="graphs in sub-folders, such as sub_graph/, are listed too"))]
        if ui.unsaved():
            st.caption("Save or undo your edits first: opening another file would drop them.")
        if st.button("Open", key="open_go", disabled=ui.unsaved()):
            open_graph(str(picked))
            st.rerun()


open_graph = ui.open_graph


def edit_chat(editor: GraphEditor, folder: Path, scope: str, staged: dict) -> None:
    """Ask for a change in words: the model answers with operations, which go through the editor like the buttons do (all or none)."""
    st.markdown("### Ask for a change")
    ui.show_chat(scope)
    value = ui.chat_box("edit", "e.g. make the critique stricter", history=scope)
    text, files = attachments.unpack(value)
    if not (text or files):
        return
    found, notes = attachments.read(files)
    history = ui.chat_history(scope)
    history.append({"role": "user", "content": (text or "(see the attachment)") + attachments.listing(found)})
    history.extend({"role": "assistant", "content": f"I did not use {note}"} for note in notes)
    request = attachments.with_documents(text or "Use the attached material for the change.", found)
    pictures = attachments.images(found)
    try:
        llm, _, model = ui.new_llm(1)
        prompt = chat_ops.build_prompt(editor.source(), chat_ops.prompt_files(folder, staged), request, NODE_TYPES)
        with st.spinner("asking the model (one billed call)"):
            say, ops = chat_ops.parse_reply(llm.generate(prompt, model=model, **({"images": pictures} if pictures else {})))
        done = chat_ops.apply_ops(editor, ops, staged)
    except (EditError,) + ui.CHAT_ERRORS as e:
        history.append({"role": "assistant", "content": f"I could not apply that: {e}"})
    else:
        history.append({"role": "assistant", "content": (say or "Done.") + "".join(f"\n- {d}" for d in done) + ("\n\nNot saved yet: check it, then Save, or Undo." if done else "")})
        forget_widgets()
    st.rerun()


def edit_page() -> None:
    workspace = ui.current_workspace()
    ui.settings()
    opened = st.session_state.get("opened")
    if not opened:
        st.header("Edit")
        st.info("Open a recipe: pick one under *Browse files* in the sidebar, or create, import or install some on the other pages.")
        with st.sidebar:
            open_box(workspace)
        return
    target = st.session_state.get("target") or opened          # a clone, once one has been made
    path = Path(target)
    if workspace.is_shipped(path):
        st.header(workspace.recipe_folder(path).name)
        st.info("This is a shipped recipe and is read-only. Copy it to your apps first; the copy is the one you edit and the original stays as it is.")
        if ui.unsaved():
            st.caption("Save or undo your edits to the other file first.")
        if st.button("Copy to my apps and edit", type="primary", key="copy_shipped", disabled=ui.unsaved()):
            try:
                folder = workspace.recipe_folder(path)
                new = ws.clone_recipe(folder, workspace.write_root, ws.free_name(workspace.write_root, folder.name))
            except (ws.WorkspaceError, OSError) as e:
                st.error(str(e))
            else:
                open_graph(str(new / path.resolve().relative_to(folder)))
                st.session_state["flash"] = ("success", f"copied to {new}")
                st.rerun()
        try:
            ui.show_graph(load_graph(path))
        except (ValueError, OSError) as e:
            st.warning(f"cannot draw the graph: {e}")
        with st.sidebar:
            open_box(workspace, path)
        return
    if st.session_state.get("file") != target:
        try:
            st.session_state["editor"], st.session_state["file"] = GraphEditor(path), target
        except EditError as e:
            st.error(str(e))
            with st.sidebar:
                open_box(workspace, path)
            return
    editor: GraphEditor = st.session_state["editor"]
    staged = st.session_state.setdefault(f"staged_{target}", {})
    dirty = editor.changed or bool(staged)

    with st.sidebar:
        st.markdown(f"### {path.name}")
        st.caption(("unsaved changes" if dirty else "saved") + " · " + str(path.resolve().parent))
        if getattr(editor, "compact_origin", False):
            st.caption("short `steps:` form: it stays short when you save (comments in the file are not kept)")
        errors, _ = editor.problems()
        save_col, undo_col, reload_col = st.columns([1, 1, 2.2])
        if save_col.button("Save", type="primary", disabled=not dirty or bool(errors), key="save"):
            def save_all():
                editor.save()
                chat_ops.write_staged(path.parent, staged)
                staged.clear()
            if attempt(save_all, "saved"):
                st.rerun()
        if undo_col.button("Undo", key="undo", disabled=not editor.can_undo):
            editor.undo()
            forget_widgets()
            st.rerun()
        if reload_col.button("Reload", key="reload", disabled=dirty, help="Reload from disk. Off while there are unsaved edits: save or undo them first." if dirty else "Reload from disk"):
            st.session_state.pop("file")
            st.rerun()
        if errors:
            st.caption(f"{len(errors)} error(s): fix them to save")
        if staged:
            st.caption("with the graph, Save also writes: " + ", ".join(sorted(staged)))
            if st.button("Discard the prompt changes", key="discard_staged"):
                staged.clear()
                st.rerun()
        view_box()
        clone_box(editor, opened, dirty)
        open_box(workspace, path)
        edit_chat(editor, path.parent, f"edit_{target}", staged)

    flash = st.session_state.pop("flash", None)
    if flash:
        (st.success if flash[0] == "success" else st.error)(flash[1])

    show_graph, show_panel = st.session_state.get("show_graph", True), st.session_state.get("show_panel", True)
    if show_graph and show_panel:
        left, right = st.columns([60, 40], gap="small")
    else:
        left = right = st.container()                  # one of them: it gets the whole width
    if show_graph:
        with left:
            picture(editor)
    if show_panel:
        with right:
            panel(editor)


def panel(editor: GraphEditor) -> None:
    tabs = st.tabs(["Source", "Node", "Add node", "Edges", "Problems", "Run", "Logs"])
    for tab, body in zip(tabs, (source_tab, node_tab, add_tab, edge_tab, problems_tab, run_tab, logs_tab)):
        with tab:
            body(editor)


def _keep_one_shown() -> None:
    """Turning both off would leave an empty page: the graph comes back."""
    if not st.session_state.get("show_graph", True) and not st.session_state.get("show_panel", True):
        st.session_state["show_graph"] = True


def view_box() -> None:
    """What the page shows: the graph, the editor tabs, or both side by side (at least one of them)."""
    st.session_state.setdefault("show_graph", True)
    st.session_state.setdefault("show_panel", True)
    graph_col, panel_col = st.columns(2)
    graph_col.toggle("Graph", key="show_graph", on_change=_keep_one_shown, help="the picture of the workflow")
    panel_col.toggle("Editor", key="show_panel", on_change=_keep_one_shown,
                     help="the tabs (Source, Node, Run, Logs, ...); turn the graph off to give them the whole width")

if __name__ == "__main__":                # Streamlit runs a page file as a script; tests import the functions
    edit_page()
