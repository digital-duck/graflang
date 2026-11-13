"""The Settings page: which provider and model the Create and Edit pages use, and the API keys they need.

Keys are saved in `~/.graflang/settings.json`, readable by you only, and put in the environment of this editor. A key that is already
set in the real environment wins over the saved one. `claude_cli` and `gemini_cli` use their own CLI login and need no key here.
"""
from __future__ import annotations

import os

import streamlit as st

from graphlang import workspace as ws
from graphlang.grafv import ui


def settings_page() -> None:
    saved = ui.settings()
    st.header("Settings")
    names = ws.providers()
    left, right = st.columns(2, gap="large")
    with left:
        provider = st.selectbox("Provider", names, index=names.index(saved["provider"]) if saved["provider"] in names else 0, key="set_provider",
                                help="the dd-llm adapter the Create and Edit chats call; `graf run` has its own --llm")
        hints = ws.MODEL_HINTS.get(str(provider), [])
        model = st.text_input("Model", saved["model"] if saved["provider"] == provider else "", key=f"set_model_{provider}",
                              placeholder=hints[0] if hints else "the provider's default",
                              help="leave empty for the provider's default" + (f"; e.g. {', '.join(hints)}" if hints else ""))
        if hints:
            st.caption("suggestions: " + ", ".join(f"`{h}`" for h in hints))

        height = st.slider("Picture height (pixels)", 400, 1600, int(saved.get("canvas_height", ws.DEFAULT_CANVAS)), 50, key="set_canvas_h",
                           help="the height of the graph picture on the Create and Edit pages; a page cannot read your window's height")
        embedding = st.text_input("Embedding model for recipe search", saved.get("embedding", "auto"), key="set_embedding",
                                  help="auto, none, sentence_transformers:all-MiniLM-L6-v2, or ollama:qwen3-embedding:0.6b. It makes the search on the Browse "
                                       "page, and the examples Create shows the model, match by meaning and not only by words.")
    with right:
        keys = dict(saved["keys"])
        variables = ws.PROVIDER_VARS.get(str(provider), [])
        if not variables:
            st.info(f"{provider} uses its own login (for claude_cli: `claude` must be signed in); there is no key to enter.")
        for var in variables:
            secret = ws.is_secret(var)
            in_env = bool(os.environ.get(var)) and var not in saved["keys"]
            current = keys.get(var, "")
            label = f"{var}" + ("  (set in your environment)" if in_env else "")
            value = st.text_input(label, "", key=f"set_{var}", type="password" if secret else "default",
                                  placeholder=ws.mask(current) if current and secret else (current or ""),
                                  help="leave empty to keep what is saved" if current else "")
            if value:
                keys[var] = value
            if current and st.button(f"Remove the saved {var}", key=f"rm_{var}"):
                keys.pop(var, None)
                _save(saved["provider"], saved["model"], keys, saved.get("canvas_height", ws.DEFAULT_CANVAS), saved.get("embedding", "auto"))   # only the key goes
                st.rerun()
    st.caption("Saved in plain text in `~/.graflang/settings.json` (only your user can read it). The environment of this process is used first.")

    if st.button("Save settings", type="primary", key="set_save"):
        _save(provider, model, keys, height, embedding)
        st.success(f"saved: the chats now use {ws.llm_spec(st.session_state['settings'])}")
    st.divider()
    st.markdown("**Test the connection**")
    st.caption("Sends one short message with the saved settings. It is a real call: billed on an API key, or counted on a subscription.")
    if st.button("Test", key="set_test"):
        try:
            llm, adapter, model_used = ui.new_llm(1)
            with st.spinner("calling the model"):
                reply = llm.generate("Reply with the single word OK.", model=model_used)
            st.success(f"{adapter} answered: {str(reply).strip()[:200]}")
        except Exception as e:                                          # a missing package, a bad key, no network: the page shows the reason
            st.error(f"{type(e).__name__}: {e}")


def _save(provider, model, keys, height, embedding) -> None:
    st.session_state["settings"] = {"provider": str(provider), "model": str(model).strip(), "keys": keys, "canvas_height": int(height), "embedding": str(embedding).strip() or "auto"}
    ws.save_settings(st.session_state["settings"])
    ws.apply_settings(st.session_state["settings"])


if __name__ == "__main__":                # Streamlit runs a page file as a script; tests import the function
    settings_page()
