"""The code_pipeline written as a Python LangGraph program: the baseline arm.

It uses the very same eight prompts as the SPL and GraphLang arms (read from the .spl files, so they cannot drift), the same
`clean_code` post-processing, the same gates and the same retry rule. Only the orchestration differs. Counted separately in
LOC: this file is the orchestration, the prompts stay in the .spl files, and `llm` is the same dd-llm adapter GraphLang uses.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "cookbook" / "code_pipeline"
_FUNCTION = re.compile(r"CREATE FUNCTION (\w+)\(([^)]*)\)\s*RETURN TEXT\s*AS \$\$\n(.*?)\n\$\$;", re.S)


def load_prompts() -> dict:
    """{function name: (parameter names, template)} from the .spl files of the cookbook recipe."""
    found = {}
    for path in sorted(PROMPTS_DIR.glob("0[0-7]_*.spl")):
        for name, params, body in _FUNCTION.findall(path.read_text(encoding="utf-8")):
            found[name] = ([p.split()[0] for p in params.split(",") if p.strip()], body)
    return found


def fill(prompts: dict, name: str, **values) -> str:
    params, body = prompts[name]
    return re.sub(r"\{(\w+)\}", lambda m: values.get(m.group(1), "") if m.group(1) in params else m.group(0), body)


class State(TypedDict, total=False):
    spec: str
    lang: str
    max_cycles: int
    analysis: str
    code: str
    feedback: str
    verdict: str
    cycle: int
    passed: bool
    docs: str
    extracted: str
    status: str


def build(llm, model: str, clean_code):
    prompts = load_prompts()
    ask = lambda name, **v: llm.generate(fill(prompts, name, **v), model=model)

    def analyze(s):
        return {"analysis": ask("spec_analyst", spec=s["spec"])}

    def generate(s):
        return {"code": clean_code(ask("coder", spec=s["spec"], lang=s["lang"])), "cycle": s.get("cycle", 0) + 1}

    def review(s):
        return {"feedback": ask("reviewer", code=s["code"], lang=s["lang"])}

    def improve(s):
        return {"code": clean_code(ask("refactor", code=s["code"], feedback=s["feedback"], test_result="", lang=s["lang"]))}

    def test(s):
        verdict = ask("run_tests", code=s["code"], spec=s["spec"], lang=s["lang"])
        return {"verdict": verdict, "passed": "[PASSED]" in verdict}

    def document(s):
        return {"docs": ask("write_docs", code=s["code"], spec=s["spec"], lang=s["lang"])}

    def extract(s):
        return {"extracted": ask("reverse_spec", code=s["code"])}

    g = StateGraph(State)
    for name, fn in [("analyze", analyze), ("generate", generate), ("review", review), ("improve", improve),
                     ("test", test), ("document", document), ("extract", extract)]:
        g.add_node(name, fn)
    g.add_edge(START, "analyze")
    g.add_conditional_edges("analyze", lambda s: "generate" if "[READY]" in s["analysis"] else END)
    g.add_edge("generate", "review")
    g.add_edge("review", "improve")
    g.add_edge("improve", "test")
    g.add_conditional_edges("test", lambda s: "document" if s["passed"] or s["cycle"] >= s["max_cycles"] else "generate")
    g.add_edge("document", "extract")
    g.add_edge("extract", END)
    return g.compile()
