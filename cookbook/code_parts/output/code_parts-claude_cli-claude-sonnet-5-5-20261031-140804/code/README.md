# Translator Chatbot

A Streamlit chatbot that translates text from a source language to a target language using an LLM.

Defaults: adapter `claude_cli`, model `claude-sonnet-5-5`. Both can be changed in the sidebar, along with an optional API key.

## Run

    pip install -r requirements.txt
    streamlit run translator/app.py

The base requirements install only Streamlit. Install the SDK for the adapter you use:

    pip install -r requirements-anthropic.txt   # anthropic adapter
    pip install -r requirements-openai.txt      # openai adapter
    pip install -r requirements-gemini.txt      # gemini adapter

Run the tests with:

    pip install pytest
    pytest

## Configuration

- Sidebar: adapter, model, API key, source language, target language.
- Environment defaults: `TRANSLATOR_ADAPTER`, `TRANSLATOR_MODEL`. The model default applies to the default adapter; other adapters start with their first suggested model.
- Adapters:
  - `claude_cli`: uses the local `claude` command line tool (no API key needed). It runs from a neutral temporary directory so project context is not picked up.
  - `anthropic`: Anthropic API (`ANTHROPIC_API_KEY`).
  - `openai`: OpenAI API (`OPENAI_API_KEY`).
  - `gemini`: Google API (`GEMINI_API_KEY`).
- The API key entered in the sidebar is passed directly to the SDK client constructor for that call. It is never written to disk and is hidden from the settings `repr`.

## Behaviour

- The user text is wrapped in explicit delimiters and the model is told to treat it only as text to translate (system prompt where supported).
- Input is limited to 8000 characters. Identical source and target languages are rejected with a message.
- Empty replies and truncated replies (output token limit reached) are reported as errors.
- Errors are shown with `st.error` and are not stored in the conversation history.
- Chinese is offered as Simplified and Traditional.

## Layout

- `translator/config.py`: settings and adapter registry.
- `translator/core.py`: prompt building and the `translate` function.
- `translator/app.py`: Streamlit chat interface.
- `tests/test_translator.py`: unit tests.
