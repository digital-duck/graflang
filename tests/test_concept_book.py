"""cookbook/concept_book: a chapter the reviewer asks to revise is revised, and the compile step gets the final chapters."""
from pathlib import Path

from graphlang.grafr.runtime import GraphLangRuntime, load_graph
from graphlang.grafr.topology import check
from test_lifecycle import Scripted

GRAPH = Path(__file__).parent.parent / "cookbook" / "concept_book" / "build_concept_book.graph.yaml"


def run(*replies, chapters=2):
    llm = Scripted(*replies)
    graph = load_graph(GRAPH)
    assert check(graph) == ([], [])
    out = GraphLangRuntime(graph, llm=llm, verbose=False).execute({"subject": "entropy", "num_chapters": chapters})
    return out, llm


def test_approved_chapters_are_kept_and_a_revision_is_asked_only_when_needed():
    out, llm = run("OUTLINE", "CH0", "APPROVED", "CH1", "REVISION_NEEDED\nadd an example", "CH1-REVISED", "BOOK")
    assert out == {"book": "BOOK"} and len(llm.prompts) == 7           # outline, write, review, write, review, revise, compile (no revise for chapter 0)
    revise = llm.prompts[5]
    assert "CH1" in revise and "add an example" in revise and "entropy" in revise and "OUTLINE" in revise      # the chapter, the feedback, the context
    compile_prompt = llm.prompts[6]
    assert "CH0" in compile_prompt and "CH1-REVISED" in compile_prompt and "add an example" not in compile_prompt
    assert "CH1\n" not in compile_prompt.replace("CH1-REVISED", "")    # the unrevised draft is not what gets compiled


def test_the_verdict_is_read_whatever_its_formatting():
    out, llm = run("OUTLINE", "CH0", "**revision_needed**: too thin", "CH0-V2", "BOOK", chapters=1)
    assert len(llm.prompts) == 5 and "CH0-V2" in llm.prompts[4]


def test_all_approved_makes_no_revision_calls():
    _, llm = run("OUTLINE", "CH0", "APPROVED", "CH1", "APPROVED", "BOOK")
    assert len(llm.prompts) == 6


def test_each_chapter_is_asked_for_by_the_number_the_outline_uses():
    """The loop counter is 0-based and the outline says "Chapter 1", "Chapter 2": a prompt that passed the raw counter made the second
    chapter a second 'Chapter 1' (see the output of 2026-10-31 17:25)."""
    _, llm = run("OUTLINE", "CH1", "APPROVED", "CH2", "APPROVED", "BOOK", chapters=2)
    first, second = llm.prompts[1], llm.prompts[3]
    assert "Write chapter 1 of 2" in first and 'heads "Chapter 1"' in first
    assert "Write chapter 2 of 2" in second and 'heads "Chapter 2"' in second and "OUTLINE" in second
    assert "chapter index" not in second.lower()


def run_with(inputs, *replies):
    llm = Scripted(*replies)
    out = GraphLangRuntime(load_graph(GRAPH), llm=llm, verbose=False).execute({"subject": "entropy", "num_chapters": 1, **inputs})
    return out, llm


def test_audience_and_style_reach_every_prompt():
    _, llm = run_with({"audience": "research", "style": "Socratic, one question at a time"},
                      "OUTLINE", "CH1", "REVISION_NEEDED\nmore rigour", "CH1-V2", "BOOK")
    names = ["outline", "chapter", "review", "revise", "compile"]
    assert len(llm.prompts) == 5
    for name, prompt in zip(names, llm.prompts):
        assert "Audience: research" in prompt and "Socratic, one question at a time" in prompt, name


def test_the_defaults_are_the_intro_audience_and_a_plain_style():
    _, llm = run_with({}, "OUTLINE", "CH1", "APPROVED", "BOOK")
    assert "Audience: intro" in llm.prompts[0] and "clear and conversational, with concrete examples" in llm.prompts[1]


def test_the_four_levels_are_described_where_the_audience_matters():
    _, llm = run_with({}, "OUTLINE", "CH1", "APPROVED", "BOOK")
    for prompt in llm.prompts[:3]:                                  # outline, chapter and review all carry the level guide
        for level in ("intro:", "intermediate:", "advanced:", "research:"):
            assert level in prompt
