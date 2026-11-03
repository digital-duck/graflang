# Patterns: which one fits, and where to start

Most workflows are one of a few shapes. Find yours here, open the recipe, change it. Every recipe is a folder under `cookbook/` with a `readme.md`; run it from the repo root. The names follow the patterns in [PocketFlow](https://github.com/The-Pocket/PocketFlow)'s design-pattern docs, so what you know from there carries over.

| Pattern | Use it when | Start from | Shape |
|---|---|---|---|
| **Chain** | each step improves or transforms the last | `self_refine`, `chain_of_thought` | `GENERATE` → `GENERATE` → `GENERATE` |
| **Branch** | the next step depends on a label or a test | `guardrail` (and `support_triage` in `graf create`'s examples) | `GENERATE` → `EVALUATE` → two paths, each ending in an `OUTPUT` |
| **Evaluator-optimizer loop** | a draft should be criticised and reworked until it is good | `supervisor`, `your_book`, `code_pipeline` | `LOOP` { write, judge, rework } with a cap |
| **Self-healing** | a rule or a tool can check the model's output | `self_heal`, `ts_verify` | `GENERATE` → deterministic check → on failure, show the model its own mistake and retry, with a cap |
| **Guardrail** | refuse or reroute input before a model sees it | `guardrail` | a cheap check, then answer or decline |
| **Supervisor** | an unreliable worker needs a second opinion | `supervisor` | worker → supervisor → approve, or back with a note; says so when nothing is approved |
| **Agent (decide, act, observe)** | the model chooses its next action from a small set | `agent_notes` | `LOOP` { decide, evaluate the choice, act (a tool node), observe }; the graph limits what a choice may do |
| **Map-reduce / batch** | the same work for every item in a list | `stock_analysis` (`BATCH`), `expand_demo` (`expand:`) | split, one run per item, combine |
| **Parallel vote** | several independent attempts, then agree | `pocketflow/majority_vote`, `pocketflow/debate` | `FORK` → samples → `JOIN` → a vote by a `SOLVE` |
| **Rules around a model** | the decision must be exact; the model only reads | `compliance_audit`, `solver_check` | model extracts facts; `SOLVE` / `ASSERT` decide; a Cedar `GUARD` releases |
| **Memory** | later runs should remember earlier ones | `chat_memory` | `QUERY` the last lines of a file, answer, `EMIT` (append) the exchange |
| **Read, write, notify** | the workflow touches the world outside it | `notes_digest` | `QUERY` in, `OBSERVE` on the way, `EMIT` out (file, terminal, webhook, e-mail), all behind a `GUARD` |
| **Always on** | check something on a schedule and act when there is work | `graf watch GRAPH --every 300` | a graph that checks and acts, run again and again; each run bounded |

Not built yet: **human in the loop** (a node that waits for a person: `docs/DEV/DESIGN/graflang-hitl.md` is the design), **retrieval (RAG)** over many documents, and **streaming of tokens** (`graf run --stream` shows each node's result as it finishes, not each word).

## Choosing

- If a **person could write the steps down in order**, it is a chain or a branch. If the model must pick the steps, it is an agent, and the graph's job is to say what a pick may do.
- If **something other than a model can check the result** (a compiler, a rule, a schema, a test), put that check in the loop: it is cheaper and more reliable than asking a model to review itself.
- If **a mistake is costly** (a file written, a message sent, a change applied), the step is risky: put it behind a `GUARD`, and let `graf validate` prove nothing goes round it.
- Whatever the shape, **bound it**: a loop cap in the graph (`max_rounds`, `max_steps`), and `limits.max_llm_calls` in a bind file for the run.

## The process: humans design, the model fills in

PocketFlow's "agentic coding" guide gives the order in which a person and a model share the work on an LLM system. It is how `graf create`, `graf describe` and the Create page are meant to be used. Use it as a checklist.

| Step | You | The model | In GraphLang |
|---|---|---|---|
| 1. Requirements | decide what the system is for; is a model even the right tool? | little | the `--spec` text, or your first message on the Create page |
| 2. Flow | sketch the steps and the pattern (the table above) | fills in the details | `graf create` drafts it; `graf vis` shows it; `graf describe` reads it back in words |
| 3. Utilities | name the files, APIs and tools the steps need | writes the glue | `QUERY`, `EMIT`, `RUN`, `SOLVE` nodes |
| 4. Data | check what flows between steps | proposes the types | typed ports; `graf validate` checks the wiring |
| 5. Nodes | review each prompt | writes the prompts | `prompts/*.md` beside the graph |
| 6. Build | little | writes the graph | `graf create`, or the editor's chat |
| 7. Optimise | judge the results; say what to change | tries the change | the Logs tab (compare runs), `graf trace`, a re-run with another `--llm` |
| 8. Reliability | decide what must never happen | writes tests and edge cases | `limits`, `GUARD`, a deterministic check in the loop, and tests with a scripted model |

Two rules from that guide hold for GraphLang as well. **Start small:** one model call and one check, run it by hand on a few real inputs, then grow it. **If you cannot say the flow, a model cannot automate it:** solve two or three examples yourself first; what you did is the graph.
