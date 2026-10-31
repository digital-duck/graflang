## Chapter 4: Tools, Agents, and Orchestration

A model on its own can only produce text. It cannot check the weather, query a database, send an email, or look up a customer's order. Tools change that. They let a model reach outside itself, and they let an application give the model a way to act on the world. Once a model can take actions, though, the design problem shifts. You are no longer only asking whether the answer is good. You are also asking what the system may do, in what order, how many times, and what happens when a step fails halfway through.

This chapter covers how tools are defined and called, how an agent loop works, how multi-step workflows can be arranged, and how to keep all of it bounded, recoverable, observable, and safe to run.

### Function calling and tool use

Function calling is the mechanism that lets a model request an action in a structured way. The application describes a set of tools to the model: each tool has a name, a plain-language description of what it does, and a schema for its arguments. When the model decides a tool is needed, it does not run anything itself. It emits a structured request, such as `{"id": "call_7f3a", "name": "get_order_status", "arguments": {"order_id": "A-1042"}}`. The application validates that request, executes the real function, and returns the result to the model as a new message. The model then uses that result to continue.

That returned message must carry the identifier of the call it answers, such as `"tool_call_id": "call_7f3a"`. This is a correctness requirement, not a style choice. When a model issues several calls in one turn, or repeats the same tool with different arguments, the call ID is the only reliable way to match each result to its request. Without it, the model may attribute a refund status to the wrong order.

This division of labour matters. The model chooses which tool to call and what arguments to pass. The code decides whether the call is allowed, performs it, and shapes what the model sees afterwards. Three points make this work well in practice:

- **Write tool descriptions as carefully as you would write an API doc.** The model selects tools from their names and descriptions. A vague description such as "handles data" invites misuse. A precise one such as "returns the shipping status for an order ID; does not modify the order" tells the model when to use it and when not to.
- **Keep arguments narrow and typed.** Prefer `order_id: string` with a documented format over `query: string`, which is also a string but accepts anything and so does everything. The contrast is one of scope, not type: a narrow argument limits what the tool can be asked to do, which makes it easier to validate and harder to misuse.
- **Return results the model can use.** A tool that returns a 4,000-line raw JSON dump wastes context and buries the fact the model needs. Return the relevant fields, a clear status, and an explicit error message when something goes wrong. An error the model can read ("order not found; check the ID format") lets it recover. A silent empty result leads it to guess.

Validate every tool call on the application side, even when the model produced a schema-conforming request. A schema check catches malformed input; it does not catch a valid-looking request that should never be made, such as deleting a record the user did not name. Authorization belongs in code, not in the prompt.

### The agent loop

An agent is a model placed inside a loop that lets it take several steps toward a goal. The loop has four phases, and most agent frameworks are variations on the same cycle:

1. **Observe.** Gather the current state: the user's request, previous tool results, and any relevant memory.
2. **Reason.** The model decides what to do next: answer now, call a tool, or ask the user for something it lacks.
3. **Act.** The application executes the chosen tool call, if there is one.
4. **Check.** The result is examined. Did the call succeed or fail? Is the goal met? Should the loop continue?

The loop ends in one of two ways. Either the model produces a final answer, or the application stops it because a limit has been reached. The second case is the one teams forget. The model does not detect on its own that it is repeating itself. A model that keeps calling a tool that keeps failing will continue indefinitely unless the application enforces a step budget. Without that budget, the loop has no exit other than the model choosing to stop, and a confused model may never make that choice. The check phase is therefore two checks at once: the model asking "am I done?", and the application asking "have I spent my step, token, or money budget?"

It helps to think of an agent as a controller over a probabilistic component. The loop itself is ordinary deterministic code: it counts steps, records results, enforces limits, and routes errors. The model supplies the judgment at the reasoning step. Keeping that split clear makes systems easier to test. You can test the loop with a fake model that returns scripted decisions, and you can test the reasoning separately with real model calls.

### Workflow patterns

Not every multi-step task needs an open-ended agent. Often a fixed workflow is more predictable, cheaper, and easier to debug. The main patterns, roughly from most constrained to least, are:

- **Sequential chains.** Step A feeds step B, which feeds step C. Each step has one job. Example: extract fields from an invoice, then validate them against a vendor list, then format a summary. Chains are the easiest pattern to reason about and should be the default.
- **Routing.** A first step classifies the input and sends it to a specialised path. Example: a support message is classified as billing, technical, or general, and each class is handled by a different prompt and tool set. Routing keeps each path simple, but it depends on the classifier being right. To guard against misclassification, include an explicit fallback route, such as "other" or "unclear", that sends the input to a general path or to a human queue. A classifier that is unsure should route to the fallback rather than guess a specialised path, so a wrong guess costs a review rather than a wrong action.
- **Parallelization.** Independent subtasks run at the same time, and their results are combined. Example: three reviewers each check a document for a different risk, and a final step merges the findings. Parallelization reduces latency only when the subtasks are truly independent of one another and the merge step is cheap. If one subtask depends on another's output, or if merging requires another model call to reconcile disagreements, the speed gain shrinks or disappears. Parallelization also multiplies cost, because every branch spends tokens.
- **Orchestrator-worker.** A coordinating model breaks a task into parts, hands each part to a worker (which may be another model call or a tool), and assembles the results. This pattern suits tasks whose structure is unknown in advance, such as researching a question that may need several sources. It is also the hardest to bound, because the orchestrator decides how much work to create. Cap the number of workers an orchestrator may spawn in one run, and count each worker's calls against the same step and cost budgets that govern the rest of the run, so that fan-out cannot exceed them.

The usual advice is to start with the simplest pattern that could work and move up only when a concrete failure justifies the extra complexity. A chain that handles 95 percent of cases well and fails predictably on the rest is often a better product than an orchestrator that handles 99 percent and fails in ways no one can explain.

### State and memory across steps

Each model call is stateless. Whatever the model "remembers" about earlier steps is whatever the application puts back into the prompt. This makes state management an explicit design task.

Distinguish three kinds of state:

- **Working state** is what the current run needs: the original request, the tool results so far, and the step count. It usually lives in the message history or in a structured record that the application updates after each step.
- **Session state** persists across turns of one conversation, such as the user's stated preferences or a partially completed form.
- **Long-term memory** persists across sessions, such as a customer's past issues. It is typically stored outside the model, retrieved when relevant, and written only through controlled paths.

Keep working state structured rather than buried in prose. A record such as `{"order_id": "A-1042", "status_checked": true, "refund_issued": false}` lets the application check progress and resume after a failure. A paragraph of summarised history does not. When a long run approaches the context limit, summarise the older steps deliberately, keeping decisions and identifiers, and drop the raw tool output that is no longer needed.

### Limits on autonomy

Every degree of autonomy you grant is a degree of risk you accept. Bounding an agent is a set of concrete, enforceable choices rather than hopes about its behaviour:

- **Step budgets.** Set a maximum number of loop iterations and tool calls per run. Stop and report when the budget is exhausted. This is the simplest and most important safeguard.
- **Cost budgets.** Cap the tokens or money a single run may spend. A run that hits its cost cap should stop cleanly, not fail mid-action.
- **Permissions.** Give each tool the least access it needs. A tool that reads order status should not hold credentials that can issue refunds. Separate read tools from write tools, and require stronger checks for writes.
- **Human-in-the-loop checkpoints.** For actions that are costly, irreversible, or externally visible, pause and ask a person to confirm. Sending an email to a customer, moving money, and deleting data are typical examples. The checkpoint should show the proposed action in plain terms, not the model's full reasoning.
- **Allowlists.** Restrict which tools, domains, or record types an agent can touch in a given context. Allowlists are easier to reason about than attempting to enumerate everything forbidden.

A useful test: if the model produced the worst plausible sequence of tool calls within the budget, what would the damage be? If the answer is unacceptable, the bound is too loose.

### Observability

Debugging a multi-step run is difficult because the same input may take a different path on the next attempt. For that reason, every step should be logged: the inputs the model saw, the decision it made, the tool call it issued with its arguments and call ID, the result the application returned, and any error or budget event. Record these in the structured run record described above, with a run identifier that ties every entry together. Logs should be written at each step, not only at the end, so that a run which crashes or hits its budget still leaves a complete trace. Treat these logs as sensitive data: they may contain customer details and should be stored and access-controlled accordingly.

### Failure handling

Multi-step systems fail more often than single calls, because every step adds a chance of failure. The goal is not to prevent every failure but to keep the process recoverable and to degrade gracefully when recovery is not possible.

Four techniques cover most cases:

- **Retries** handle transient failures such as timeouts and rate limits. Retry with exponential backoff and a cap on attempts. Retry only operations that are safe to repeat. An operation is safe to repeat if running it twice has the same effect as running it once. Check this before writing the retry logic: a read is usually safe, while a write is safe only if it carries an idempotency key that the receiving system honours, so that a duplicate request is recognised and ignored.
- **Fallbacks** provide an alternative when the primary path fails. A search tool that is down might fall back to a cached index. A model that returns malformed output might fall back to a simpler prompt or a different model.
- **Graceful degradation** means delivering a reduced but honest result when the full task cannot be completed. "I could check the order status but could not reach the refund system; here is what I found, and the refund needs a person to review it" is better than a confident answer built on missing data.
- **Checkpointing** saves progress after each successful step so that a failure at step five does not force steps one through four to run again. Checkpointing also makes it possible to resume a run after a crash, which matters most for long or expensive workflows.

The hardest case is a non-idempotent call that times out with an unknown outcome. The request may have succeeded before the connection dropped, so retrying it blindly could issue a second refund. Do not retry it directly. First query the system of record for the state the call was meant to produce, such as whether a refund with that reference exists. If the state shows the action completed, record it and continue. If the state shows it did not, retry under the same idempotency key. If the state cannot be determined, stop and escalate to a person. Treating an unknown outcome as a failure to be checked, rather than as a failure to be retried, is what keeps refund-style workflows correct.

Distinguish between errors the model can act on and errors it cannot. A malformed argument is something the model can fix on the next attempt if you return a clear message. A revoked credential is not, and retrying the model will not help. Route each kind differently: feed the first back into the loop, and stop and escalate the second.

### Putting it together

Consider a refund assistant. A customer asks for a refund on a late order. A well-designed system does not give one model free rein. It is best described as a chain with a routing step at the front. A classifier routes the request to the refund path, or to a human queue if it is unclear. A read tool fetches the order and checks the refund policy. A deterministic rule computes the eligible amount. A checkpoint asks a human to approve any refund above a set threshold. A write tool issues the refund with an idempotency key, and if the call times out, the system checks the refund record before deciding whether to retry. Every step records its result in a structured run record. The model contributes judgment where judgment is needed, such as interpreting the customer's message and explaining the outcome. The code contributes the bounds, the permissions, and the recovery paths.

That division is the central lesson of this chapter. Tools give a model reach. Agents give it initiative. Orchestration gives it structure. Each one is worth adding only when you can say what it does, what limits it, what happens when it goes wrong, and what the logs show afterwards.