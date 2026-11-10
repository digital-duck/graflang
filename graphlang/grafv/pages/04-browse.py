"""The Browse page: search the recipes of the work area (the shipped cookbook and your apps) by what they do, look inside, open one on the
Edit page, or use one as the starting point of a new app on the Create page.

The search is `graphlang.recipe_index`: words in a recipe's name, description, readme, node types, inputs and prompts, and (when an
embedding model is set up) their meaning. It makes no billed call.
"""
from __future__ import annotations

import streamlit as st

from graphlang.grafr.runtime import load_graph
from graphlang.grafv import ui


def _badges(e) -> str:
    bits = ["shipped" if e.shipped else "mine"]
    bits += [f"`{t}`" for t in e.tags if t not in ("programs",)]
    bits.append(f"~{e.llm_calls} model call(s)" if e.llm_calls else "no model call")
    if e.has_code:
        bits.append("**runs programs**")
    return " · ".join(bits)


def browse_page() -> None:
    ui.settings()
    index = ui.recipe_index()
    st.header("Browse")
    if not index.entries:
        st.info("No recipes yet. Install the cookbook on the Import / Export page, or create an app on the Create page.")
        return
    with st.sidebar:                                    # the filters live in the sidebar; the page is the search and the cards
        where = sorted({e.root for e in index.entries})
        default = ["apps"] if "apps" in where else where        # your apps first: a card per shipped recipe too makes the page slow
        roots = st.multiselect("Where", where, default=default, key="browse_roots",
                               help="the folders of the work area to list and search; add more to see the shipped recipes")
        no_code = st.checkbox("Only recipes that run no programs", key="browse_no_code")
        hidden = {r: sum(1 for e in index.entries if e.root == r) for r in where if r not in roots}
        if hidden:
            st.info(f"**{sum(hidden.values())} more recipes** to browse in "
                    + ", ".join(f"{r} ({n})" for r, n in hidden.items()) + ": add them under **Where**.")
        if st.button("Refresh", key="browse_refresh", help="look for an embedding model again and re-read the recipes"):
            ui.recipe_index(rebuild=True)
            st.rerun()
    query = st.text_input(f"Search the recipes · {index.note}", key="browse_query",
                          placeholder="e.g. write and test code, check personal data, loop until it passes")
    if query.strip():
        hits = index.search(query, k=8, allow_code=not no_code, roots=roots)
        st.caption(f"{len(hits)} recipe(s) close to the request" if hits else "No recipe is close to that. Try other words, or browse everything by clearing the search.")
        rows = [(h.entry, h.matched, h.meaning) for h in hits]
    else:
        listed = [e for e in index.listing(roots=roots) if not (no_code and e.has_code)]
        st.caption(f"{len(listed)} recipe(s)")
        rows = [(e, [], None) for e in listed]

    for i, (e, matched, meaning) in enumerate(rows):
        with st.container(border=True):
            st.markdown(f"**{e.title}**  ·  `{e.key}`")
            st.markdown(_badges(e))
            if e.description:
                st.write(e.description[:400] + ("…" if len(e.description) > 400 else ""))
            io = []
            if e.inputs:
                io.append("takes " + ", ".join(f"`{x}`" for x in e.inputs))
            if e.outputs:
                io.append("gives " + ", ".join(f"`{x}`" for x in e.outputs))
            if io:
                st.caption(" · ".join(io))
            if matched or meaning is not None:
                st.caption((f"closeness {meaning:.2f}" if meaning is not None else "") + (" · " if matched and meaning is not None else "")
                           + ("shares words: " + ", ".join(matched) if matched else ""))
            if len(e.graphs) > 1:
                st.caption("files: " + ", ".join(e.graphs))
            a, b, c = st.columns([1, 1, 3])
            if a.button("Open", key=f"browse_open_{i}", disabled=ui.unsaved(), help=("The Edit page has unsaved changes: save or undo them first. " if ui.unsaved() else "") + "open its main graph on the Edit page (a shipped recipe is copied to your apps first); the other files are under Browse files there"):
                ui.open_graph(str(e.graph))
                st.switch_page(st.session_state["pages"]["edit"])
            if b.button("Use in Create", key=f"browse_seed_{i}", help="start a new app from this one: the Create chat shows it to the model as an example"):
                st.session_state["create_seed"] = e.key
                st.switch_page(st.session_state["pages"]["create"])
            with st.expander("Use as a part of another workflow"):
                try:
                    from graphlang.grafr.partinfo import describe, part_summary, use_snippet
                    info = part_summary(e.graph)
                    root = str(e.key).partition("/")[0] if "/" in str(e.key) else "cookbook"
                    root = root if root in ("apps", "cookbook", "solvers", "pocketflow") else "cookbook"
                    st.caption("It would " + describe(info["capabilities"]).replace("touches nothing outside", "touch nothing outside the graph"))
                    for io_ in info["inputs"] + info["outputs"]:
                        if io_.get("description"):
                            st.caption(f"`{io_['name']}`: {io_['description']}")
                    st.code(use_snippet(f"{root}:{e.graph.parent.name}", e.graph.parent.name, info), language="yaml")
                except (ValueError, OSError) as err:
                    st.caption(f"cannot read it as a part: {err}")
            with c.expander("Look inside"):
                if e.readme:
                    st.markdown(e.readme[:3000])
                if st.toggle("Show the picture", key=f"browse_pic_{i}", help="drawn on request: a picture for every card would slow the page"):
                    try:
                        ui.show_graph(load_graph(e.graph), height=420)
                    except (ValueError, OSError) as err:
                        st.caption(f"cannot draw it: {err}")


if __name__ == "__main__":                # Streamlit runs a page file as a script; tests import the function
    browse_page()
