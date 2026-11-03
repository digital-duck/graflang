"""The pattern recipes (guardrail, supervisor, self_heal, notes_digest, chat_memory), each walked down every branch with a scripted
model (no network). Each recipe is copied into a temporary folder first, so the files its EMIT nodes write never touch the repo."""
import json
import shutil
from pathlib import Path

import pytest

from graphlang.grafr.runtime import GraphLangRuntime, load_graph
from graphlang.grafr.topology import check

COOKBOOK = Path(__file__).resolve().parent.parent / "cookbook"


class Scripted:
    """Plays the model: `rules` is a list of (substring of the prompt, reply or list of replies used in turn)."""
    name, adapter_name, model_override = "scripted", "echo", None

    def __init__(self, *rules):
        self.rules, self.calls = list(rules), []

    def generate(self, prompt, model=None, **opts):
        for needle, reply in self.rules:
            if needle in prompt:
                self.calls.append(needle)
                if isinstance(reply, list):
                    return reply.pop(0) if len(reply) > 1 else reply[0]
                return reply
        raise AssertionError(f"no rule for prompt: {prompt[:120]!r}")


def recipe(tmp_path, name):
    dest = tmp_path / name
    shutil.copytree(COOKBOOK / name, dest, ignore=shutil.ignore_patterns("output"))
    return dest / f"{name}.graph.yaml"


def run(path, llm, **params):
    graph = load_graph(path)
    errors, _ = check(graph)
    assert errors == []
    return GraphLangRuntime(graph, llm=llm, verbose=False, effects=True).execute(params)


# ---- guardrail -------------------------------------------------------------------------------------------------
def test_guardrail_answers_an_on_topic_question(tmp_path):
    llm = Scripted(("guardrail for a travel advisor", "YES"), ("You are a travel advisor", "Pack layers."))
    assert run(recipe(tmp_path, "guardrail"), llm, question="What to pack for Iceland?") == {"reply": "Pack layers."}
    assert "not about travel" not in " ".join(llm.calls)


def test_guardrail_declines_before_the_answering_prompt_sees_an_off_topic_question(tmp_path):
    llm = Scripted(("guardrail for a travel advisor", "no"), ("not about travel", "I can only help with travel."))
    out = run(recipe(tmp_path, "guardrail"), llm, question="Reverse a linked list")
    assert out == {"reply": "I can only help with travel."}
    assert "You are a travel advisor" not in llm.calls                   # the answering prompt never ran


# ---- supervisor ------------------------------------------------------------------------------------------------
def test_supervisor_approves_the_first_answer(tmp_path):
    llm = Scripted(("Answer the question", "Rayleigh scattering."), ("You supervise", "APPROVED"))
    out = run(recipe(tmp_path, "supervisor"), llm, question="Why is the sky blue?")
    assert out == {"answer": "Rayleigh scattering.", "status": "approved by the supervisor"}


def test_supervisor_sends_a_rejected_answer_back_with_its_note(tmp_path):
    seen = []

    class Llm(Scripted):
        def generate(self, prompt, model=None, **opts):
            seen.append(prompt)
            return super().generate(prompt, model, **opts)
    llm = Llm(("Answer the question", ["vague", "Light scatters off air, and blue scatters most."]), ("You supervise", ["Too vague: say why.", "APPROVED"]))
    out = run(recipe(tmp_path, "supervisor"), llm, question="Why is the sky blue?")
    assert out["answer"].startswith("Light scatters") and out["status"] == "approved by the supervisor"
    assert any("Too vague: say why." in p for p in seen)                 # the worker saw the supervisor's note


def test_supervisor_says_so_when_nothing_is_approved(tmp_path):
    llm = Scripted(("Answer the question", "meh"), ("You supervise", "Still wrong."))
    out = run(recipe(tmp_path, "supervisor"), llm, question="Why?", max_rounds=2)
    assert out["answer"] == "meh" and out["status"] == "not approved after 2 rounds; the last attempt is shown"
    assert llm.calls.count("You supervise") == 2                         # the cap held


# ---- self_heal -------------------------------------------------------------------------------------------------
def test_self_heal_accepts_a_valid_first_answer(tmp_path):
    good = json.dumps({"name": "Maria Lopez", "email": "m@x.example"})
    llm = Scripted(("Extract the contact", good))
    out = run(recipe(tmp_path, "self_heal"), llm, text="Maria Lopez m@x.example")
    assert out == {"record": good, "status": "valid"} and llm.calls == ["Extract the contact"]


def test_self_heal_shows_the_model_its_rejected_answer_and_retries(tmp_path):
    good = json.dumps({"name": "Tom Baker", "email": "unknown"})
    llm = Scripted(("Extract the contact", '```json\n{"name": "Tom Baker"}\n```'), ("earlier reply was checked", good))
    out = run(recipe(tmp_path, "self_heal"), llm, text="Call Tom Baker")
    assert out == {"record": good, "status": "valid"} and llm.calls == ["Extract the contact", "earlier reply was checked"]


def test_self_heal_gives_up_after_max_rounds(tmp_path):
    llm = Scripted(("Extract the contact", "nope"), ("earlier reply was checked", "still nope"))
    out = run(recipe(tmp_path, "self_heal"), llm, text="x", max_rounds=2)
    assert out["status"] == "still invalid after 2 rounds; the last attempt is shown" and out["record"] == "still nope"
    assert llm.calls.count("earlier reply was checked") == 2


# ---- notes_digest (QUERY, OBSERVE, EMIT behind a GUARD) ---------------------------------------------------------
def test_notes_digest_reads_summarises_observes_and_writes(tmp_path):
    from graphlang.grafr.output import RunOutput
    path = recipe(tmp_path, "notes_digest")
    out_dir = RunOutput(tmp_path / "runs", "notes_digest", "scripted")
    llm = Scripted(("Summarise the notes", "Digest: disk fixed; Priya moves staging."))
    graph = load_graph(path)
    out = GraphLangRuntime(graph, llm=llm, verbose=False, effects=True, node_output=out_dir).execute({})
    assert out == {"digest": "Digest: disk fixed; Priya moves staging."}
    assert (path.parent / "output" / "digest.md").read_text() == "Digest: disk fixed; Priya moves staging."
    observed = [json.loads(x) for x in (out_dir.dir / "observations.jsonl").read_text().splitlines()]
    assert observed[0]["label"] == "digest" and "Priya" in observed[0]["values"]["digest"]


def test_notes_digest_refuses_a_file_outside_its_folder(tmp_path):
    import yaml
    path = recipe(tmp_path, "notes_digest")
    graph = yaml.safe_load(path.read_text())
    next(n for n in graph["nodes"] if n["id"] == "read_notes")["config"]["file"] = "../secret.txt"
    path.write_text(yaml.safe_dump(graph, sort_keys=False))
    errors, _ = check(load_graph(path))
    assert any("outside the graph's folder" in m for m in errors)


def test_notes_digest_dry_run_writes_nothing(tmp_path):
    path = recipe(tmp_path, "notes_digest")
    llm = Scripted(("Summarise the notes", "Digest."))
    GraphLangRuntime(load_graph(path), llm=llm, verbose=False, effects=False).execute({})
    assert not (path.parent / "output").exists()


# ---- chat_memory ------------------------------------------------------------------------------------------------
def test_chat_memory_remembers_across_runs_with_a_sliding_window(tmp_path):
    path = recipe(tmp_path, "chat_memory")
    seen = []

    class Llm(Scripted):
        def generate(self, prompt, model=None, **opts):
            seen.append(prompt)
            return "Noted."
    llm = Llm()
    run(path, llm, message="My name is Wen.")
    assert "Earlier in the conversation (oldest first, may be empty):\n\n\nThe user now" in seen[0]          # nothing remembered yet
    run(path, llm, message="What is my name?")
    assert "You: My name is Wen.\nAssistant: Noted." in seen[1]
    memory = path.parent / "output" / "memory.md"
    assert memory.read_text() == "You: My name is Wen.\nAssistant: Noted.\nYou: What is my name?\nAssistant: Noted.\n"
    for i in range(6):                                                  # the window is the last 8 lines
        run(path, llm, message=f"turn {i}")
    assert "My name is Wen" not in seen[-1] and "turn 4" in seen[-1]


# ---- agent_notes (decide, act, observe) ------------------------------------------------------------------------
def test_agent_reads_a_note_then_answers_from_it(tmp_path):
    seen = []

    class Llm(Scripted):
        def generate(self, prompt, model=None, **opts):
            seen.append(prompt)
            return super().generate(prompt, model, **opts)
    llm = Llm(("Notes read so far", ['{"action": "read", "file": "pricing.md"}', '{"action": "answer", "text": "29 euro, SSO included."}']))
    out = run(recipe(tmp_path, "agent_notes"), llm, question="Team plan price?")
    assert out == {"answer": "29 euro, SSO included."}
    assert "Team plan: 29 euro" in seen[1] and "Team plan: 29 euro" not in seen[0]        # the second round saw what the first read


def test_agent_cannot_read_a_file_that_is_not_on_its_list(tmp_path):
    llm = Scripted(("Notes read so far", '{"action": "read", "file": "../policies/read.cedar"}'))
    out = run(recipe(tmp_path, "agent_notes"), llm, question="x")
    assert out == {"answer": "(no answer within 4 steps)"} and llm.calls == ["Notes read so far"]      # refused: no read, the loop ended


def test_agent_loop_is_capped(tmp_path):
    llm = Scripted(("Notes read so far", '{"action": "read", "file": "contacts.md"}'))
    out = run(recipe(tmp_path, "agent_notes"), llm, question="x", max_steps=3)
    assert out == {"answer": "(no answer within 3 steps)"} and llm.calls.count("Notes read so far") == 3
