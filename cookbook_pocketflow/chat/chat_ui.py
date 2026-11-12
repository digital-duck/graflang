"""A chatbot page for the chat recipe: one question, up to three chatbots answering side by side.

    streamlit run cookbook_pocketflow/chat/chat_ui.py

The sidebar sets how many chatbots there are and, for each, its provider, model and how many recent turns it sees.
A question goes to every chatbot at once (in parallel); each keeps its own conversation and shows it in its own column,
so the models can be compared on the same questions. Each chatbot's turn runs `chat_turn.graph.yaml` (beside this
file) once: its history and the question go in, the reply and the new history come out. Every question is one model
call per chatbot, capped at one per run; Anthropic models are billed, local Ollama models are not.
"""
from __future__ import annotations

import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import streamlit as st

from graphlang.grafr.adapters import make_llm
from graphlang.grafr.metering import MeteredLLM
from graphlang.grafr.runtime import GraphLangRuntime, load_graph

GRAPH = Path(__file__).with_name("chat_turn.graph.yaml")
MAX_BOTS = 3
ANTHROPIC = {"fable": "claude-fable-5-1", "opus": "claude-opus-5-5", "sonnet": "claude-sonnet-5-5", "haiku": "claude-haiku-5-5"}
PROVIDERS = {"anthropic": "claude_cli", "ollama": "ollama"}     # shown name -> graflang adapter (Anthropic through the Claude CLI)
OLLAMA_URL = "http://localhost:11434"


@st.cache_data(ttl=60, show_spinner=False)
def ollama_models() -> list[str]:
    """The local Ollama models that can chat (embedding models are left out); empty when Ollama is not running."""
    def get(path: str, body: dict | None = None) -> dict:
        data = json.dumps(body).encode() if body is not None else None
        with urllib.request.urlopen(urllib.request.Request(OLLAMA_URL + path, data=data), timeout=2) as r:
            return json.load(r)
    try:
        names = sorted(m["name"] for m in get("/api/tags").get("models", []))
    except OSError:
        return []
    chat = []
    for name in names:
        try:
            capabilities = get("/api/show", {"model": name}).get("capabilities")
        except OSError:
            capabilities = None
        if capabilities is None or "completion" in capabilities:      # an older Ollama does not say: keep the model
            chat.append(name)
    return chat


def ask(question: str, history: list[dict], llm: str, last_n: int) -> tuple[str, float]:
    """One run of the graph for one chatbot: (reply, seconds). The graph sees only role and content."""
    adapter, _, model = llm.partition(":")
    start = time.monotonic()
    runtime = GraphLangRuntime(load_graph(GRAPH), llm=MeteredLLM(make_llm(adapter, model or None), max_calls=1), verbose=False)
    plain = [{"role": m["role"], "content": m["content"]} for m in history]
    out = runtime.execute({"history": json.dumps(plain), "question": question, "last_n": last_n})
    return out["reply"], time.monotonic() - start


def bot_settings(i: int) -> dict:
    """The sidebar block of chatbot i: provider, model, turns, New chat. Returns {llm, label, last_n}."""
    history = st.session_state.setdefault(f"history_{i}", [])
    with st.sidebar.expander(f"**Chatbot {i + 1}**", expanded=True):
        provider = st.selectbox("Provider", list(PROVIDERS), key=f"provider_{i}")
        if provider == "anthropic":
            name = st.selectbox("Model", list(ANTHROPIC), index=list(ANTHROPIC).index("haiku"), key=f"model_anthropic_{i}",
                                format_func=lambda n: f"{n} ({ANTHROPIC[n]})")
            model = ANTHROPIC[name]
        else:
            local = ollama_models()
            if not local:
                st.warning(f"No Ollama models found at {OLLAMA_URL}: start Ollama (`ollama serve`) and pull a model.")
            name = model = st.selectbox("Model", local, key=f"model_ollama_{i}")
        last_n = int(st.number_input("Turns it sees", 1, 50, 10, key=f"last_n_{i}",
                                     help="the most recent questions and replies sent with each question"))
        left, right = st.columns([1, 1])
        if left.button("New chat", key=f"new_{i}", disabled=not history):
            st.session_state[f"history_{i}"] = []
            st.rerun()
        right.caption(f"{len(history) // 2} turn(s)")
    return {"llm": f"{PROVIDERS[provider]}:{model}" if model else "", "label": f"{provider} · {name or 'no model'}", "last_n": last_n}


SETTING_KEYS = ("bots", "provider_", "model_anthropic_", "model_ollama_", "last_n_")
CHAT_KEYS = ("history_", "error_")


def forget(prefixes: tuple[str, ...]) -> None:
    """Drop the session values whose keys start with one of `prefixes` (a button's callback, so it runs before the widgets)."""
    for key in [k for k in st.session_state if str(k).startswith(prefixes)]:
        del st.session_state[key]


def show(history: list[dict]) -> None:
    for m in history:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
            if m["role"] == "assistant" and m.get("model"):
                st.caption(f"{m['model']} · {m['seconds']:.1f}s")


def main() -> None:
    st.set_page_config(page_title="Chat · GraphLang", page_icon="💬", layout="wide")
    reset, clear = st.sidebar.columns(2)
    reset.button("Reset", key="reset", on_click=forget, args=(SETTING_KEYS,), width="stretch",
                 help="back to the default settings: one chatbot, anthropic · haiku, 10 turns (the chats are kept)")
    clear.button("Clear Chats", key="clear", on_click=forget, args=(CHAT_KEYS,), width="stretch",
                 help="clear every chatbot's conversation (the settings are kept)")
    n = int(st.sidebar.selectbox("Number of chatbots", list(range(1, MAX_BOTS + 1)), key="bots",
                                 help="each one answers every question, side by side; Anthropic models are one billed call each"))
    bots = [bot_settings(i) for i in range(n)]
    st.sidebar.caption(f"graph: `{GRAPH.name}`, run once per chatbot per question")

    st.header("💬 Chat")
    columns = st.columns(n)
    for i, (column, bot) in enumerate(zip(columns, bots)):
        with column:
            st.subheader(f"{i + 1} · {bot['label']}", divider="gray")
            show(st.session_state[f"history_{i}"])
            if not st.session_state[f"history_{i}"]:
                st.caption("Ask a question below to start.")
            if st.session_state.get(f"error_{i}"):
                st.error(st.session_state[f"error_{i}"])

    question = st.chat_input("Ask a question" + (" (every chatbot answers)" if n > 1 else ""))
    if not question:
        return
    ready = [i for i, bot in enumerate(bots) if bot["llm"]]
    if not ready:
        st.error("No chatbot has a model: pick one in the sidebar.")
        return
    with st.spinner(f"asking {len(ready)} chatbot(s)"):
        with ThreadPoolExecutor(max_workers=len(ready)) as pool:          # the chatbots answer at the same time
            futures = {i: pool.submit(ask, question, st.session_state[f"history_{i}"], bots[i]["llm"], bots[i]["last_n"]) for i in ready}
    for i, future in futures.items():
        st.session_state.pop(f"error_{i}", None)
        try:
            reply, seconds = future.result()
        except Exception as e:              # one failing chatbot does not lose the others' replies, and its conversation stays as it was
            st.session_state[f"error_{i}"] = f"{question!r} failed: {type(e).__name__}: {e}"
            continue
        st.session_state[f"history_{i}"] += [{"role": "user", "content": question},
                                             {"role": "assistant", "content": reply, "model": bots[i]["llm"], "seconds": seconds}]
    st.rerun()


main()
