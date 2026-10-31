[READY]
Build a single-page Streamlit chat app that translates user-entered text from a chosen source language to a chosen target language via dd-llm, defaulting to adapter `claude_cli` with model `claude-sonnet-5-5`, with the adapter, model, and API key configurable in the UI.

STRUCTURED SPEC:
1. **App shell**: One Streamlit script (e.g. `app.py`) using `st.chat_input` and `st.chat_message`. Chat history is kept in `st.session_state`, and each user message is translated and shown as an assistant reply.
2. **Language selection**: Sidebar selectboxes for source and target language. Source includes an "Auto-detect" option. Target excludes it. Provide a reasonable preset list (English, Chinese, Spanish, French, German, Japanese, Korean, etc.).
3. **Translation call**: Each message goes to the LLM with a prompt asking for the translation only, with no commentary, from source to target. When source is auto-detect, the prompt tells the model to detect it.
4. **Defaults**: Adapter `claude_cli` and model `claude-sonnet-5-5` are preselected. `claude_cli` needs no API key.
5. **Configuration**: The sidebar lets the user pick the adapter (at least `claude_cli`, plus the other dd-llm adapters such as anthropic, openai, gemini; the list is read from dd-llm where possible) and edit the model name as free text. A password-type field takes the API key for adapters that need one. The key is held only in session state and passed to the adapter. It is never logged, written to disk, or echoed.
6. **Error handling**: Show failures (missing key, adapter error, empty input) with `st.error` instead of crashing. Keep the chat history intact after an error.
7. **Extras**: A "Clear chat" button. Include run instructions (`streamlit run app.py`) and the dependencies (`streamlit`, `dd-llm`).

**Assumptions to note:**
- Each message is translated independently, with no multi-turn context.
- No streaming is required.
- Tests are optional. If written, they should stub the LLM call.