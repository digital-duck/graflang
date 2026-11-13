"""Searching the recipes of the work area: one entry per recipe (not per file), meaning from an embedding model plus words (BM25).
Plain `pytest` is offline: the embedding model is a stand-in here. The test that uses a real local embedding model is `--mode llm`."""
import shutil
from pathlib import Path

import numpy as np
import pytest

from graphlang import embedding as E
from graphlang import recipe_index as R
from graphlang import workspace as ws

COOKBOOK = Path(__file__).parent.parent / "cookbook"

# a stand-in embedding model: each concept is a direction, and a text points where its words point
CONCEPTS = {"code": ["code", "coding", "programming", "typescript", "tests", "pipeline", "review"],
            "data": ["personal", "pii", "privacy", "compliance", "audit", "document"],
            "book": ["book", "chapter", "chapters", "audience", "outline"],
            "essay": ["essay", "critique", "draft", "refine", "rewrite"],
            "container": ["docker", "container", "image"]}


def fake_embed(texts):
    """Concept directions plus a small text-specific random part, so unrelated texts are nearly orthogonal, as real embeddings are not quite."""
    import hashlib
    out = np.zeros((len(texts), len(CONCEPTS) + 16), dtype="float32")
    for i, text in enumerate(texts):
        for w in R.words(text):
            for j, group in enumerate(CONCEPTS.values()):
                if w in {R.stem(x) for x in group}:
                    out[i, j] += 1
        seed = int(hashlib.sha1(text.encode()).hexdigest()[:8], 16)
        out[i, len(CONCEPTS):] = np.random.default_rng(seed).normal(size=16) * 0.12
    return out / np.linalg.norm(out, axis=1, keepdims=True)


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("GRAFLANG_HOME", str(tmp_path / "home"))
    ws.install_cookbook(COOKBOOK, ws.default_src_dir())
    return tmp_path / "home"


@pytest.fixture()
def words_only(home):
    return R.RecipeIndex.build(ws.Workspace())


@pytest.fixture()
def meaning(home):
    return R.RecipeIndex.build(ws.Workspace(), E.Embedder("fake:concepts", fake_embed), "meaning and words (fake)")


def top(index, query, **kw):
    return [h.entry.folder.name for h in index.search(query, **kw)]


def test_the_stemmer_makes_coding_and_code_agree_and_words_split_names():
    assert R.stem("coding") == R.stem("code") == R.stem("codes") == "cod" and R.stem("pipelines") == R.stem("pipeline")
    assert R.words("self_refine the Recipes") == ["self", "refin", "recip"] and R.words("the of and") == []


def test_one_entry_is_one_recipe_not_one_file(words_only):
    names = [e.folder.name for e in words_only.entries]
    assert len(names) == len(set(names))
    audit = next(e for e in words_only.entries if e.folder.name == "compliance_audit")
    assert audit.graph.name == "compliance_audit.graph.yaml" and "compliance_audit_llm_only.graph.yaml" in audit.graphs
    demo = next(e for e in words_only.entries if e.folder.name == "expand_demo")
    assert "sub_graph/explain.graph.yaml" in demo.graphs and "subgraph" in demo.tags
    assert all(e.title and e.description for e in words_only.entries) and all(e.shipped for e in words_only.entries)


def test_words_find_coding_recipes_through_the_stem(words_only):
    assert "code_pipeline" in top(words_only, "coding")
    assert top(words_only, "check personal data")[0] == "compliance_audit"
    assert top(words_only, "write a book with chapters for a chosen audience")[0] == "your_book"


def test_words_only_search_keeps_the_best_and_close_ones_not_a_long_tail(words_only):
    hits = words_only.search("code pipeline", k=10)
    assert hits[0].entry.folder.name == "code_pipeline" and len(hits) <= 5
    assert [h.score for h in hits] == sorted((h.score for h in hits), reverse=True)
    assert all(h.score >= R.WORDS_FRACTION * hits[0].score for h in hits)


def test_a_search_with_no_shared_word_returns_nothing(words_only):
    assert words_only.search("zzzqqq xxyyzz") == [] and words_only.search("   ") == [] and words_only.search("the of and") == []


def test_meaning_finds_a_recipe_by_a_word_it_does_not_contain(meaning):
    assert meaning.semantic and top(meaning, "programming")[0] in {"code_pipeline", "code_parts", "ts_verify"}
    assert top(meaning, "privacy")[0] == "compliance_audit"                         # "privacy" is in neither its name nor its readme
    assert top(meaning, "docker")[0] == "container_demo"


def test_meaning_keeps_only_the_recipes_close_to_the_best_and_says_when_none_is_close(meaning):
    hits = meaning.search("personal data privacy audit", k=10)
    assert [h.entry.folder.name for h in hits] == ["compliance_audit"]
    assert all(h.meaning is not None for h in hits)
    assert meaning.search("cooking dinner for friends", k=10) == []                 # nothing is close: the floor, not a long tail


def test_recipes_that_run_programs_can_be_left_out(meaning, words_only):
    for index in (meaning, words_only):
        with_code = {e.folder.name for e in index.entries if e.has_code}
        assert "code_parts" in with_code
        assert not (set(top(index, "code review tests", k=20, allow_code=False)) & with_code)


def test_the_search_can_be_limited_to_one_root(home):
    shutil.copytree(COOKBOOK / "self_refine", ws.apps_dir() / "my_essay", ignore=shutil.ignore_patterns("output"))
    idx = R.RecipeIndex.build(ws.Workspace())
    assert top(idx, "essay critique", roots=["apps"]) == ["my_essay"]
    assert {"my_essay", "self_refine"} <= set(top(idx, "essay critique", roots=["cookbook", "apps"]))
    assert [e.folder.name for e in idx.listing(roots=["apps"])] == ["my_essay"]


def test_a_failing_embedding_model_falls_back_to_words_and_says_so(home):
    def broken(texts):
        raise ConnectionError("ollama is not running")
    idx = R.RecipeIndex.build(ws.Workspace(), E.Embedder("ollama:x", broken))
    assert not idx.semantic and "words only" in idx.note and "ollama is not running" in idx.note
    assert "code_pipeline" in top(idx, "coding")


def test_a_model_that_fails_at_query_time_falls_back_to_words(home):
    calls = {"n": 0}

    def flaky(texts):
        calls["n"] += 1
        if calls["n"] > 1:
            raise ConnectionError("gone")
        return fake_embed(texts)
    idx = R.RecipeIndex.build(ws.Workspace(), E.Embedder("fake:flaky", flaky))
    assert idx.semantic and "code_pipeline" in top(idx, "coding")
    assert "words only" in idx.note


def test_embeddings_are_cached_so_an_unchanged_recipe_is_embedded_once(home):
    seen = []

    def counting(texts):
        seen.append(len(texts))
        return fake_embed(texts)
    embedder = E.Embedder("fake:cache", counting)
    R.RecipeIndex.build(ws.Workspace(), embedder)
    first = sum(seen)
    R.RecipeIndex.build(ws.Workspace(), embedder)
    assert first == len(R.RecipeIndex.build(ws.Workspace()).entries) and sum(seen) == first               # the second build embedded nothing
    (ws.default_src_dir() / "self_refine" / "readme.md").write_text("# self_refine\n\nA new description of the recipe.")
    R.RecipeIndex.build(ws.Workspace(), embedder)
    assert sum(seen) == first + 1                                                                         # only the changed recipe


def test_the_signature_changes_when_a_recipe_changes(home):
    w = ws.Workspace()
    before = R.RecipeIndex.signature(w)
    assert R.RecipeIndex.signature(w) == before
    (ws.default_src_dir() / "self_refine" / "readme.md").write_text("# changed\n\nnew words")
    assert R.RecipeIndex.signature(w) != before


def test_reference_text_shows_description_graph_and_prompts_and_is_bounded(words_only):
    entry = next(e for e in words_only.entries if e.folder.name == "self_refine")
    text = R.reference_text([entry])
    assert "Existing recipe `self_refine`" in text and "=== FILE: self_refine.graph.yaml ===" in text and "=== FILE: prompts/draft.md ===" in text
    big = next(e for e in words_only.entries if e.folder.name == "code_pipeline")
    assert len(R.reference_text([big])) < R.MAX_REFERENCE_GRAPH + R.MAX_REFERENCE_PROMPTS + 2000


def test_a_broken_graph_is_still_listed(tmp_path, monkeypatch):
    monkeypatch.setenv("GRAFLANG_HOME", str(tmp_path / "home"))
    folder = ws.apps_dir() / "broken"
    folder.mkdir(parents=True)
    (folder / "broken.graph.yaml").write_text("a: [\n")
    idx = R.RecipeIndex.build(ws.Workspace())
    assert [e.folder.name for e in idx.entries] == ["broken"] and idx.entries[0].title == "broken"


# ── choosing the embedding model ─────────────────────────────────────────────────────────────────

def test_none_switches_embedding_off_and_an_unknown_provider_is_not_an_error():
    assert E.resolve("none")[0] is None
    embedder, note = E.resolve("nonesuch:model")
    assert embedder is None and note.startswith("words only")


def test_auto_prefers_sentence_transformers_then_a_local_ollama_embedding_model(monkeypatch):
    monkeypatch.setattr(E, "_ollama_models", lambda host=None: ["gemma3:latest", "qwen3-embedding:0.6b"])
    monkeypatch.setattr("importlib.util.find_spec", lambda name: None if name == "sentence_transformers" else object())
    embedder, note = E.resolve("auto")
    assert embedder is not None and embedder.spec == "ollama:qwen3-embedding:0.6b" and "ollama:qwen3-embedding" in note
    monkeypatch.setattr(E, "_ollama_models", lambda host=None: ["gemma3:latest"])
    assert E.resolve("auto")[0] is None
    monkeypatch.setattr(E, "_ollama_models", lambda host=None: (_ for _ in ()).throw(ConnectionError("no ollama")))
    embedder, note = E.resolve("auto")
    assert embedder is None and "no embedding model found" in note


# ── a real embedding model (local Ollama, free): the cases from the bug report ───────────────────

@pytest.mark.llm
def test_with_a_real_embedding_model_coding_finds_the_code_pipeline_and_code_pipeline_is_few(home):
    embedder, note = E.resolve("auto")
    if embedder is None:
        pytest.skip(note)
    idx = R.RecipeIndex.build(ws.Workspace(), embedder, note)
    assert idx.semantic, idx.note
    assert top(idx, "coding", k=10) == ["code_pipeline"]                          # the bug report: "coding" did not show the code pipeline
    hits = top(idx, "code pipeline", k=10)
    assert hits[:1] == ["code_pipeline"] and len(hits) <= 3 and len(hits) == len(set(hits))      # and this one gave too many, one per file
    assert top(idx, "cooking dinner for friends") == []
    assert top(idx, "check personal data")[:1] == ["compliance_audit"]
    assert top(idx, "docker")[:1] == ["container_demo"]


def test_a_query_is_embedded_once_however_often_it_is_searched(home):
    calls = []

    def counting(texts):
        calls.append(list(texts))
        return fake_embed(texts)
    idx = R.RecipeIndex.build(ws.Workspace(), E.Embedder("fake:counting", counting), "meaning and words (fake)")
    before = len(calls)
    first = idx.search("write code and test it")
    second = idx.search("write code and test it")
    assert [h.entry.key for h in first] == [h.entry.key for h in second]
    assert len(calls) == before + 1


def test_a_declared_workflow_description_is_the_recipes_description(tmp_path):
    folder = tmp_path / "r"
    folder.mkdir()
    (folder / "r.graph.yaml").write_text(
        "# a header comment\nversion: 1.0-graph\nworkflow:\n  name: r\n  description: |\n    Triage support tickets by urgency.\n"
        "nodes:\n- {id: a, type: INPUT, ports: [entry]}\n- {id: b, type: OUTPUT, ports: [trigger]}\n"
        "edges:\n- {source: a.entry, target: b.trigger, type: triggers}\n", encoding="utf-8")
    (folder / "readme.md").write_text("# R\n\nThe readme says something else.\n", encoding="utf-8")
    entry = R.describe("apps", folder, True)
    assert entry.description == "Triage support tickets by urgency."
    from graphlang.grafr.runtime import load_graph
    assert load_graph(folder / "r.graph.yaml")["workflow"]["description"].startswith("Triage")        # the schema accepts it
