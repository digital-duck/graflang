"""The shared code_pipeline experiment's oracle and LangGraph baseline (no LLM, no network)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "experiments" / "code_pipeline"))

import oracle  # noqa: E402

TASK = {
    "task_id": "T/0",
    "prompt": "from typing import List\n\n\ndef total(xs: List[int]) -> int:\n    \"\"\"Sum of xs.\"\"\"\n",
    "entry_point": "total",
    "test": "def check(candidate):\n    assert candidate([1, 2, 3]) == 6\n    assert candidate([]) == 0\n",
}


def test_correct_code_passes_even_without_repeating_the_prompts_imports():
    assert oracle.check(TASK, "def total(xs: List[int]) -> int:\n    return sum(xs)\n").passed


@pytest.mark.parametrize("code, reason", [
    ("", "no_code"),
    ("   \n", "no_code"),
    ("def total(xs):\n    return 0\n", "AssertionError"),
    ("def total(xs) return", "SyntaxError"),
    ("def other(xs):\n    return sum(xs)\n", "NameError"),          # the function was renamed
    ("def total(xs):\n    while True:\n        pass\n", ""),          # never finishes
])
def test_everything_else_is_a_failure(code, reason):
    verdict = oracle.check(TASK, code, timeout=2)
    assert not verdict.passed
    assert reason in verdict.reason or verdict.reason == "timeout"


def test_the_oracle_does_not_see_the_environment(monkeypatch):
    monkeypatch.setenv("SECRET_TOKEN", "x")
    code = "import os\n\ndef total(xs):\n    assert 'SECRET_TOKEN' not in os.environ\n    return sum(xs)\n"
    assert oracle.check(TASK, code).passed


def test_the_langgraph_arm_reads_the_same_prompts_as_the_other_arms():
    pytest.importorskip("langgraph")
    import lg_pipeline
    prompts = lg_pipeline.load_prompts()
    assert {"spec_analyst", "coder", "reviewer", "refactor", "run_tests", "write_docs", "reverse_spec"} <= set(prompts)
    text = lg_pipeline.fill(prompts, "coder", spec="make {lang} work", lang="python")
    assert "make {lang} work" in text and "{spec}" not in text         # a value that looks like a placeholder is left alone


def test_the_langgraph_arm_follows_the_pipeline_with_a_scripted_model():
    pytest.importorskip("langgraph")
    import lg_pipeline

    class Scripted:
        def __init__(self, tester):
            self.tester, self.calls = list(tester), []

        def generate(self, prompt, model=None, **opts):
            if "data-protection" in prompt:
                raise AssertionError
            if "automated test suite" in prompt:
                self.calls.append("test")
                return self.tester.pop(0)
            for key, name in (("specification analyst", "analyze"), ("senior", "review"), ("improving code", "improve"),
                              ("expert python developer.\n\nWrite", "generate")):
                if key in prompt:
                    self.calls.append(name)
                    return "[READY]" if name == "analyze" else "def f():\n    return 1"
            self.calls.append("other")
            return "text"

    llm = Scripted(["[FAILED] no", "[PASSED]"])
    final = lg_pipeline.build(llm, "m", lambda t: t).invoke({"spec": "s", "lang": "python", "max_cycles": 3})
    assert final["cycle"] == 2 and final["passed"] is True
    assert llm.calls.count("test") == 2 and llm.calls.count("generate") == 2
