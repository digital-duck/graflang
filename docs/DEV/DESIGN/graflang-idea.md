# Idea: outcome-driven workflows (the MonteFlow vision)

Status: **placeholder, not built here.** A candidate roadmap item, recorded 2026-11-02 from the owner's earlier plan (`/home/gongai/projects/digital-duck/monteflow`, a package skeleton: "stochastic workflow simulation engine with transition matrices", built on MarkoFlow). The owner has a prototype on another machine; it is not in this repo and is not reviewed here. The plan is to pick this up **once GraphLang is stable**, with that prototype as the starting point. Nothing below is implemented in GraphLang, and no result is claimed.

**The aim in one line:** a workflow whose **set of states is fixed** (the nodes of the graph) while **how it moves between them is probabilistic**: a Markov chain over a known, finite state space. The behaviour is bound because the states are enumerable and nothing outside them can happen; it is unpredictable because which transition is taken on a given run is drawn from a distribution (set by the model's answers), not fixed by the file.

## The idea

A workflow step that calls a model does not have one outcome. An `EVALUATE` or `ASSERT` sends the token to `pass` or `fail`; a `LOOP` exits early or runs to its cap; a `GUARD` allows or denies. Each of these is a choice among a few next nodes, and over many runs it has a frequency. Treat the graph as a **Markov chain** over its nodes: the edges out of a node carry probabilities, estimated from past runs. Then a workflow can be *driven by outcome probability*:

- **Predict before running:** the chance a run reaches each `OUTPUT` (`released`, `escalated`), the expected number of model calls, tokens and cost, and the spread, from the transition matrix, without spending a call.
- **Simulate:** sample paths through the graph with the estimated probabilities (a Monte Carlo run with no model), to size a budget (`max_llm_calls`) or find a retry cap that is rarely hit.
- **Revise the graph from the numbers:** because the workflow is data, a `MUTATE` delta can act on what the chain shows (a retry edge that almost never helps is removed or capped; a branch that fails 60% of the time gets a cheaper first step). This is the part only a graph can do: code cannot be revised from its own statistics in a checkable way.

Bound here means the **state space is closed**: every state is a node you can list, every transition is an edge you can list, and a run cannot enter anything else. Unpredictable means the **transition out of a state is a distribution** (for example `fail` 0.3, `pass` 0.7), so two runs of the same graph on the same input may differ. Together they give a finite chain that can be analysed exactly (reachability, absorbing states such as `released` and `escalated`, expected visits) while the workflow stays free to adapt to what the model says. This is a different bound from the budget limits (`max_steps`, `max_llm_calls`, cost), which cap one run in time and money; those still apply on top.

An analogy from the owner: people all work, play, study, rest and dream (the same small set of states), yet every person is unique, because each moves between those states with different habits (different transition probabilities). In the same way, many agents or runs can share one graph and differ only in their transition weights. The weights are then what characterises a run, a model or a user, and they can be estimated from logs and compared (is `claude-haiku-5-5` more likely than `claude-sonnet-5-5` to take the retry edge on this graph?). This is an analogy for intuition, not a claim about people or models.

Hypotheses from the same analogy (to test, not to assume): a weaker model may settle into a steady state, meaning a retry loop it rarely leaves or an absorbing state such as `escalated`, which shows in the chain as a high self-transition or absorption probability; a stronger model may reach paths the weaker one almost never takes. Two cautions. With the state set fixed, "novel behaviour" can only mean a different distribution over existing paths (rare paths becoming likelier); a genuinely new state needs a `MUTATE` that adds one, which the tension below governs. And a stronger model may look *less* varied, not more, because it passes the gate on the first try and the chain collapses onto the short path. The evolution picture (variation, then selection) maps onto sampling or mutation deltas as the variation and `EVALUATE`/`GUARD` as the selection; whether anything like adaptation over many runs happens is exactly what the estimates would show.

One tension to settle: a `MUTATE` changes the graph, so it changes the state space. Either the chain is re-estimated after each accepted revision, or a mutation is only allowed to keep the state set (rewire or reweight, not add nodes), which would make the fixed-state guarantee hold across revisions too. The second is stricter and may be the safer default.

## Why GraphLang is a good host

| Needed | Already in GraphLang |
|---|---|
| a discrete state space | nodes and ports; token-passing dataflow |
| the observed choices | the `route` of every `node.done` event in the run log (`route=fail`), and per-node firing counts in `summary.json` |
| many recorded runs | `output/<graph>-<model>-<time>/` folders (`run.json`, `summary.json`, `result.json`, `nodes/`), now also written by the editor's Run tab and read back by its Logs tab |
| cheap repeats | record and replay of model answers (`--record`, `--replay`), the `mock` adapter |
| a safe way to change the graph | `MUTATE` deltas, validated (schema, Cedar, budget, invariants on a trial copy) |
| bounds | `--max-steps`, `limits.max_llm_calls`, cost and wall-time limits |

## Sketch

1. **Estimate.** Read the JSONL logs (or run folders) of a graph; count, per node, how often each route was taken; add a prior so unseen routes keep a small probability. Output a transition table: `node.port -> next node: p`, with the count behind each number.
2. **Analyse.** From the table: absorption probabilities at each `OUTPUT`, expected visits per node, expected calls and cost (visits times the measured per-node tokens), and a cap check ("a loop of 3 is exceeded in about p of runs").
3. **Simulate.** Sample N paths; report the distribution of calls, cost and result. No model is called.
4. **Propose.** Suggest (never apply on its own) `MUTATE` deltas from the table, shown as a diff the owner accepts, as the app's chat already does for edits.

A command might read `graf chain GRAPH [--logs DIR]` (the table, the absorption probabilities, an expected cost) and `graf chain GRAPH --simulate N`. Whether it lives in this repo or in `monteflow` (GraphLang reading the table through an optional import, as `procedure_ref` reads SPL.py) is open; the second keeps GraphLang free of the statistics.

## Honest limits

- **The Markov assumption is a model, not a fact.** A node's outcome often depends on more than the node: the content of the draft, the loop counter, the input. The probability of `fail` on the third retry is not the probability on the first. Likely remedy: a state that is the node plus the loop cycle (or a small bucket of the inputs), checked against the data; where it does not fit, the numbers must say so.
- **Estimates need runs, and real runs cost money.** A handful of runs gives wide uncertainty. Report counts and intervals, not bare probabilities; use replay and the mock for the cheap part and keep real-model runs capped, as always.
- **Inputs shift the probabilities.** A table from one kind of document does not carry to another. Keep it per graph and per model (the output folder name already carries both).
- **Revising from the numbers can chase noise.** Any proposed change should be tested by a fresh batch of runs before it is believed; the claim "this change helps" is an experiment, and none exists yet.
- **No claim about accuracy or savings** until such an experiment is run (see the paper draft's list of missing work).

## Roadmap placement

When picked up (after GraphLang is stable, starting from the prototype on the other machine), a small, checkable first step: **estimate and report** (items 1 and 2 above) from logs that already exist, on `code_pipeline` and `compliance_audit`, where the routes are known and the answers can be compared with the raw counts. Simulation (3) follows if the estimates are stable. Proposing graph changes (4) is last, and only after the first three show the table predicts a held-out batch of runs. It connects to the Logs tab (a "chain" view of a graph's past runs) and to the speculative-outlook slide's "safer self-editing agents".

Open questions: whether a revision may add states or only change transitions (above); the state definition (node, node plus cycle, node plus a feature of the input); whether `GENERATE` outcomes that are not routes (the quality of a text) can enter at all, or only the routes of `EVALUATE`, `ASSERT`, `GUARD` and `LOOP`; where the code lives (this repo or `monteflow`); and the MonteFlow naming and its "path" vocabulary, which should be written in plain words (probability of a path) here.
