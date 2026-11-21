"""Deterministic checks for the code pipeline, shared by its procedures (SPL calls them with CALL) and by the LangGraph
baseline. Nothing here calls a model.

The name check: the specification gives the function's name in its signature (the last top-level `def` in the prompt, for
HumanEval). If the code does not define that function, the attempt fails at once with a fixed message that the next attempt
receives, instead of going to the LLM tester, which does not check names and can pass code the hidden tests reject.
"""
import re

from spl.tools import spl_tool

_TOP_LEVEL_DEF = re.compile(r"^def\s+(\w+)\s*\(", re.M)


def required_name(spec: str) -> str:
    """The name of the last top-level function defined in the specification, or '' if there is none."""
    names = _TOP_LEVEL_DEF.findall(spec or "")
    return names[-1] if names else ""


def defines(code: str, name: str) -> bool:
    return bool(re.search(rf"^\s*def\s+{re.escape(name)}\s*\(", code or "", re.M))


def name_verdict(spec: str, code: str) -> str:
    """'' when the code defines the function the specification names (or the spec names none); otherwise a failure verdict
    in the same form the LLM tester uses ('[FAILED]' on the first line)."""
    name = required_name(spec)
    if not name or defines(code, name):
        return ""
    return (f"[FAILED]\nThe specification requires a function named `{name}`, and the code does not define it. "
            f"Keep that name and signature exactly as the specification gives them.")


@spl_tool
def name_check(spec: str, code: str) -> str:
    """SPL tool: the name verdict for a code attempt ('' if the name is right)."""
    return name_verdict(spec, code)
