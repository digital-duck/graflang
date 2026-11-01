"""The app behind `graf vis --edit [FILE] [--src-dir DIR]` (Streamlit; `pip install 'graflang[edit]'`): six pages in pages/ (00-welcome, 01-create, 02-edit,
04-browse, 80-transfer, 99-settings), each a Streamlit page file; the number orders them. This entry script sets up the work area and the navigation.

`graf vis --edit` sets GRAF_EDIT_FILE (the file to open, optional) and GRAF_SRC_DIR (the work area instead of ~/.graflang/cookbook and
apps, optional).
"""
import os
from pathlib import Path

import streamlit as st

from graphlang import workspace as ws

PAGES = Path(__file__).with_name("pages")
LOOK = {"welcome": ("Welcome", ":material/home:"), "create": ("Create", ":material/auto_awesome:"), "edit": ("Edit", ":material/edit:"), "settings": ("Settings", ":material/settings:"),
        "transfer": ("Import / Export", ":material/swap_vert:"), "browse": ("Browse", ":material/search:")}


def main() -> None:
    st.set_page_config(page_title="GraphLang", layout="wide")
    if "workspace" not in st.session_state:
        src = os.environ.get("GRAF_SRC_DIR")
        st.session_state["workspace"] = ws.Workspace(Path(src).expanduser().resolve() if src else None)
        if os.environ.get("GRAF_EDIT_FILE"):
            st.session_state["opened"] = os.environ["GRAF_EDIT_FILE"]
    pages = {}
    landing = "edit" if os.environ.get("GRAF_EDIT_FILE") else "welcome"      # a file given on the command line opens straight on the Edit page
    for path in sorted(PAGES.glob("[0-9]*-*.py")):                # 00-welcome.py, 01-create.py ...: the number orders the pages
        stem = path.stem.partition("-")[2]
        title, icon = LOOK.get(stem, (stem.replace("_", " ").title(), ":material/description:"))
        pages[stem] = st.Page(str(path), title=title, url_path=stem, icon=icon, default=stem == landing)
    st.session_state["pages"] = pages
    st.navigation(list(pages.values())).run()


main()
