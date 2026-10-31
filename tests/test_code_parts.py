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


def test_the_prompts_are_the_spl_sub_workflows_text_plus_the_file_layout():
    for part, spl in (("analyze_spec", "00_analyze_spec"), ("write_code", "01_generate_code"), ("review_code", "02_review_code"), ("improve_code", "03_improve_code")):
        body = (PIPELINE / f"{spl}.spl").read_text().split("AS $$\n", 1)[1].split("\n$$;", 1)[0]
        text = (DIR / "sub_graph" / "prompts" / f"{part}.md").read_text().strip()
        original = re.sub(r"\{(\w+)\}", r"{{in_\1}}", body).strip()
        # analyze and review are the SPL text; write and improve add the instruction to lay the code out as project files
        assert text == original if part in ("analyze_spec", "review_code") else text.startswith(original) and "=== FILE:" in text


def test_a_ready_spec_flows_through_write_review_and_improve():
    llm = Scripted("[READY]\nbuild it", "CODE1", "REVIEW", "=== FILE: pal/core.py ===\ndef f():\n    return 1\n=== FILE: README.md ===\n# pal\n")
    out = GraphLangRuntime(load_graph(GRAPH), llm=llm, verbose=False).execute({"spec": "is_palindrome(s)", "lang": "python"})
    assert out["review"] == "REVIEW" and set(out["code"]) == {"pal/core.py", "pal/__init__.py", "README.md"}
    assert out["code"]["pal/core.py"] == "def f():\n    return 1\n" and out["code"]["pal/__init__.py"] == ""
    assert "is_palindrome(s)" in llm.prompts[0] and "python developer" in llm.prompts[1]
    assert "CODE1" in llm.prompts[2] and "REVIEW" in llm.prompts[3] and "CODE1" in llm.prompts[3]


def test_a_vague_spec_stops_after_the_analysis():
    llm = Scripted("[VAGUE]\nmissing everything")
    out = GraphLangRuntime(load_graph(GRAPH), llm=llm, verbose=False).execute({"spec": "make something useful"})
    assert len(llm.prompts) == 1 and not out.get("code")


def _collect(text, lang="python", spec="a spec"):
    import json
    import subprocess
    import sys
    done = subprocess.run([sys.executable, "-I", str(DIR / "tools" / "collect_files.py")], input=json.dumps({"text": text, "lang": lang, "spec": spec}),
                          capture_output=True, text=True)
    return done


def test_the_collector_splits_files_strips_fences_and_adds_init_and_readme():
    import json
    text = "=== FILE: pkg/sub/mod.py ===\n```python\nx = 1\n```\n=== FILE: pkg/other.py ===\nfrom pkg.sub.mod import x\n"
    files = json.loads(_collect(text, spec="do x").stdout)
    assert files["pkg/sub/mod.py"] == "x = 1\n" and files["pkg/other.py"] == "from pkg.sub.mod import x\n"
    assert {"pkg/__init__.py", "pkg/sub/__init__.py"} <= set(files) and "do x" in files["README.md"]


def test_a_reply_without_markers_is_one_main_file():
    import json
    assert json.loads(_collect("```go\npackage main\n```", lang="go").stdout)["main.go"] == "package main\n"


def test_the_collector_refuses_a_path_that_escapes_the_folder():
    done = _collect("=== FILE: ../evil.py ===\nx\n")
    assert done.returncode != 0 and "unsafe path" in done.stderr
