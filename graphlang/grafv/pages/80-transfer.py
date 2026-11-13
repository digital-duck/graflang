"""The Import/Export page: bring recipes in (the cookbook, a shared zip, a lone graph file) and send your apps out as a zip or a file.

Nothing is run on the way in, and nothing is overwritten: a taken name is refused. An imported recipe that holds programs is listed
so you can read them before you run it; an exported one is checked for what looks like a key or token.
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from graphlang import workspace as ws
from graphlang.grafv import ui


def _report_code(folders) -> None:
    for folder in folders:
        notes = ws.scan_for_code(folder)
        if notes:
            st.warning(f"**{folder.name}** holds programs. Read them before you run it:\n\n" + "\n".join(f"- {n}" for n in notes))


def transfer_page() -> None:
    workspace = ui.current_workspace()
    ui.settings()
    st.header("Import / Export")
    cookbook_root = next(r.path for r in workspace.roots if r.name in ("cookbook", "src"))

    st.subheader("Install the cookbook")
    repo = ws.find_repo_cookbook()
    source = st.text_input("Folder with the recipes", str(repo) if repo else "", key="cookbook_source",
                           help="a folder of recipe folders, such as `cookbook/` in a graflang checkout")
    target_text = st.text_input("Install into (optional)", "", key="cookbook_target",
                                help="a folder name such as `solvers` (under ~/.graflang) or a path; empty: the cookbook folder. "
                                     "Only `cookbook`, `solvers` and `pocketflow` are listed by Browse and Edit")
    try:
        target = ws.install_target(target_text, cookbook_root)
    except ws.WorkspaceError as e:
        target = None
        st.error(str(e))
    st.caption(f"copied into {target or cookbook_root}; a recipe that is already there is left as it is")
    if st.button("Install", key="cookbook_install", disabled=not source.strip() or target is None):
        try:
            copied, skipped = ws.install_cookbook(Path(source.strip()).expanduser(), target)
        except (ws.WorkspaceError, OSError) as e:
            st.error(str(e))
        else:
            st.success(f"installed {len(copied)} recipe(s)" + (f", kept {len(skipped)} that were already there" if skipped else ""))

    st.divider()
    st.subheader("Import")
    st.caption(f"into {workspace.write_root}. A zip or `.tar.gz` made by Export (or a whole cookbook archive), or a single `*.graph.yaml` (without its prompts).")
    upload = st.file_uploader("A zip, a tar.gz or a graph file", type=["zip", "gz", "tgz", "tar", "yaml", "yml"], key="import_file")
    name = st.text_input("Name for it (optional)", "", key="import_name", help="the folder name; default: the name in the file")
    if st.button("Import", key="import_go", disabled=upload is None):
        try:
            data = upload.getvalue()
            if upload.name.endswith(".zip"):
                made = ws.import_zip(data, workspace.write_root, name.strip() or None)
            elif upload.name.endswith((".tar.gz", ".tgz", ".tar")):
                made = ws.import_tar(data, workspace.write_root, name.strip() or None)
            else:
                made = [ws.import_graph_file(data.decode("utf-8", errors="replace"), upload.name, workspace.write_root, name.strip() or None).parent]
        except (ws.WorkspaceError, OSError) as e:
            st.error(str(e))
        else:
            st.success("imported: " + ", ".join(p.name for p in made))
            _report_code(made)

    st.divider()
    st.subheader("Export")
    recipes = workspace.recipes()
    if not recipes:
        st.info("No recipes yet.")
        return
    labels = {r.label: r for r in recipes}
    picked = labels[str(st.selectbox("Recipe", list(labels), key="export_pick"))]
    secrets = ws.find_secrets(picked.folder)
    if secrets:
        st.warning("These files look like they hold a key or a token; check them before you share this recipe:\n\n" + "\n".join(f"- {s}" for s in secrets))
    st.download_button("Download the recipe (zip: graph, prompts, procedures)", ws.export_zip(picked.folder), file_name=f"{picked.folder.name}.zip",
                       mime="application/zip", key="export_zip")
    st.download_button("Download only the graph file", picked.graph.read_bytes(), file_name=picked.graph.name, mime="text/yaml", key="export_graph")
    st.caption("Run output (`output/`), caches and hidden files are left out. Your API keys are in `settings.json`, which is never part of a recipe.")


if __name__ == "__main__":                # Streamlit runs a page file as a script; tests import the function
    transfer_page()
