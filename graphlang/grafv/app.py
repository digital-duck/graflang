"""The editor behind `graf vis --edit FILE` (a Streamlit app; `pip install 'graflang[edit]'`).

The picture is the same cytoscape view `graf vis` writes. Editing goes through `GraphEditor`: nothing is written until Save, Save
refuses while `graf validate` reports errors, comments in the file are kept, and every edit can be undone. The file to edit comes
from the GRAF_EDIT_FILE environment variable (set by `graf vis --edit`).
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from ruamel.yaml import YAML

from graphlang.grafr.runtime import SCHEMA_PATH
from graphlang.grafv.editor import EditError, GraphEditor
from graphlang.grafv.engines import render

NODE_TYPES = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))["properties"]["nodes"]["items"]["properties"]["type"]["enum"]
_yaml = YAML(typ="safe")


def parse_value(text: str):
    """What a person typed in a config box: YAML, so 3 is a number, [a, b] a list, plain words a string."""
    return _yaml.load(text) if text.strip() else None


def show_value(value) -> str:
    if isinstance(value, str) and "\n" not in value:
        return value
    import io
    buf = io.StringIO()
    YAML(typ="safe").dump(value, buf)
    return buf.getvalue().rstrip()


def forget_widgets() -> None:
    """A text box keeps what was typed in it; after an edit or an undo the boxes must show the file's state again."""
    for key in [k for k in st.session_state if str(k).startswith(("cfg_", "ports_", "rename_"))]:
        del st.session_state[key]


def attempt(action, success: str = "") -> bool:
    try:
        action()
    except (EditError, ValueError) as e:
        st.session_state["flash"] = ("error", str(e))
        return False
    forget_widgets()
    if success:
        st.session_state["flash"] = ("success", success)
    return True


def picture(editor: GraphEditor) -> None:
    graph = editor.data()
    with tempfile.TemporaryDirectory() as tmp:
        try:
            path, _, _ = render(graph, Path(tmp) / "view.html", "cytoscape")
            html = path.read_text(encoding="utf-8")
            if hasattr(st, "iframe"):                                  # newer Streamlit; components.html is being removed
                st.iframe(html, height=620)
            else:
                components.html(html, height=620, scrolling=True)
        except (ValueError, RuntimeError) as e:
            st.warning(f"cannot draw the graph yet: {e}")


def node_tab(editor: GraphEditor) -> None:
    ids = editor.node_ids()
    if not ids:
        st.info("no nodes yet")
        return
    node_id = str(st.selectbox("Node", ids, key="node_pick"))
    node = editor.node(node_id)
    st.caption(f"type **{node['type']}**")
    ports = st.text_input("Ports (comma separated)", ", ".join(node["ports"]), key=f"ports_{node_id}")
    if ports != ", ".join(node["ports"]) and st.button("Set ports", key=f"setports_{node_id}"):
        if attempt(lambda: editor.set_ports(node_id, [p.strip() for p in ports.split(",") if p.strip()]), "ports changed"):
            st.rerun()
    st.markdown("**Config**")
    for key, value in (node.get("config") or {}).items():
        text = st.text_area(key, show_value(value), key=f"cfg_{node_id}_{key}", height=68 if "\n" not in show_value(value) else 160)
        left, right = st.columns(2)
        if text != show_value(value) and left.button("Set", key=f"set_{node_id}_{key}"):
            if attempt(lambda: editor.set_config(node_id, key, parse_value(text)), f"{key} changed"):
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
    with st.form("addedge"):
        kind = st.radio("Type", ["triggers", "binds"], horizontal=True)
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


def main() -> None:
    st.set_page_config(page_title="GraphLang editor", layout="wide")
    target = os.environ.get("GRAF_EDIT_FILE")
    if not target:
        st.error("Start this with `graf vis --edit FILE`.")
        return
    if st.session_state.get("file") != target:
        try:
            st.session_state["editor"], st.session_state["file"] = GraphEditor(Path(target)), target
        except EditError as e:
            st.error(str(e))
            return
    editor: GraphEditor = st.session_state["editor"]

    with st.sidebar:
        st.markdown(f"### {Path(target).name}")
        st.caption(("unsaved changes" if editor.changed else "saved") + " · " + str(Path(target).resolve().parent))
        errors, _ = editor.problems()
        if st.button("Save", type="primary", disabled=not editor.changed or bool(errors), key="save"):
            if attempt(editor.save, "saved"):
                st.rerun()
        if errors:
            st.caption(f"{len(errors)} error(s): fix them to save")
        if st.button("Undo", key="undo", disabled=not editor._undo):
            editor.undo()
            forget_widgets()
            st.rerun()
        if st.button("Reload from disk", key="reload"):
            st.session_state.pop("file")
            st.rerun()

    flash = st.session_state.pop("flash", None)
    if flash:
        (st.success if flash[0] == "success" else st.error)(flash[1])

    left, right = st.columns([3, 2])
    with left:
        picture(editor)
    with right:
        tabs = st.tabs(["Node", "Add node", "Edges", "Problems"])
        for tab, body in zip(tabs, (node_tab, add_tab, edge_tab, problems_tab)):
            with tab:
                body(editor)


main()
