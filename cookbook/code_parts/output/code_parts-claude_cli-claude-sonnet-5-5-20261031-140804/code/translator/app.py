"""Streamlit chat interface for the translator."""
import logging
import os
import sys

# Allow `streamlit run translator/app.py` from the project root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st  # noqa: E402

from translator.config import (  # noqa: E402
    ADAPTERS, AUTO_DETECT, DEFAULT_ADAPTER, LANGUAGES, LLMSettings,
    default_model_for,
)
from translator.core import translate  # noqa: E402

log = logging.getLogger("translator")


def sidebar_settings():
    st.sidebar.header("LLM settings")
    names = list(ADAPTERS)
    idx = names.index(DEFAULT_ADAPTER) if DEFAULT_ADAPTER in names else 0
    adapter = st.sidebar.selectbox("Adapter", names, index=idx)

    info = ADAPTERS[adapter]
    model = st.sidebar.text_input(
        "Model", value=default_model_for(adapter), key=f"model_{adapter}",
        help="Suggested: " + ", ".join(info.models),
    )

    api_key = ""
    if info.key_env:
        api_key = st.sidebar.text_input(
            f"API key ({info.key_env})", type="password",
            key=f"key_{adapter}", help="Leave empty to use the environment variable.",
        )
    else:
        st.sidebar.caption("claude_cli uses your local Claude login; no API key needed.")

    st.sidebar.header("Languages")
    source = st.sidebar.selectbox("Source language", LANGUAGES, index=0)
    targets = [lang for lang in LANGUAGES if lang != AUTO_DETECT]
    target = st.sidebar.selectbox(
        "Target language", targets, index=targets.index("Chinese (Simplified)"),
    )

    if st.sidebar.button("Clear conversation"):
        st.session_state.history = []
        st.rerun()
    return LLMSettings(adapter=adapter, model=model.strip(), api_key=api_key), source, target


def main():
    st.set_page_config(page_title="Translator Chatbot", page_icon="🌐")
    st.title("🌐 Translator Chatbot")
    if "history" not in st.session_state:
        st.session_state.history = []

    settings, source, target = sidebar_settings()
    st.caption(f"{source} → {target} · {settings.adapter} / {settings.model}")

    for msg in st.session_state.history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    text = st.chat_input("Type text to translate")
    if not text:
        return

    with st.chat_message("user"):
        st.markdown(text)

    reply = None
    with st.chat_message("assistant"):
        with st.spinner("Translating..."):
            try:
                reply = translate(text, source, target, settings)
            except ValueError as exc:
                st.warning(str(exc))
            except RuntimeError as exc:
                st.error(str(exc))
            except Exception as exc:  # unexpected adapter/SDK failure
                log.exception("Unexpected translation failure")
                st.error(f"Unexpected {type(exc).__name__}: {exc}")
        if reply is not None:
            st.markdown(reply)

    if reply is not None:
        st.session_state.history.append({"role": "user", "content": text})
        st.session_state.history.append({"role": "assistant", "content": reply})


if __name__ == "__main__":
    main()
