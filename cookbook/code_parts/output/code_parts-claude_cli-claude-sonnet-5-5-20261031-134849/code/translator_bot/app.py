"""Streamlit chat UI for the translator."""

import logging

import streamlit as st

from translator_bot.config import (
    ADAPTERS, AUTO_DETECT, DEFAULT_ADAPTER, KEYLESS_ADAPTERS, LANGUAGES,
    MAX_HISTORY, Settings, default_model_for,
)
from translator_bot.core import TranslationError, translate

log = logging.getLogger("translator_bot")


def sidebar_settings() -> Settings:
    st.sidebar.header("Settings")
    adapter = st.sidebar.selectbox(
        "Adapter", ADAPTERS, index=ADAPTERS.index(DEFAULT_ADAPTER)
    )
    custom = st.sidebar.text_input("Other adapter (optional)", value="").strip()
    chosen = custom or adapter
    # Keyed on the adapter, so the model field resets to that adapter's default.
    model = st.sidebar.text_input(
        "Model", value=default_model_for(chosen), key=f"model_{chosen}"
    )
    if chosen in KEYLESS_ADAPTERS:
        st.sidebar.caption("claude_cli uses the logged-in CLI; an API key is not used.")
        api_key = ""
    else:
        api_key = st.sidebar.text_input(
            "API key (optional)", type="password", key=f"key_{chosen}"
        )
    source = st.sidebar.selectbox("From", [AUTO_DETECT] + LANGUAGES)
    target = st.sidebar.selectbox("To", LANGUAGES, index=0)
    return Settings(
        adapter=chosen,
        model=model.strip(),
        api_key=api_key.strip() or None,
        source_lang=source,
        target_lang=target,
    )


def main() -> None:
    st.set_page_config(page_title="Translator Chatbot", page_icon="🌐")
    st.title("🌐 Translator Chatbot")
    settings = sidebar_settings()
    st.caption(
        f"{settings.source_lang} → {settings.target_lang} · "
        f"{settings.adapter} / {settings.model or 'adapter default'}"
    )

    if "history" not in st.session_state:
        st.session_state.history = []
    if st.sidebar.button("Clear chat"):
        st.session_state.history = []

    for role, content in st.session_state.history:
        with st.chat_message(role):
            st.text(content)

    prompt = st.chat_input("Type text to translate")
    if not prompt:
        return

    with st.chat_message("user"):
        st.text(prompt)
    reply = None
    try:
        with st.spinner("Translating..."):
            reply = translate(prompt, settings)
    except (ValueError, TranslationError) as exc:
        st.error(str(exc))
    except Exception:
        log.exception("Unexpected error")
        st.error("Something went wrong. See the log for details.")

    if reply is not None:
        with st.chat_message("assistant"):
            st.text(reply)
        st.session_state.history.append(("user", prompt))
        st.session_state.history.append(("assistant", reply))
        del st.session_state.history[:-MAX_HISTORY]


if __name__ == "__main__" or st.runtime.exists():
    main()
