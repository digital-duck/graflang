"""Pieces the editor's pages share: the saved LLM settings, a metered LLM from them, and the picture of a graph."""
from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import streamlit as st
import streamlit.components.v1 as components

from .. import workspace as ws
from ..grafr.runtime import load_graph
from . import attachments
from .engines import render


PICTURE_LAYOUT = "grid"          # the arrangement the picture starts on (the selector above it offers the others)
CHAT_ERRORS = (RuntimeError, ValueError, ImportError, OSError)     # what a model call or a missing package raises (LLMUnavailable, LimitExceeded are RuntimeErrors)


@dataclass
class Message:
    """What the chat box hands back: the text typed and the files attached (`attachments.unpack` reads it)."""
    text: str
    files: List = field(default_factory=list)


def chat_box(key: str, placeholder: str, history: Optional[str] = None) -> Optional[Message]:
    """A two-line message box. Under it one row: Send, Clear (empties the chat history `history`, default `key`) and Upload (a
    popover with the file chooser). Ctrl+Enter sends too, and the box empties when sent. Returns the message in the run where
    it was sent, else None. Widget keys: `{key}_text`, `{key}_files`, `{key}_send`, `{key}_clear`."""
    with st.form(f"{key}_form", clear_on_submit=True, border=False):
        text = st.text_area("Message", key=f"{key}_text", height=68, placeholder=placeholder, label_visibility="collapsed")
        send_col, clear_col, upload_col = st.columns([1, 1, 1.3])
        sent = send_col.form_submit_button("Send", key=f"{key}_send", type="primary")
        cleared = clear_col.form_submit_button("Clear", key=f"{key}_clear", help="empty the chat above (the app and its files stay)")
        with upload_col.popover("Upload", help="attach a screenshot or a document (text, markdown, YAML, JSON, CSV, code)"):
            files = st.file_uploader("Attach files", key=f"{key}_files", accept_multiple_files=True, type=attachments.FILE_TYPES)
    if cleared:
        st.session_state[f"chat_{history or key}"] = []
        st.rerun()
    text = (text or "").strip()
    return Message(text, list(files or [])) if sent and (text or files) else None


def settings() -> dict:
    """The saved settings, read once per session; their keys are put in the environment (a variable already set there wins)."""
    if "settings" not in st.session_state:
        st.session_state["settings"] = ws.load_settings()
        ws.apply_settings(st.session_state["settings"])
    return st.session_state["settings"]


def current_workspace() -> ws.Workspace:
    return st.session_state["workspace"]


def new_llm(max_calls: int):
    """The model the settings choose, counted and capped at `max_calls` (every call is billed). Tests replace this function."""
    from ..grafr.adapters import make_llm
    from ..grafr.metering import MeteredLLM
    from dd_llm.models import parse_llm_spec
    adapter, model = parse_llm_spec(ws.llm_spec(settings()))
    return MeteredLLM(make_llm(adapter, model), max_calls=max_calls), adapter, model


def canvas_height() -> int:
    """The picture's height in pixels, from the Settings page (a page cannot read the window's height, so the person sets it)."""
    return int(settings().get("canvas_height", ws.DEFAULT_CANVAS))


@st.cache_data(show_spinner=False, max_entries=64)
def _graph_html(graph_json: str) -> str:
    """The picture's page for a graph, made once per distinct graph (every click of the app reruns the script)."""
    with tempfile.TemporaryDirectory() as tmp:
        path, _, _ = render(json.loads(graph_json), Path(tmp) / "view.html", "cytoscape", default_layout=PICTURE_LAYOUT)
        return path.read_text(encoding="utf-8")


def show_graph(graph: Dict, height: "int | None" = None) -> None:
    height = height or canvas_height()
    try:
        html = _graph_html(json.dumps(graph, sort_keys=True, default=str))
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as e:      # also a missing graphviz program
        st.warning(f"cannot draw the graph yet: {e}")
        return
    if hasattr(st, "iframe"):                                      # newer Streamlit; components.html is being removed
        st.iframe(html, height=height)
    else:
        components.html(html, height=height, scrolling=True)


def draft_graph(name: str, files: Dict[str, str]) -> Optional[Dict]:
    """The loaded (expanded) graph of an app that is only in memory; None when it does not load yet."""
    with tempfile.TemporaryDirectory() as tmp:
        for rel, text in files.items():
            target = Path(tmp) / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        try:
            return load_graph(Path(tmp) / f"{name}.graph.yaml")
        except (ValueError, OSError, KeyError):
            return None


def chat_history(scope: str) -> list:
    return st.session_state.setdefault(f"chat_{scope}", [])


CHAT_HEIGHT = 380                 # pixels; a longer thread scrolls inside its box instead of pushing the page down


def show_chat(scope: str) -> None:
    messages = chat_history(scope)
    if not messages:
        return
    with st.container(height=CHAT_HEIGHT, key=f"chat_box_{scope}", autoscroll=True):       # scrolls; follows the newest message
        for message in messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])


def recipe_index(rebuild: bool = False):
    """The search index over the work area, rebuilt when a recipe file or the embedding setting changes (or when asked to)."""
    from .. import embedding
    from ..recipe_index import RecipeIndex
    workspace = current_workspace()
    spec = str(settings().get("embedding") or "auto")
    signature = (RecipeIndex.signature(workspace), spec)
    cached = st.session_state.get("recipe_index")
    if rebuild or cached is None or cached[0] != signature:
        embedder, note = embedding.resolve(spec)
        st.session_state["recipe_index"] = (signature, RecipeIndex.build(workspace, embedder, note))
    return st.session_state["recipe_index"][1]


def forget_widgets() -> None:
    """A text box keeps what was typed in it; after an edit, an undo or a new file the boxes must show the file's state again."""
    for key in [k for k in st.session_state if str(k).startswith(("cfg_", "ports_", "rename_", "source_"))]:
        del st.session_state[key]


def open_graph(path: str) -> None:
    """Make `path` the file the Edit page shows."""
    st.session_state["opened"] = path
    for key in ("target", "file", "run_result"):
        st.session_state.pop(key, None)
    forget_widgets()


def unsaved() -> bool:
    """The Edit page holds changes that are not saved (graph edits or staged prompt files): opening another file would drop them."""
    editor, file = st.session_state.get("editor"), st.session_state.get("file")
    return file is not None and editor is not None and bool(editor.changed or st.session_state.get(f"staged_{file}"))
