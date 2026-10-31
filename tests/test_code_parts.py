"""cookbook/code_parts: code_pipeline's first steps as parts, with no .spl file and no SPL.py."""
import re
from pathlib import Path

from graphlang.grafr.runtime import GraphLangRuntime, load_graph
from graphlang.grafr.topology import check
from test_lifecycle import Scripted

DIR = Path(__file__).parent.parent / "cookbook" / "code_parts"
GRAPH = DIR / "code_parts.graph.yaml"
PIPELINE = DIR.parent / "code_pipeline"


def test_it_needs_no_spl_file_and_no_procedure():
    assert not list(DIR.rglob("*.spl"))
    graph = load_graph(GRAPH)
    assert check(graph) == ([], []) and not any("procedure_ref" in n.get("config", {}) for n in graph["nodes"])


def test_the_prompts_are_the_ones_the_spl_sub_workflows_carry():
    for part, spl in (("analyze_spec", "00_analyze_spec"), ("write_code", "01_generate_code"), ("review_code", "02_review_code"), ("improve_code", "03_improve_code")):
        body = (PIPELINE / f"{spl}.spl").read_text().split("AS $$\n", 1)[1].split("\n$$;", 1)[0]
        assert (DIR / "parts" / "prompts" / f"{part}.md").read_text().strip() == re.sub(r"\{(\w+)\}", r"{{in_\1}}", body).strip()


def test_a_ready_spec_flows_through_write_review_and_improve():
    llm = Scripted("[READY]\nbuild it", "CODE1", "REVIEW", "CODE2")
    out = GraphLangRuntime(load_graph(GRAPH), llm=llm, verbose=False).execute({"spec": "is_palindrome(s)", "lang": "go"})
    assert out == {"code": "CODE2", "review": "REVIEW"}
    assert "is_palindrome(s)" in llm.prompts[0] and "go developer" in llm.prompts[1]
    assert "CODE1" in llm.prompts[2] and "REVIEW" in llm.prompts[3] and "CODE1" in llm.prompts[3]


def test_a_vague_spec_stops_after_the_analysis():
    llm = Scripted("[VAGUE]\nmissing everything")
    out = GraphLangRuntime(load_graph(GRAPH), llm=llm, verbose=False).execute({"spec": "make something useful"})
    assert len(llm.prompts) == 1 and not out.get("code")
