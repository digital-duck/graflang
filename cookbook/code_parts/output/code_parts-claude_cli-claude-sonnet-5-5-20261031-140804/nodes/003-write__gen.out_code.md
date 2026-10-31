=== FILE: README.md ===
# Translator Chatbot

A Streamlit chatbot that translates text from a source language to a target language using an LLM.

Defaults: adapter `claude_cli`, model `claude-sonnet-5-5`. Both can be changed in the sidebar, along with an optional API key.

## Run

    pip install -r requirements.txt
    streamlit run translator/app.py

## Configuration

- Sidebar: adapter, model, API key, source language, target language.
- Environment defaults: `TRANSLATOR_ADAPTER`, `TRANSLATOR_MODEL`.
- Adapters:
  - `claude_cli`: uses the local `claude` command line tool (no API key needed).
  - `anthropic`: Anthropic API (`ANTHROPIC_API_KEY`).
  - `openai`: OpenAI API (`OPENAI_API_KEY`).
  - `gemini`: Google API (`GEMINI_API_KEY`).
- The API key entered in the sidebar is passed only to the call (via environment variable of the process or subprocess) and is never written to disk.

## Layout

- `translator/config.py`: settings and adapter registry.
- `translator/core.py`: prompt building and the `translate` function.
- `translator/app.py`: Streamlit chat interface.

=== FILE: requirements.txt ===
streamlit>=1.30
anthropic>=0.40
openai>=1.40
google-genai>=1.0

=== FILE: translator/__init__.py ===
"""Translator chatbot package."""

=== FILE: translator/config.py ===
"""Settings and adapter registry for the translator chatbot."""
import os
from dataclasses import dataclass
from typing import Dict, List

DEFAULT_ADAPTER = os.environ.get("TRANSLATOR_ADAPTER", "claude_cli")
DEFAULT_MODEL = os.environ.get("TRANSLATOR_MODEL", "claude-sonnet-5-5")

LANGUAGES: List[str] = [
    "Auto-detect", "English", "Chinese", "Spanish", "French", "German",
    "Japanese", "Korean", "Portuguese", "Italian", "Russian", "Arabic",
    "Hindi", "Dutch", "Turkish", "Vietnamese",
]

# adapter -> (environment variable holding the API key or None, suggested models)
ADAPTERS: Dict[str, dict] = {
    "claude_cli": {"key_env": None, "models": ["claude-sonnet-5-5", "claude-opus-5-5", "claude-haiku-5-5"]},
    "anthropic": {"key_env": "ANTHROPIC_API_KEY", "models": ["claude-sonnet-5-5", "claude-opus-5-5", "claude-haiku-5-5"]},
    "openai": {"key_env": "OPENAI_API_KEY", "models": ["gpt-4o", "gpt-4o-mini"]},
    "gemini": {"key_env": "GEMINI_API_KEY", "models": ["gemini-2.0-flash", "gemini-1.5-pro"]},
}


@dataclass
class LLMSettings:
    adapter: str = DEFAULT_ADAPTER
    model: str = DEFAULT_MODEL
    api_key: str = ""

    def resolved_key(self) -> str:
        """API key from the settings, else from the adapter's environment variable."""
        if self.api_key:
            return self.api_key
        env = ADAPTERS.get(self.adapter, {}).get("key_env")
        return os.environ.get(env, "") if env else ""

=== FILE: translator/core.py ===
"""Prompt building and LLM calls for translation."""
import os
import subprocess

from translator.config import ADAPTERS, LLMSettings

TIMEOUT_SECONDS = 120


def build_prompt(text: str, source: str, target: str) -> str:
    if source == "Auto-detect":
        origin = "Detect the source language and translate"
    else:
        origin = f"Translate from {source}"
    return (
        f"{origin} to {target}. Output only the translation, with no "
        f"explanation, notes, or quotation marks.\n\nText:\n{text}"
    )


def _call_claude_cli(prompt: str, settings: LLMSettings) -> str:
    env = os.environ.copy()
    result = subprocess.run(
        ["claude", "-p", prompt, "--model", settings.model],
        capture_output=True, text=True, timeout=TIMEOUT_SECONDS, env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "claude CLI failed")
    return result.stdout.strip()


def _call_anthropic(prompt: str, settings: LLMSettings) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=settings.resolved_key() or None)
    msg = client.messages.create(
        model=settings.model,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()


def _call_openai(prompt: str, settings: LLMSettings) -> str:
    import openai

    client = openai.OpenAI(api_key=settings.resolved_key() or None)
    resp = client.chat.completions.create(
        model=settings.model,
        messages=[{"role": "user", "content": prompt}],
    )
    return (resp.choices[0].message.content or "").strip()


def _call_gemini(prompt: str, settings: LLMSettings) -> str:
    from google import genai

    client = genai.Client(api_key=settings.resolved_key() or None)
    resp = client.models.generate_content(model=settings.model, contents=prompt)
    return (resp.text or "").strip()


_CALLERS = {
    "claude_cli": _call_claude_cli,
    "anthropic": _call_anthropic,
    "openai": _call_openai,
    "gemini": _call_gemini,
}


def translate(text: str, source: str, target: str, settings: LLMSettings) -> str:
    """Translate `text` from `source` to `target` using the configured LLM."""
    if not text or not text.strip():
        raise ValueError("Nothing to translate.")
    if settings.adapter not in ADAPTERS:
        raise ValueError(f"Unknown adapter: {settings.adapter}")
    prompt = build_prompt(text.strip(), source, target)
    return _CALLERS[settings.adapter](prompt, settings)

=== FILE: translator/app.py ===
"""Streamlit chat interface for the translator."""
import os
import sys

# Allow `streamlit run translator/app.py` from the project root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st  # noqa: E402

from translator.config import (  # noqa: E402
    ADAPTERS, DEFAULT_ADAPTER, DEFAULT_MODEL, LANGUAGES, LLMSettings,
)
from translator.core import translate  # noqa: E402


def sidebar_settings():
    st.sidebar.header("LLM settings")
    names = list(ADAPTERS)
    idx = names.index(DEFAULT_ADAPTER) if DEFAULT_ADAPTER in names else 0
    adapter = st.sidebar.selectbox("Adapter", names, index=idx)

    suggestions = ADAPTERS[adapter]["models"]
    default_model = DEFAULT_MODEL if adapter in ("claude_cli", "anthropic") else suggestions[0]
    model = st.sidebar.text_input(
        "Model", value=default_model, key=f"model_{adapter}",
        help="Suggested: " + ", ".join(suggestions),
    )

    api_key = ""
    if ADAPTERS[adapter]["key_env"]:
        api_key = st.sidebar.text_input(
            f"API key ({ADAPTERS[adapter]['key_env']})", type="password",
            key=f"key_{adapter}", help="Leave empty to use the environment variable.",
        )
    else:
        st.sidebar.caption("claude_cli uses your local Claude login; no API key needed.")

    st.sidebar.header("Languages")
    source = st.sidebar.selectbox("Source language", LANGUAGES, index=0)
    targets = [l for l in LANGUAGES if l != "Auto-detect"]
    target = st.sidebar.selectbox("Target language", targets, index=targets.index("Chinese"))

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

    st.session_state.history.append({"role": "user", "content": text})
    with st.chat_message("user"):
        st.markdown(text)

    with st.chat_message("assistant"):
        with st.spinner("Translating..."):
            try:
                reply = translate(text, source, target, settings)
            except Exception as exc:  # show any adapter failure in the chat
                reply = f"Error: {exc}"
        st.markdown(reply)
    st.session_state.history.append({"role": "assistant", "content": reply})


main()