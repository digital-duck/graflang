=== FILE: README.md ===
# Translator Chatbot

A Streamlit chatbot that translates text from a source language to a target language using an LLM.

Defaults: adapter `claude_cli`, model `claude-sonnet-5-5`. Both can be changed in the sidebar, together with an optional API key.

## Run

    pip install streamlit
    pip install -e /path/to/dd-llm      # provides the LLM adapters
    streamlit run translator_bot/app.py

## Configuration

- Adapter: `claude_cli` (default), `anthropic`, `openai`, `gemini`, or any other adapter name dd-llm knows.
- Model: free text, default `claude-sonnet-5-5`.
- API key: stored only in the session. It is passed to the adapter and also exported as the provider's environment variable (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`) for the process. `claude_cli` normally needs no key (it uses the logged-in CLI).
- Source language may be `Auto-detect`.

## Layout

- `translator_bot/config.py`: settings dataclass, defaults, API key environment handling.
- `translator_bot/core.py`: prompt building and the `translate` function.
- `translator_bot/app.py`: the Streamlit chat UI.

## Tests

    pip install pytest
    pytest

=== FILE: translator_bot/__init__.py ===
"""Streamlit translation chatbot."""

=== FILE: translator_bot/config.py ===
"""Settings and API key handling."""

import os
from dataclasses import dataclass
from typing import Optional

DEFAULT_ADAPTER = "claude_cli"
DEFAULT_MODEL = "claude-sonnet-5-5"
ADAPTERS = ["claude_cli", "anthropic", "openai", "gemini"]

LANGUAGES = [
    "English", "Chinese", "Spanish", "French", "German", "Japanese",
    "Korean", "Portuguese", "Italian", "Russian", "Arabic", "Hindi",
]
AUTO_DETECT = "Auto-detect"

API_KEY_ENV = {
    "anthropic": "ANTHROPIC_API_KEY",
    "claude_cli": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
}


@dataclass
class Settings:
    adapter: str = DEFAULT_ADAPTER
    model: str = DEFAULT_MODEL
    api_key: Optional[str] = None
    source_lang: str = AUTO_DETECT
    target_lang: str = "English"


def apply_api_key(adapter: str, api_key: Optional[str]) -> None:
    """Export the key as the provider's environment variable, if one is given."""
    if not api_key:
        return
    env_name = API_KEY_ENV.get(adapter)
    if env_name:
        os.environ[env_name] = api_key

=== FILE: translator_bot/core.py ===
"""Prompt building and translation through a dd-llm adapter."""

from typing import Callable, Optional

from translator_bot.config import AUTO_DETECT, Settings, apply_api_key


def build_prompt(text: str, source_lang: str, target_lang: str) -> str:
    if source_lang == AUTO_DETECT:
        source_part = "Detect the source language and translate"
    else:
        source_part = f"Translate from {source_lang}"
    return (
        f"{source_part} into {target_lang}.\n"
        "Reply with the translation only: no notes, quotes or explanations.\n\n"
        f"Text:\n{text}"
    )


def _get_adapter(settings: Settings):
    """Create a dd-llm adapter (imported lazily so the UI can show a clear error)."""
    from dd_llm import get_adapter  # type: ignore

    kwargs = {"model": settings.model}
    if settings.api_key:
        kwargs["api_key"] = settings.api_key
    try:
        return get_adapter(settings.adapter, **kwargs)
    except TypeError:
        kwargs.pop("api_key", None)
        return get_adapter(settings.adapter, **kwargs)


def _call(adapter, prompt: str) -> str:
    for name in ("generate", "complete", "call", "run"):
        fn = getattr(adapter, name, None)
        if callable(fn):
            result = fn(prompt)
            return getattr(result, "text", result if isinstance(result, str) else str(result))
    raise RuntimeError("The LLM adapter has no known generate method.")


def translate(
    text: str,
    settings: Settings,
    llm: Optional[Callable[[str], str]] = None,
) -> str:
    """Translate text per settings. `llm` may be a callable prompt -> str (for tests)."""
    text = (text or "").strip()
    if not text:
        raise ValueError("Nothing to translate.")
    prompt = build_prompt(text, settings.source_lang, settings.target_lang)
    if llm is not None:
        return llm(prompt).strip()
    apply_api_key(settings.adapter, settings.api_key)
    adapter = _get_adapter(settings)
    return _call(adapter, prompt).strip()

=== FILE: translator_bot/app.py ===
"""Streamlit chat UI for the translator."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st  # noqa: E402

from translator_bot.config import (  # noqa: E402
    ADAPTERS, AUTO_DETECT, DEFAULT_ADAPTER, DEFAULT_MODEL, LANGUAGES, Settings,
)
from translator_bot.core import translate  # noqa: E402


def sidebar_settings() -> Settings:
    st.sidebar.header("Settings")
    adapter = st.sidebar.selectbox(
        "Adapter", ADAPTERS, index=ADAPTERS.index(DEFAULT_ADAPTER)
    )
    custom = st.sidebar.text_input("Other adapter (optional)", value="")
    model = st.sidebar.text_input("Model", value=DEFAULT_MODEL)
    api_key = st.sidebar.text_input("API key (optional)", type="password")
    source = st.sidebar.selectbox("From", [AUTO_DETECT] + LANGUAGES)
    target = st.sidebar.selectbox("To", LANGUAGES, index=0)
    return Settings(
        adapter=custom.strip() or adapter,
        model=model.strip() or DEFAULT_MODEL,
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
        f"{settings.adapter} / {settings.model}"
    )

    if "history" not in st.session_state:
        st.session_state.history = []
    if st.sidebar.button("Clear chat"):
        st.session_state.history = []

    for role, content in st.session_state.history:
        with st.chat_message(role):
            st.markdown(content)

    prompt = st.chat_input("Type text to translate")
    if not prompt:
        return

    st.session_state.history.append(("user", prompt))
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        try:
            with st.spinner("Translating..."):
                reply = translate(prompt, settings)
        except Exception as exc:  # show any adapter failure in the chat
            reply = f"Error: {exc}"
        st.markdown(reply)
    st.session_state.history.append(("assistant", reply))


main()

=== FILE: tests/test_core.py ===
import pytest

from translator_bot.config import Settings
from translator_bot.core import build_prompt, translate


def test_prompt_mentions_languages():
    p = build_prompt("hola", "Spanish", "English")
    assert "Spanish" in p and "English" in p and "hola" in p


def test_auto_detect_prompt():
    assert "Detect" in build_prompt("hola", "Auto-detect", "English")


def test_translate_with_stub():
    s = Settings(source_lang="Spanish", target_lang="English")
    assert translate("hola", s, llm=lambda p: " hello \n") == "hello"


def test_empty_text_rejected():
    with pytest.raises(ValueError):
        translate("  ", Settings(), llm=lambda p: "x")

=== FILE: tests/conftest.py ===
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))