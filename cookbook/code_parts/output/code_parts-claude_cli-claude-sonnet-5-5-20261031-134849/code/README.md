# Translator Chatbot

A Streamlit chatbot that translates text from a source language to a target language using an LLM.

Defaults: adapter `claude_cli`, model `claude-sonnet-5-5`. The adapter, model and an optional API key can be changed in the sidebar.

## Run

    pip install streamlit
    pip install -e /path/to/dd-llm      # provides the LLM adapters
    pip install -e .                    # installs translator_bot (no sys.path tricks)
    streamlit run translator_bot/app.py

## Configuration

- Adapter: `claude_cli` (default), `anthropic`, `openai`, `gemini`, or any other adapter name dd-llm knows (type it in "Other adapter").
- Model: free text. Each adapter has its own default model; changing the adapter resets the model field to that default. A blank model uses the adapter's default.
- API key: kept in the Streamlit session only and passed to the adapter constructor (`api_key=`). It is never written to `os.environ`, so it cannot leak to other sessions. `claude_cli` ignores the key by design: it uses the logged-in CLI and the key is not sent to it.
- If an adapter does not accept `api_key`, the translation fails with a clear message instead of silently dropping the key.
- Source language may be `Auto-detect`. If source and target are the same language, the text is returned unchanged.
- Translation runs with a timeout (default 120 s) so a hung adapter cannot freeze the session forever.
- Errors are shown with `st.error`, are not stored in the chat history, and show a generic message; details go to the log.
- History is capped at 50 messages. Translations are shown as plain text, so formatting characters are not interpreted.

## Layout

- `translator_bot/config.py`: settings dataclass, defaults, per-adapter models.
- `translator_bot/core.py`: prompt building, adapter creation, the `translate` function.
- `translator_bot/app.py`: the Streamlit chat UI (`main()` runs only under Streamlit / `__main__`).

## Tests

    pip install pytest
    pytest
