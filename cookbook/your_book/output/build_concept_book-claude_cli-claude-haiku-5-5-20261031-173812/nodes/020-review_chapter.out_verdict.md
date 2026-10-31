REVISION_NEEDED
1. **Factual error about the agent loop's end condition.** The text says the loop ends "when the model produces a final answer or when a limit is reached," but the description of the Check phase omits that the check also covers errors. More importantly, the claim that a model "that keeps calling a tool that keeps failing, will loop indefinitely unless something stops it" is accurate only if no step budget exists; the chapter should say this directly so readers don't infer that the model itself detects repetition.

2. **Inconsistent terminology for the orchestrator pattern.** "Orchestrator-worker" is described as a "coordinating model," but the Putting-it-together section and the Limits section never revisit it, so readers are left without guidance on how its unbounded fan-out interacts with the step and cost budgets. Add one sentence tying the orchestrator's fan-out to a worker-count cap.

3. **Missing statement that a tool-call result must be linked to its request.** The function-calling section describes returning "the result to the model as a new message" but does not mention that the result must reference the call ID the model emitted. Without this, parallel or repeated calls become ambiguous. Add this, since it is a correctness requirement, not a style point.

4. **"Routing" paragraph is incomplete.** It says routing "depends on the classifier being right" but gives no mitigation. Add one concrete option, such as a fallback/"other" route to a human or a general path, to keep the section actionable and parallel to the Failure handling section.

5. **Parallelization claim needs qualification.** "Reduces latency" is true only when subtasks are truly independent and the merge is cheap. Add that condition, because otherwise the statement reads as universal.

6. **Retry guidance is incomplete.** "Retry only operations that are safe to repeat" is correct, but the idempotency example is the only one given, and the chapter never says how to check idempotency or what to do when a non-idempotent call times out with an unknown outcome. That ambiguous case is the most important one for refund-style workflows and should be addressed, for example by querying state before retrying.

7. **Overstated universal in the Putting-it-together example.** "The model contributes judgment where judgment is needed" is fine, but the chapter claims the refund system "runs a chain," then adds an orchestration-style classifier and checkpoint. Clarify that this is a chain with a routing step, so it matches the pattern names defined earlier.

8. **Minor clarity issues.**
   - "It is also the application asking 'have I spent my budget?'" should name the budget types explicitly (steps, tokens, money), which the Limits section defines later.
   - "Keep arguments narrow and typed" lists "Prefer `order_id: string` with a documented format over a free-form `query: string`". The contrast is clear, but the second example should be typed as a string too, or the contrast reads as a type difference rather than a scope difference.
   - The sentence "The check phase is therefore not only the model asking..." uses "therefore" where the logic is not a consequence of the preceding sentence. Replace with a plain transition.

9. **Completeness gap: no mention of observability.** A chapter on agent safety and recoverability never says that each step's inputs, outputs, and decisions should be logged. The run record is mentioned only in the example. Add a short paragraph or bullet under Failure handling or Limits, since debugging non-deterministic multi-step runs depends on it.