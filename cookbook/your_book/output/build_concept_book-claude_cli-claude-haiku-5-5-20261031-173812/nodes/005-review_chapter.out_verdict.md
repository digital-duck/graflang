REVISION_NEEDED
1. **Factual error in the "Inputs, outputs" section, not just wording:** "Sampling settings such as temperature influence how much this happens" is fine, but the claim that outputs are "not guaranteed to be identical across calls" is stated without qualification. Provider-side nondeterminism is real, but the chapter should say explicitly that temperature 0 reduces variability without guaranteeing identical outputs. As written, the reader can't tell what "low settings" means.

2. **Inconsistent use of "non-deterministic" vs. "probabilistic":** The section header "Inputs, outputs, and probabilistic responses" and the later section "Deterministic and non-deterministic parts" use different vocabulary for the same property. Pick one and define it once. The chapter also says "the model does not look up an answer" but then discusses retrieval in the patterns section without bridging the two ideas.

3. **Unsupported "most production incidents begin" claim:** "That boundary is where most production incidents begin" is a strong empirical statement with no source. Soften it to something like "that boundary is a common source of production incidents," or cite evidence.

4. **Pattern list ordering claim is asserted, not argued:** "these patterns increase in autonomy and in difficulty to evaluate, roughly in the order listed" is plausible, but Retrieval-augmented QA is listed before Agents while Generation is listed before RAG, and generation's evaluation difficulty is arguably comparable to RAG's. Either justify the ordering or say it is a rough heuristic.

5. **Missing scope note on the "Choosing" section:** The chapter lists conditions favoring AI ("a reasonably good answer is valuable") but never addresses cost, latency, or privacy, which are often decisive in practice. For completeness, add one short paragraph or bullet list on these constraints.

6. **Output handling is underdeveloped relative to its emphasis:** The chapter calls it "often the most underestimated component" but gives it one bullet. A brief concrete example (e.g., schema validation failing, a retry, a fallback) would make the claim land and set up later chapters.

7. **Memory definition is slightly off:** "the model does not remember anything between calls on its own" is correct, but "Memory is something your application stores and selectively reintroduces" should note that memory reintroduced into context also consumes context budget and can mislead the model if stale. This is a completeness gap, not an error.

8. **Minor clarity:** "Plausible and true usually overlap, but not always" is awkward. Consider "Plausible text is usually true, but the model does not signal when it is not."

9. **Missing failure-mode framing for the demo gap:** The opening lists failure modes (multilingual input, empty input, prompt injection) but prompt injection is never revisited in the component or design sections. Since it is a major production risk and the email example names it, a sentence in the design-consequences list would close the loop.