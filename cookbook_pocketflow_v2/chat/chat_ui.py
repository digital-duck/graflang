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
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

import chat_models as cm
from chat_models import PROVIDERS
from graphlang.grafr.adapters import make_llm
from graphlang.grafr.metering import MeteredLLM
from graphlang.grafr.runtime import GraphLangRuntime, load_graph

GRAPH = Path(__file__).with_name("chat_turn.graph.yaml")
MAX_BOTS = 3
DEFAULT_BOTS = 3
DEFAULT_MODELS = [("anthropic", "sonnet"), ("anthropic", "opus"), ("ollama", "gemma3")]      # chatbot 1, 2, 3: provider, model (ollama: name prefix)


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
        want_provider, want_model = DEFAULT_MODELS[i] if i < len(DEFAULT_MODELS) else DEFAULT_MODELS[0]
        provider = st.selectbox("Provider", list(PROVIDERS), index=list(PROVIDERS).index(want_provider), key=f"provider_{i}")
        options = cm.selected(provider)
        if not options:
            st.warning(f"No {provider} models to offer: " + ("start Ollama (`ollama serve`) and pull a model, or " if provider == "ollama" else "")
                       + "choose some on the Config LLM page.")
        key = f"model_{provider}_{i}"
        if st.session_state.get(key) not in options:         # a model that is no longer offered
            st.session_state.pop(key, None)
        first = next((k for k, m in enumerate(options) if want_model in m), 0)
        model = st.selectbox("Model", options, index=first, key=key) if options else None
        name = cm.short_name(provider, model) if model else None
        last_n = int(st.number_input("Turns it sees", 1, 50, 10, key=f"last_n_{i}",
                                     help="the most recent questions and replies sent with each question"))
        left, right = st.columns([1, 1])
        if left.button("New chat", key=f"new_{i}", disabled=not history):
            st.session_state[f"history_{i}"] = []
            st.rerun()
        right.caption(f"{len(history) // 2} turn(s)")
    return {"llm": f"{PROVIDERS[provider]}:{model}" if model else "", "label": f"{provider} · {name or 'no model'}", "last_n": last_n}


SETTING_KEYS = ("bots", "provider_", "model_anthropic_", "model_openrouter_", "model_ollama_", "last_n_", "pane_height", "font_size")
CHAT_KEYS = ("history_", "error_", "qnum")

PANE_HEIGHT = 1000                          # default pixels of conversation shown per chatbot before it scrolls
FONT_SIZE = 20                              # default pixels of the conversation text


def forget(prefixes: tuple[str, ...]) -> None:
    """Drop the session values whose keys start with one of `prefixes` (a button's callback, so it runs before the widgets)."""
    for key in [k for k in st.session_state if str(k).startswith(prefixes)]:
        del st.session_state[key]


def set_feedback(i: int, idx: int, value: int) -> None:
    """A thumb button's callback: the same thumb again takes the feedback back (0)."""
    m = st.session_state[f"history_{i}"][idx]
    m["feedback"] = 0 if m.get("feedback", 0) == value else value


def copy_button(text: str) -> None:
    """📋 puts `text` on the clipboard. Streamlit has no clipboard call, so a small page of its own does it (the textarea route works
    where `navigator.clipboard` is not allowed in an iframe)."""
    components.html(
        """<button id="b" title="Copy markdown" style="font-size:16px;padding:2px 10px;border:1px solid #ccc;border-radius:8px;
        background:transparent;cursor:pointer">📋</button><script>
        const text = %s, b = document.getElementById("b");
        b.onclick = () => {
          const t = document.createElement("textarea"); t.value = text; document.body.appendChild(t); t.select();
          let ok = false; try { ok = document.execCommand("copy"); } catch (e) {}
          t.remove(); b.textContent = ok ? "✅" : "⚠️"; setTimeout(() => b.textContent = "📋", 1200);
        };</script>""" % json.dumps(text).replace("</", "<\\/"), height=38)


def show(i: int, history: list[dict]) -> None:
    asked = 0
    for idx, m in enumerate(history):
        asked += m["role"] == "user"
        with st.chat_message(m["role"]):
            st.markdown(f"**[{m.get('q', asked)}]** {m['content']}" if m["role"] == "user" else m["content"])   # the question number lines the columns up
            if m["role"] == "assistant":
                if m.get("model"):
                    st.caption(f"{m['model']} · {m['seconds']:.1f}s")
                copy, up, down, _ = st.columns([1, 1, 1, 5], vertical_alignment="center")
                with copy:
                    copy_button(m["content"])
                feedback = m.get("feedback", 0)
                up.button("👍", key=f"up_{i}_{idx}", on_click=set_feedback, args=(i, idx, 1), type="primary" if feedback == 1 else "secondary",
                          help="good answer (click again to undo)")
                down.button("👎", key=f"down_{i}_{idx}", on_click=set_feedback, args=(i, idx, -1), type="primary" if feedback == -1 else "secondary",
                            help="poor answer (click again to undo)")


def block(text: str, indent: int) -> str:
    """`text` as a YAML literal block scalar (`|2-`), so it needs no quoting: every line is indented, nothing is escaped."""
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text.replace("\r\n", "\n").replace("\r", "\n")).rstrip("\n")
    pad = " " * indent
    return "|2-\n" + "\n".join(pad + line if line.strip() else "" for line in text.split("\n"))


def export_yaml() -> str:
    """Every conversation as YAML, organised by question: for each, the answers with chatbot id, `<provider>:<model-id>`, the response time
    in seconds, the response and the human feedback (1 thumb up, -1 thumb down, 0 none)."""
    by_question: dict[int, dict] = {}
    adapter_provider = {adapter: provider for provider, adapter in PROVIDERS.items()}
    for i in range(MAX_BOTS):
        asked = 0
        pending = None
        for m in st.session_state.get(f"history_{i}", []):
            if m["role"] == "user":
                asked += 1
                pending = (m.get("q", asked), m["content"])
            elif pending:
                q, text = pending
                adapter, _, model = (m.get("model") or ":").partition(":")
                entry = by_question.setdefault(q, {"question": text, "answers": []})
                entry["answers"].append((i + 1, f"{adapter_provider.get(adapter, adapter)}:{model}", m["content"], m.get("feedback", 0), m.get("seconds")))
                pending = None
    lines = [f"exported: {datetime.now().isoformat(timespec='seconds')}", "questions:"]
    for q in sorted(by_question):
        entry = by_question[q]
        lines += [f"  - number: {q}", f"    question: {block(entry['question'], 6)}", "    answers:"]
        for bot, llm, response, feedback, seconds in sorted(entry["answers"], key=lambda a: a[0]):
            lines += [f"      - chatbot: {bot}", f"        llm: {llm}",
                      f"        seconds: {round(seconds, 1)}" if seconds is not None else "        seconds: null", f"        feedback: {feedback}",
                      f"        response: {block(response, 10)}"]
    return "\n".join(lines) + "\n"


def main() -> None:
    st.set_page_config(page_title="Chat · GraphLang", page_icon="💬", layout="wide")
    st.sidebar.header("Multi-Chats")
    reset, export, clear = st.sidebar.columns(3)
    reset.button("Reset", key="reset", on_click=forget, args=(SETTING_KEYS,), width="stretch",
                 help="back to the default settings: three chatbots (sonnet, opus, gemma3), 10 turns (the chats are kept)")
    export.download_button("Export", export_yaml(), file_name=f"GraphLang-Multi-Chats-{datetime.now():%y%m%d-%H%M%S}.yaml",
                           mime="application/x-yaml", key="export", width="stretch",
                           disabled=not any(st.session_state.get(f"history_{i}") for i in range(MAX_BOTS)),
                           help="every question with each chatbot's response and your thumbs, as YAML")
    clear.button("Clear Chats", key="clear", on_click=forget, args=(CHAT_KEYS,), width="stretch",
                 help="clear every chatbot's conversation (the settings are kept)")
    n = int(st.sidebar.selectbox("Number of chatbots", list(range(1, MAX_BOTS + 1)), index=DEFAULT_BOTS - 1, key="bots",
                                 help="each one answers every question, side by side; Anthropic models are one billed call each"))
    pane_height = int(st.sidebar.number_input("Pane height (px)", 200, 2000, PANE_HEIGHT, step=50, key="pane_height",
                                              help="how tall each chatbot's conversation is before it scrolls"))
    font_size = int(st.sidebar.number_input("Font size (px)", 10, 28, FONT_SIZE, step=1, key="font_size",
                                            help="the size of the conversation text"))
    st.markdown(f"<style>[data-testid='stChatMessage'] :is(p, li, code, td, th), [data-testid='stChatInput'] textarea "
                f"{{ font-size: {font_size}px; }}</style>", unsafe_allow_html=True)
    bots = [bot_settings(i) for i in range(n)]
    st.sidebar.caption(f"graph: `{GRAPH.name}`, run once per chatbot per question")

    st.header("💬 Chat")
    columns = st.columns(n)
    for i, (column, bot) in enumerate(zip(columns, bots)):
        with column:
            st.subheader(f"{i + 1} · {bot['label']}", divider="gray")
            with st.container(height=pane_height, border=False):          # each chatbot scrolls on its own, so the columns stay side by side
                show(i, st.session_state[f"history_{i}"])
                if not st.session_state[f"history_{i}"]:
                    st.caption("Ask a question below to start.")
                if st.session_state.get(f"error_{i}"):
                    st.error(st.session_state[f"error_{i}"])

    question = st.chat_input("Ask a question" + (" (every chatbot answers)" if n > 1 else ""))
    if not question:
        return
    qnum = st.session_state["qnum"] = st.session_state.get("qnum", 0) + 1
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
        st.session_state[f"history_{i}"] += [{"role": "user", "content": question, "q": qnum},
                                             {"role": "assistant", "content": reply, "model": bots[i]["llm"], "seconds": seconds}]
    st.rerun()


main()
