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
    assert "is_palindrome(s)" in llm.prompts[0] and "python developer" in llm.prompts[1] and out["report"].startswith("[PASSED]")
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


BAD = "=== FILE: pal/core.py ===\ndef f(:\n    pass\n"
GOOD = ("=== FILE: pal/core.py ===\ndef f():\n    return 1\n=== FILE: tests/test_core.py ===\n"
        "from pal.core import f\n\n\ndef test_f():\n    assert f() == 1\n")


def test_a_failed_verification_goes_back_into_the_next_improve():
    llm = Scripted("[READY]\nok", "FIRST", "REVIEW", BAD, GOOD)
    out = GraphLangRuntime(load_graph(GRAPH), llm=llm, verbose=False).execute({"spec": "f returns 1", "lang": "python"})
    assert len(llm.prompts) == 5                                      # analyze, write, review, improve (fails), improve (fixed)
    second = llm.prompts[4]
    assert "[FAILED]" in second and "syntax" in second and "def f(:" in second          # the report and the code it was about
    assert out["report"].startswith("[PASSED]") and "pal/core.py" in out["code"] and "def f():" in out["code"]["pal/core.py"]


def test_the_loop_stops_at_max_cycles_with_the_last_report():
    llm = Scripted("[READY]\nok", "FIRST", "REVIEW", BAD, BAD)
    out = GraphLangRuntime(load_graph(GRAPH), llm=llm, verbose=False).execute({"spec": "f", "lang": "python", "max_cycles": 2})
    assert len(llm.prompts) == 5 and out["report"].startswith("[FAILED]")


def _verify(files, smoke="", lang="python"):
    import json
    import subprocess
    import sys
    done = subprocess.run([sys.executable, "-I", str(DIR / "tools" / "verify_project.py")], capture_output=True, text=True,
                          input=json.dumps({"files": files, "lang": lang, "smoke": smoke}))
    return json.loads(done.stdout)


def test_verification_runs_syntax_imports_tests_and_the_smoke_code():
    files = {"p/__init__.py": "", "p/core.py": "def f():\n    return 1\n", "tests/test_core.py": "from p.core import f\n\n\ndef test_f():\n    assert f() == 1\n"}
    ok = _verify(files)
    assert ok["passed"] and "**syntax:** ok" in ok["report"] and "**tests:** ok" in ok["report"]
    wrong = _verify(files, smoke="from p.core import f\nassert f() == 2")
    assert not wrong["passed"] and "**smoke:** FAILED" in wrong["report"] and "AssertionError" in wrong["report"]    # what fake-based tests miss
    broken = _verify({**files, "tests/test_core.py": "from p.core import f\n\n\ndef test_f():\n    assert f() == 2\n"})
    assert not broken["passed"] and "**tests:** FAILED" in broken["report"]


def test_a_missing_third_party_package_is_skipped_not_failed_and_another_language_is_not_checked():
    skipped = _verify({"p/__init__.py": "", "p/a.py": "import not_installed_pkg_xyz\n"})
    assert skipped["passed"] and "not installed here, skipped: not_installed_pkg_xyz" in skipped["report"]
    assert _verify({"main.go": "package main"}, lang="go")["report"].startswith("[PASSED]\n\nNot checked")
