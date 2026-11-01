"""The Create page: describe a workflow app in the chat on the left, read and revise it, then save it to your apps.

The first message is the specification (what `graf create --spec` takes); every later message asks for a change. Nothing is written to
disk until Save, nothing generated is executed, and code in an app (programs, `RUN`) is refused unless you tick the box.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import streamlit as st

from graphlang import workspace as ws
from graphlang.grafc.create import CreateError, check_app, check_name, create_app, find_examples, revise_app, write_app
from graphlang.grafv import attachments, ui

KINDS = {".yaml": "yaml", ".yml": "yaml", ".md": "markdown", ".json": "json", ".py": "python", ".txt": "text"}


def _draft():
    return st.session_state.get("draft")


def _say(role: str, content: str) -> None:
    ui.chat_history("create").append({"role": role, "content": content})


def _name_ok(name: str) -> bool:
    try:
        check_name(name)
    except CreateError:
        return False
    return True


def _run_chat(text: str, name: str, allow_code: bool, rounds: int, images=None, references=None) -> None:
    draft = _draft()
    try:
        check_name(name)
        llm, adapter, model = ui.new_llm(rounds)
        with st.spinner("asking the model (each attempt is a billed call)"):
            if draft is None:
                created = create_app(name, text, llm, model, max_rounds=rounds, allow_code=allow_code, images=images, references=references)
                st.session_state["draft"] = {"name": name, "spec": text, "files": created.files, "created": created, "llm": f"{adapter}:{model or ''}",
                                             "previous": []}
            else:
                created = revise_app(name, text, draft["files"], llm, model, max_rounds=rounds, allow_code=allow_code, images=images)
                draft["previous"].append((draft["files"], draft["spec"]))     # one step of undo per revision
                draft.update(files=created.files, created=created, spec=draft["spec"] + f"\n\nChange: {text}")
    except (CreateError,) + ui.CHAT_ERRORS as e:
        _say("assistant", f"I could not do that: {e}")
        return
    usage = llm.snapshot()
    if created.ok:
        _say("assistant", f"Done in {created.rounds} attempt(s) ({usage['input_tokens']} tokens in / {usage['output_tokens']} out). Ask for a change, or save it.")
    else:
        _say("assistant", f"It still has {len(created.problems)} problem(s) after {created.rounds} attempt(s); see the list. Describe a fix, or edit it after saving.")


def create_page() -> None:
    workspace = ui.current_workspace()
    ui.settings()
    draft = _draft()
    with st.sidebar:
        st.markdown("### Describe your app")
        ui.show_chat("create")
        with st.expander("Settings for this chat"):
            name = st.text_input("App name", draft["name"] if draft else "", key="create_name", disabled=draft is not None,
                                 help="lower-case letters, digits, underscores; it names the graph file")
            allow_code = st.checkbox("Allow app to call external programs", key="create_allow_code",
                                     help="Off: the model may only use nodes that run no program. On: it may add programs (SOLVE with code, RUN). They are not run when created, only when you run the app.")
            rounds = st.slider("Most attempts per message", 1, 3, 3, key="create_rounds", help="each attempt is a real, billed model call")
            use_refs = st.checkbox("Show similar recipes to the model", value=True, key="create_use_refs",
                                   help="the best matches from your recipes (found like on the Browse page) go into the first request as examples")
        seed = st.session_state.get("create_seed")
        if seed and draft is None:
            st.caption(f"starting from `{seed}`")
            if st.button("Drop it", key="create_drop_seed"):
                st.session_state.pop("create_seed", None)
                st.rerun()
        st.caption(f"model: {ws.llm_spec(ui.settings())} (change it on the Settings page)")
        st.caption("📎 attach a screenshot or a document (text, markdown, YAML, JSON, CSV, code) with the + button")
        value = st.chat_input("What should the app do?" if draft is None else "What should change?", key="create_input",
                              accept_file="multiple", file_type=attachments.FILE_TYPES)
    text, files = attachments.unpack(value)
    if (text or files) and draft is None and not _name_ok(str(name)):
        _say("user", text or "(see the attachment)")
        _say("assistant", "Give the app a name first (under *Settings for this chat*: lower-case letters, digits, underscores), then send your message again.")
        st.rerun()
    if text or files:
        found, notes = attachments.read(files)
        _say("user", (text or "(see the attachment)") + attachments.listing(found))
        for note in notes:
            _say("assistant", f"I did not use {note}")
        request = attachments.with_documents(text or "Use the attached material as the specification.", found)
        references, used = ("", [])
        if draft is None and (use_refs or st.session_state.get("create_seed")):
            shown = find_examples(request, workspace, allow_code=bool(allow_code), chosen=st.session_state.get("create_seed"), index=ui.recipe_index())
            references, used = shown.text, shown.keys
            if used:
                _say("assistant", "Looking at similar recipes: " + ", ".join(f"`{k}`" for k in used))
            if shown.words_only:
                _say("assistant", f"Note: the examples were chosen by words only ({shown.note[len('words only'):].lstrip(': ') or 'no embedding model'}); "
                                  "they match better by meaning with an embedding model (Settings).")
        _run_chat(request, str(name), bool(allow_code), int(rounds), attachments.images(found), references or None)
        st.rerun()

    st.title("Create")
    if draft is None:
        st.info("Describe what the app should do in the chat, for example: *classify a support message as urgent or normal, then draft a reply*. "
                "Give it a name first (under *Settings for this chat*).")
        return
    created = draft["created"]
    st.subheader(draft["name"])
    for problem in created.problems:
        st.error(problem)
    for warning in created.warnings:
        st.warning(warning)
    if created.ok:
        st.success("This app checks out: it validates and its dry run works.")
    tabs = st.tabs(["Picture"] + list(draft["files"]))
    with tabs[0]:
        graph = ui.draft_graph(draft["name"], draft["files"])
        if graph is None:
            st.info("The graph does not load yet.")
        else:
            ui.show_graph(graph)
    for tab, (rel, body) in zip(tabs[1:], draft["files"].items()):
        with tab:
            st.code(body, language=KINDS.get(Path(rel).suffix, "text"), line_numbers=True)

    left, middle, right = st.columns(3)
    if left.button("Undo the last change", disabled=not draft["previous"], key="create_undo"):
        draft["files"], draft["spec"] = draft["previous"].pop()
        problems, warnings = check_app(draft["name"], draft["files"], allow_code=bool(allow_code))
        draft["created"] = replace(created, files=draft["files"], problems=problems, warnings=warnings)
        st.rerun()
    if middle.button("Start over", key="create_reset"):
        st.session_state.pop("draft", None)
        st.session_state.pop("chat_create", None)
        st.session_state.pop("saved_app", None)
        st.rerun()
    target = workspace.write_root / draft["name"]
    again = draft.get("saved_to") == str(target)               # this draft already wrote the folder: saving a revision replaces its files
    if right.button(f"Save again, replacing {draft['name']}/" if again else f"Save to {target.parent.name}/", type="primary", key="create_save",
                    help="Files you changed in this folder on the Edit page are overwritten." if again else None):
        try:
            write_app(draft["name"], draft["spec"], created, target, draft["llm"], force=again)
        except (CreateError, OSError) as e:
            st.error(str(e))
        else:
            draft["saved_to"] = str(target)
            st.session_state["saved_app"] = str(target / f"{draft['name']}.graph.yaml")
    saved = st.session_state.get("saved_app")
    if saved:
        st.success(f"Saved {saved}")
        st.caption("Next: open it on the Edit page to change it by hand or by chat, or run it with `graf run`.")
        if ui.unsaved():
            st.caption("The Edit page has unsaved changes: save or undo them there first.")
        if st.button("Open in the Edit page", key="create_open_edit", disabled=ui.unsaved()):
            ui.open_graph(saved)                                   # sets what the Edit page shows, also when it has not been opened before
            st.switch_page(st.session_state["pages"]["edit"])


if __name__ == "__main__":                # Streamlit runs a page file as a script; tests import the function
    create_page()
