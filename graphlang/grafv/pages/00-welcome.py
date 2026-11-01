"""The Welcome page: what GraphLang is, what this app offers, and where to start."""
from __future__ import annotations

import streamlit as st

from graphlang import workspace as ws
from graphlang.grafv import ui

FEATURES = [
    ("create", "Create", "Describe a workflow app in a chat and the model writes it: the graph, its prompts and a readme. It is checked "
                         "like `graf validate` plus a dry run before you see it. Ask for changes, undo them, and save when you are happy. "
                         "Attach a screenshot or a document as part of the request."),
    ("edit", "Edit", "Open any recipe: the graph is drawn, and you change it with forms (nodes, ports, config, edges), with the chat, "
                     "or as text in the Source tab (a code editor). Every edit is validated, keeps your comments, can be undone, "
                     "and nothing is written until Save. Clone before you experiment."),
    ("browse", "Browse", "Search the recipes by what they do, in your own words. One card per recipe, found by meaning (with an embedding "
                         "model) and by words. Open one, or use it as the starting point of a new app."),
    ("transfer", "Import / Export", "Install the cookbook, import a recipe someone shared (a zip or a graph file; nothing is run on import), "
                                    "or export yours."),
    ("settings", "Settings", "Pick the provider and model the chats use, enter API keys, choose the embedding model for search "
                             "and set the size of the picture."),
]


def _link(key: str, label: str) -> None:
    pages = st.session_state.get("pages", {})
    page = pages.get(key)
    if page is not None and not isinstance(page, str):
        st.page_link(page, label=f"Open {label}")


def welcome_page() -> None:
    workspace = ui.current_workspace()
    settings = ui.settings()
    st.title("GraphLang")
    st.markdown("##### A graph-first language for agentic workflows")
    st.write(
        "In GraphLang the **graph is the program**. A workflow is a `*.graph.yaml` file: typed nodes (an LLM that generates, a rule that "
        "decides, a program that computes, a loop, a guard) joined by control and data edges. You read it, draw it, validate it and run it "
        "with `graf`. Because the workflow is data, a model can *change the graph* (add a step, rewire a branch) and the change is checked "
        "before it is applied, instead of rewriting code.")
    left, right = st.columns(2)
    with left:
        st.markdown("**What a workflow can use**")
        st.markdown(
            "- `GENERATE`: ask a model, each node can choose its own provider and model\n"
            "- `SOLVE`, `EVALUATE`, `ASSERT`: deterministic steps and checks, including a Python kernel and external programs\n"
            "- `LOOP`, `FORK` / `JOIN`: repeat until a condition, or run branches in parallel\n"
            "- `GUARD`: a [Cedar](https://www.cedarpolicy.com/) policy decides before anything risky happens\n"
            "- parts: a named subgraph used as one node")
    with right:
        st.markdown("**Deterministic where it matters**")
        st.write(
            "The model reads and writes language; rules, solvers and policies decide. The `compliance_audit` recipe, for example, lets a model "
            "list the personal data in a document and a rule engine (plain Python, sympy or z3) decide whether it may be released. "
            "GraphLang is an early prototype: some of its larger ideas are not built yet.")

    st.divider()
    st.subheader("What this app offers")
    for key, label, text in FEATURES:
        with st.container(border=True):
            columns = st.columns([1, 4, 1])
            columns[0].markdown(f"**{label}**")
            columns[1].write(text)
            with columns[2]:
                _link(key, label)

    st.divider()
    st.subheader("Where you are")
    recipes = {r.folder for r in workspace.recipes()}
    shipped = {r.folder for r in workspace.recipes() if not r.writable}
    a, b, c = st.columns(3)
    a.metric("Recipes", len(recipes), help="folders with a *.graph.yaml in the work area")
    b.metric("Your apps", len(recipes) - len(shipped))
    c.metric("Model for the chats", ws.llm_spec(settings))
    st.caption("Work area: " + ", ".join(f"`{r.path}`" for r in workspace.roots) + ". Settings are in `~/.graflang/settings.json` (or `$GRAFLANG_HOME`).")
    if not recipes:
        st.info("The work area has no recipes yet. Install the shipped cookbook on the **Import / Export** page, or describe an app on the "
                "**Create** page.")
    else:
        st.success("Start by browsing the recipes, or by describing the app you want on the Create page.")
    with st.expander("The command line"):
        st.code("graf run  RECIPE.graph.yaml --param key=value   # run a workflow (a real model is billed; give a --bind file with limits)\n"
                "graf validate RECIPE.graph.yaml                  # check it\n"
                "graf vis  RECIPE.graph.yaml                      # draw it\n"
                "graf create --name NAME --spec \"what it should do\"\n"
                "graf compile RECIPE.graph.yaml --lang spl       # write it as an SPL script", language="bash")


if __name__ == "__main__":                # Streamlit runs a page file as a script; tests import the function
    welcome_page()
