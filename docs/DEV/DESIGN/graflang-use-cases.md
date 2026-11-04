# What GraphLang is for, and what it is not

Status: position paper and decisions (2026-11-04). Written after building a "hello world" app in the editor, which came out larger than the task. The owner's reading: *GraphLang is designed for agentic workflows, complex tasks; it is too complex for a minimal task, because it creates an abstraction over a language.* This note records that assessment, what follows from it, and the answer to the question every newcomer asks: **"How do I write Hello World in GraphLang?"**

## What GraphLang is designed for

**The problem it is designed to solve is orchestrating complex workflows that involve both LLM tasks and solver tasks**: steps where a model does what needs language (reading, writing, judging) and steps where a deterministic solver, program or rule engine does what must not vary (computing, checking, deciding), composed in one declarative graph that can be checked before it runs. This is the setting of the paper *Orchestrating Workflows with Declarative Deterministic–Probabilistic Composition* ([arXiv:2607.07727](https://arxiv.org/pdf/2607.07727)), which GraphLang builds on: the probabilistic parts (models) and the deterministic parts (solvers, rules, policy) are first-class, typed steps of one workflow, and the graph says which does what. The compliance audit below is the clearest example: a model reads and rewrites, rules decide, a policy has the last word.

**GraphLang is not a general-purpose programming language, and it should not be used as one.** It is a *workflow* language for work where the shape of the work, the checks on it and the rules around it matter as much as the code:

| Use it when | Why a graph helps |
|---|---|
| A task has **several steps, branches or loops** and a model decides or writes at some of them | The control flow is data: `graf validate` checks wiring, dead ends, races and deadlocks before anything runs |
| **Risky actions** (read or write files, send e-mail, run generated code, call a webhook) must be controlled | A risky node is refused unless it sits behind a Cedar `GUARD`; paths cannot leave the graph's folder; a delta can never add code |
| **Policy and audit** matter: who may do what, what was spent, what happened | Cedar policy on nodes and mutations, `parts_policy` on composed recipes, budgets (`max_llm_calls`), JSONL logs, `graf trace` |
| A **person** is part of the process | `DECISION` is a node like any other, with a timeout, a default and an identity |
| The workflow should **change itself** under rules (a model adds or rewires steps) | `MUTATE` and `add_part` apply a delta only after schema, Cedar, budget and invariant checks |
| Workflows are **assembled from other workflows** | Recipes are parts with interfaces, capabilities and costs; a model can pick from a catalogue |
| Several people or tools must **read, review and compare** the process | One declarative file, drawable (`graf vis`), describable in words (`graf describe`), exportable (`graf compile --lang spl`) |

> **Do not use it for:** a single model call, a script, a function, a data transformation, a calculation, or any task with fewer than about five steps and no policy, audit or composition need. Write a Python script (or one `llm` call). The graph would be longer than the program and harder to read.
>
> **Rule of thumb: if you would not draw it on a whiteboard, do not write it as a graph.**

## The assessment: Hello World in the editor

The task, as asked: write a program that prints "Hello, <name>!" in a language, with two modes (an LLM writes it, or a deterministic tool does), then run it.

What came out: **13 nodes and about 30 edges** (`cookbook/hello_world`, before this note's changes; it is now 9 short steps). In Python, the same logic is about 30 lines: an `if mode == "solver"`, one model call, a check on the language, a `subprocess.run`.

- **The graph re-encodes ordinary code.** Each `if`, sequence step and join became nodes, ports and wires. Nothing in it is something the script cannot do; it is only longer and harder to read at a glance. This is the same criticism made of LangGraph, and it is fair.
- **Most of the size was added, not required.** A minimal hello world is *one* `generate` step. The size came from the two-mode requirement, a step that runs the code, and a Cedar guard in front of it. Each addition was reasonable alone; together they are an app, not a hello world.
- **Plumbing dominated.** Two branches meeting needed duplicate wires for every shared value; a branch's else-edge was wired from the wrong node (a bug a script would not have had).
- **The tool made it worse in two places.** The editor only took the long `nodes:`/`edges:` form, so a short `steps:` file was converted in place, dropping its brevity; and the model that generates apps had no instruction to keep graphs small.

Where the graph did earn its cost, even here: `graf validate` caught the dead-end branch once it was made to look for it; the code-running step could not be added without a guard; every run produced a log and per-node timings. Those are small gains at this size and large ones at fifty nodes with a model editing them.

## The counter-example: compliance audit

The picture that shows what the graph is for is `cookbook/compliance_audit` ([capture](../../DEMO/compliance_audit_GraphLang_.pdf)): load a document, find personal data, check it against rules, branch on compliant or not, redact and find personal data again, re-check, and only then ask a Cedar guard "may it be released?", ending in one of two audited outcomes (released, escalated). The control flow *is* the content: a reader sees in seconds that nothing is released without passing the guard, that the redacted text is checked again before release, and that nothing falls through without an audit note. Model steps, deterministic steps, gates and the guard are told apart by colour. Written as a script, the same logic is shorter and has all of this buried; `graf validate` also enforces, rather than documents, that the release step cannot be reached around the guard. Compare it with the 13-node hello world above: same tool, opposite fit.

## Decisions (what was done about it)

1. **Create prefers the smallest graph.** The generation guide now says: use the fewest steps that meet the specification; one `generate` step for a single model call; do not add guards, policies, code-running or branches the specification does not ask for, and when the specification would need one, say so in the reply instead of adding it silently.
2. **The short form is the form on disk.** The editor opens a `steps:` file as it is: it edits the long form internally, shows and saves the short form (checked by `graf compact`: the saved file expands to exactly the graph that was edited). Comments in a short file are not kept when the editor saves it.
3. **Higher-level steps** so common patterns need less plumbing:
   - `in: {x: [a, b]}`: "whichever of these ran". It removes the duplicate wires where exclusive branches meet.
   - `run_code`: runs the program text a step produced (Python or JavaScript) in a throwaway folder with an empty environment, no input and a time limit, and returns what it printed; a reply that is not code is reported, not run, and nothing fails. It is risky, so a guard must precede it.
4. **This note and a "when not to use it" line** in the README and the user guide.

## How to program "Hello World" in GraphLang

The honest answer has three parts.

**1. The shortest program is one step.** A prompt file `prompts/hello.md` that says `Write a Hello, World! program in {{in_language}}`, and the graph:

```yaml
version: "1.0-graph"
workflow:
  name: hello
  inputs:  [{name: language, type: TEXT, default: Python}]
  outputs: [{name: program, type: TEXT}]
resources: {prompts: {hello: ./prompts/hello.md}}
steps:
  - hello: {generate: prompts.hello, in: {language: $in.language}, out: program}
  - done:  {output: hello.program}
```

Two steps, one model call. (`graf run hello.graph.yaml --param language=Go`.) This is the right size: a graph is a thin wrapper around the prompt.

**2. If you want no model at all, do not use GraphLang.** `print("Hello, World!")` is the program. A deterministic step exists (`solve`), but a graph around a `print` adds nothing.

**3. The bigger version is a different question.** "Hello World that picks a model or a tool, runs what it wrote, and refuses languages a policy does not allow" is a small *agentic workflow*. That is what `cookbook/hello_world` is, and it is the point at which a graph starts to pay: the mode switch is one `evaluate` step, the program is run behind a guard, and the result says why when it was not run. Its size is the size of its requirements.

A short way to say it to someone: *GraphLang is not where you write programs; it is where you describe, check and control the work that models and programs do together.* Hello World is a program. "Hello World, safely, with an audit trail" is a workflow.

## What this means for the product

- Position GraphLang against **orchestration code** (LangGraph, SPL, hand-rolled agent loops), not against a general-purpose language.
- Keep the guide, the editor and Create **conservative**: the default answer to a small task is a small graph or no graph.
- Measure complexity as *nodes per requirement*, not nodes. A recipe whose node count is far above its requirements is a bug in the recipe or in the generator.
- Do not add node types to cover what an expression or a script already does. New steps (as in decision 3) are justified only where they remove plumbing from patterns that occur in real workflows (switch, converge, run generated code, ask a person).

## Reference

- *Orchestrating Workflows with Declarative Deterministic–Probabilistic Composition.* arXiv:2607.07727. https://arxiv.org/pdf/2607.07727
