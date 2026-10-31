REVISION_NEEDED
1. **Factual error about LLM judges (the "Judge scores drift" bullet and the calibration paragraph are fine, but check the bias claim):** "answers that appear first when comparing two candidates" is a position bias, which is accurate. However, the sentence "Judges can be wrong confidently. A fluent judge can approve a fluent but unfaithful answer" is repetitive with the faithfulness metric and should either be cut or tied to a concrete mechanism (e.g. judges check plausibility, not grounding, unless given the source).

2. **The "Metrics" section lists faithfulness as a metric that "matters most in retrieval-based systems," but gives no way to measure it.** Add one concrete method (for example, checking each claim against the retrieved passages, by a human or an entailment/judge model with calibration), since the chapter otherwise promises measurement.

3. **"Five are worth tracking in most applications" with an explicit "Task success" bullet that repeats accuracy.** Clarify how task success differs from accuracy (e.g. a correct answer can still fail the task if it arrives too late or in the wrong format), or merge the two.

4. **Prompt injection defences: "Restrict what the system can do... Limit tool permissions"** is good, but the chapter should state the core principle explicitly: the model must not be the security boundary. The later sentence "Design so that a successful injection has limited effect" gestures at this; make it the lead.

5. **Data leakage section mixes two claims with unclear scope.** "Training or logging pipelines that retain private text" is a different risk from in-session leakage. Either separate them or name the mechanism for each.

6. **"Harmful output" is vague on what to do.** "Apply output checks appropriate to the domain" needs at least one concrete example of a check and one of an unfixable rule (e.g. a hard-coded validation that blocks a payment above a limit regardless of model output), since the next sentence refers to "rules the model cannot override" without defining them.

7. **Reliability paragraph** correctly lists retries and fallbacks but omits the important caveat that retries on non-idempotent actions (payments, emails) can duplicate effects. This ties to the confirmation advice and should be mentioned.

8. **Monitoring: "Log enough to reconstruct any decision"** conflicts with the earlier privacy note only lightly. Add a sentence that logs should be redacted or minimised where possible, not merely retained under the same rules.

9. **Deployment section: "Pin versions where the provider allows it"** should note that some providers deprecate pinned versions on a schedule, so pinning does not remove the need to rerun evaluations. Otherwise the advice is incomplete.

10. **Model selection paragraph** says "Run the same suite against two or three candidate models." Add that the comparison should use the same held-out split and the same prompt, or the comparison is confounded (this is the same point as the versioning bullet, so a cross-reference suffices).

11. **Opening paragraph and "Putting it together"** are clear, but the chapter never states its scope in relation to earlier chapters. If the book has prior chapters on prompting or retrieval, add a one-line pointer so readers know where the prerequisites are. (If this is the first chapter the claim is moot; confirm.)