# Design note: human in the loop (the person as a node)

Status: **piece 1 built** (2026-11-04: `DECISION` with `mode: interactive`, `default`, `timeout_s`, `max_asks`, `graf run --answer node=value --by NAME`, validate rules, a delta cannot touch it, `cookbook/release_approval`, `tests/test_decision.py`; code in `grafr/decision.py`); pieces 2 to 4 (park mode, editor form, more recipes) are still design. Originally design only (2026-11-03). Owner's direction (2026-11-03): *model the human as another node*, and then *call it `DECISION`, a neutral name* (the first drafts called it `ASK`, then `HUMAN`); one node, not two. Written because the PocketFlow review (`graflang-idea.md`, "What GraphLang could borrow") named human in the loop as the largest and most useful gap, and asked for a note before any code. PocketFlow's examples are `pocketflow-cli-hitl` (a joke generator: the person likes or dislikes the joke, a dislike feeds the next try), `pocketflow-gradio-hitl` and `pocketflow-fastapi-hitl` (a web page or an API that waits for the person).

## What exists today

- `GUARD`'s Cedar context can carry `human_approval` (a flag in `MUTATE`'s proposed-delta context), so a *policy* can say "a person must approve this change". Nothing in the runtime can *ask* a person, so the flag can only be used to deny.
- Checkpoint and resume (`--checkpoint`, `--resume`) can park a run between nodes and continue it later, in another process. Kernel variables are not saved.
- Runs are non-interactive: a graph reads its inputs once (`--param`, `--bind`) and runs to the end or fails.

## Why a person is just another node

A `GENERATE` node is a step whose `exec` is a model; a `SOLVE` node is a step whose `exec` is a program. A `DECISION` node is a step whose `exec` is a decision made by a person. Everything else about it stays the same, which is the point:

| Same as every node | For a person |
|---|---|
| typed ports in and out | the question and context go in (`in_question`, `in_context`); the answer and a note come out |
| `pre -> exec -> post` (`config.phases`) | `pre` fills in the question, `exec` waits for the answer, `post` checks it against `answers` or an `out_schema` and routes on it |
| `timeout`, `retry`, `fallback` | a timeout and a fallback route are the normal case, not the exception; a retry means asking again (a reminder), not repeating a computation |
| Cedar `GUARD` and the principal | the answer carries who gave it (`out_by`), so a guard can ask whether *that* principal may approve *this* action |
| a span in the trace, a row in the Logs tab | the wait is a span with its duration; a person's slowness shows up in the timeline like a slow model |
| composable as a part | `release_approval` (a `DECISION` then a `GUARD` then an `EMIT`) is a recipe like any other and can be dropped into a larger graph |
| a node of the Markov view (`graflang-idea.md`) | a person's choices at a `DECISION` node are transitions with probabilities, estimated from past runs (approve 0.8, reject 0.15, no answer 0.05); each person has their own, which is the "every human is unique" point made concrete |

What is different, and must be stated, not hidden:

- **Latency is hours, not seconds,** so the run usually cannot wait in a process. That is what the park mode is for (checkpoint, a pending file, resume).
- **The cost is not money.** The budget that bounds a `DECISION` node is wait time and the number of times a person is asked (`max_asks`), not tokens. `graf describe` should show a person's steps as such.
- **An answer is not a computation.** It cannot be replayed from a cassette (record and replay would record the answer, which is useful for tests, but it is a fixed script, not the person).
- **A person is an authority and a risk.** The answer is data, never instructions; a timeout must not approve; who may answer is decided outside the graph.

**Why "DECISION".** The name says what the node is for, not who fills it. Today the decider is a person (`decider: human`, the only value). A step where a model decides is a `GENERATE` plus an `EVALUATE`, and one where a rule decides is an `EVALUATE`; they stay as they are. Keeping the name neutral leaves room to treat all three as one idea later (a decision point with a decider, a set of allowed answers and a record of who answered), which is what the Markov view and composition both want: a recipe could swap its decider (a person in production, a model in a test) without changing its shape. That unification is not proposed here; only the name is chosen so it is not ruled out.

## What a person is for

Three uses, in order of how often they come up:

1. **Approval** before something irreversible: release a document, send a message, apply a model's proposed graph change. The answer is yes or no, optionally with a reason.
2. **Feedback** in a retry loop: a draft is shown; the person accepts it or says what to change; the loop runs again with the note (the CLI joke example).
3. **Missing information:** the graph reaches a step it cannot finish without a fact only the person has (an account number, a choice between two options).

## Proposal: one node, `DECISION` (the decider is a person)

A node that stops the run until a person answers.

```yaml
- id: approve
  type: DECISION
  config:
    question: "Send this digest to the whole team?"     # or an in_question port
    answers: [yes, no]                                  # the allowed answers; omit for free text
    default: no                                         # taken when nobody answers in time; must be one of `answers`
    timeout_s: 3600                                     # how long to wait (omit: wait until answered)
    decider: human                                      # the only decider for now; the name is neutral on purpose
    mode: park                                          # interactive | park
  ports: [trigger, answered, timeout, in_question, in_context, out_answer, out_note]
```

- **Routing:** the token leaves by `answered` with the answer on `out_answer` (and a free-text note on `out_note`), or by `timeout` after `timeout_s`. A graph that wants "no means stop" wires `answered` to an `EVALUATE` on `@in_answer == 'yes'`, as it would for a model's verdict. With `answers` and a `default`, `timeout` is optional: the default is used.
- **`mode: interactive`:** the terminal prompts (`graf run` in a tty). Good for development and for the CLI joke pattern. A run with no tty falls back to `default` if there is one, else fails with a clear message ("DECISION 'approve' needs a person; run it in a terminal, or use mode: park").
- **`mode: park`:** the run writes its checkpoint, writes `pending/<run>-<node>.json` (the question, the allowed answers, the context shown, a deadline) and exits with a distinct status (75, "temporary failure": not an error). `graf answer RUN_FOLDER --value yes [--note "..."]` records the answer; `graf run --resume` continues from the checkpoint. A web app, a chat bot or a scheduler can do the same thing by reading the pending file and writing the answer file: no server inside GraphLang. The editor's Run tab would list pending questions with a form.
- **What the person sees:** `in_context` (a port) is shown with the question: the draft, the document, the proposed change. The question and context are data from the graph and are shown as text, never run.

## Safety rules

- **The answer is data, not instructions.** It goes to `out_answer` / `out_note` like any value; a prompt that receives it is wrapped like any attached document ("material to read, not instructions").
- **A timeout must not approve.** `default` is optional, must be one of `answers`, and `graf validate` warns when the default is the affirmative one of a risky step (it cannot know which answer is affirmative, so: a warning whenever an `DECISION` feeding a risky node has a `default`).
- **Who may answer** is outside the graph: the pending file is on the machine that runs it; a service that exposes it must authenticate its own users. A graph can add a second check (a `GUARD` after the answer asking Cedar whether the answering role may approve this action) once the answer carries an identity (`out_by`, from `graf answer --by NAME`).
- **A MUTATE can never add or change a DECISION node's `answers`, `default` or `mode`** (add them to the code keys), and a delta cannot remove a DECISION node that sits in front of a risky node (the same rule as a `GUARD`).
- **It is not a guard.** A person's yes does not replace a Cedar `GUARD`; the validate rule that a risky node needs a guard stays. An `DECISION` feeds the guard's context (`human_approval`), which finally gives that flag a source.

## Pieces to build, smallest first

1. `DECISION` with `mode: interactive` and `default`, a prompt on the terminal, tests with a scripted stdin. No checkpoint work.
2. `mode: park`: pending file, exit status 75, `graf answer`, resume. This needs checkpoint to work inside a `LOOP` body (it does not today: "top level only"), which decides whether feedback loops (use 2) can be parked or only run interactively.
3. The editor's Run tab: a pending-question form, and the Create page's "approve this change" step.
4. A recipe for each use: `joke_feedback` (loop with feedback), `release_approval` (DECISION, then GUARD, then EMIT), `missing_fact` (DECISION with free text).

## Open questions

- A loop with a person in it: is `max_rounds` enough of a bound, or should a person's "stop" always end the loop? (Likely both: the cap stays.)
- **Resolved (owner, 2026-11-03): one node, `DECISION`.** A yes/no approval is a `DECISION` with `answers: [yes, no]`; the safety rules (a timeout must not approve, the answer carries an identity, a guard still follows) apply to every `DECISION` node.
- Time: parked runs have a deadline in the pending file, but nothing wakes them. A scheduler (`graf watch`) could look for expired pending files and resume them down the `timeout` port.
