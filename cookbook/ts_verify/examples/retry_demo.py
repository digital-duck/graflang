"""Watch the retry loop without a real model: a scripted "model" writes TypeScript with a type error first, then fixes it.

    python cookbook/ts_verify/examples/retry_demo.py          # from the repo root; needs `npm install` in cookbook/ts_verify

It runs the real graph with the real tools (tsc, Node, Python); only the LLM is replaced.
"""
from pathlib import Path

from graphlang.grafr.runtime import GraphLangRuntime, load_graph

HERE = Path(__file__).resolve().parent.parent

ATTEMPTS = [
    # attempt 1: the return type says number, the body returns a string
    'export function slugify(title: string): number {\n  return title.toLowerCase();\n}',
    # attempt 2: the fix a model would make after reading the compiler's message
    'export function slugify(title: string): string {\n'
    '  return title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");\n}',
]


class ScriptedModel:
    name, adapter_name, model_override = "scripted", "echo", None

    def __init__(self):
        self.prompts = []

    def generate(self, prompt, model=None, **opts):
        self.prompts.append(prompt)
        return ATTEMPTS[len(self.prompts) - 1]


def section(prompt, heading):
    """The text under `heading` in the prompt, up to the next blank line."""
    return prompt.split(heading, 1)[1].strip().split("\n\n")[0]


model = ScriptedModel()
result = GraphLangRuntime(load_graph(HERE / "ts_verify.graph.yaml"), llm=model, verbose=False).execute({
    "spec": "slugify(title): lowercase; every run of characters that are not ASCII letters or digits becomes one hyphen",
    "function": "slugify",
    "cases": "examples/slugify.cases.json",
})["result"]

print("ATTEMPT 1 (written by the model):\n" + ATTEMPTS[0] + "\n")
print("WHAT THE COMPILER SAID, as the model saw it in its second prompt:")
print(section(model.prompts[1], "Type errors from the compiler (JSON):") + "\n")
print("ATTEMPT 2 (the fix):\n" + result["code"])
print(result["report"])
