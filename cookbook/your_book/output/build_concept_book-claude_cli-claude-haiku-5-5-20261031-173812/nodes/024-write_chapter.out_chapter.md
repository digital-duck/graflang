## Chapter 5: Evaluation, Safety, and Deployment

An AI feature that impressed in a demo can still fail quietly in production. The model answers, the output looks plausible, and nobody notices that a fraction of the answers are wrong, that a clever user has tricked the system into leaking data, or that the monthly bill has tripled. This chapter is about closing that gap. It covers how to measure whether a system works, how to keep it safe, and how to run it over time.

### Measuring what matters: evaluation sets

You cannot improve what you cannot measure, and with language models, intuition is a poor measuring instrument. Two systems can produce fluent answers that differ sharply in correctness, and reading a few outputs will not reveal which is better.

The remedy is an **evaluation set**: a collection of representative inputs, each paired with what a good answer looks like. Build it from real traffic where you can, or from realistic examples written by the people who understand the task. Aim for coverage rather than size. A hundred cases that include the messy, ambiguous, and adversarial inputs teach you more than a thousand copies of the easy cases.

Some practical guidance:

- **Include the hard cases on purpose.** Add inputs that are ambiguous, malformed, out of scope, or near the boundary of what the system should refuse.
- **Record the expected result in a checkable form.** An exact label, a required fact, or a rubric is far more useful than "a good answer."
- **Version the set.** When the set changes, scores from before and after are no longer comparable. Keep a changelog.
- **Keep a held-out portion.** If you tune prompts against the whole set, your scores become optimistic. Reserve some cases you never look at while iterating.

### Automated and human evaluation

Automated checks are cheap and repeatable. Where the output has a verifiable structure, such as valid JSON, a correct label from a fixed set, or a value that matches a known record, code can score it directly. Use these wherever possible, because they run on every change without anyone's time.

Free-form text is harder. Here, teams often turn to **LLM-as-judge**: a second model reads the input and the output, then scores them against a rubric. This scales well and is often good enough for coarse comparisons. It also has real limitations:

- **Judges have biases.** They may prefer longer answers, answers in their own style, or answers that appear first when comparing two candidates.
- **Judges can be wrong confidently.** A fluent judge can approve a fluent but unfaithful answer.
- **Judge scores drift with the judge.** Changing the judge model or its prompt changes the numbers, so treat judge configuration as part of the evaluation's definition.

The safeguard is calibration. Have a human label a sample of cases, then measure how often the judge agrees with them. If agreement is low on a category, do not trust the judge for that category. Human review remains the reference point for subtle quality questions, and periodic spot checks catch what automated scores miss.

### Metrics that reflect task success

Choose metrics from the task's actual requirements, not from whatever the tooling reports by default. Five are worth tracking in most applications:

- **Accuracy.** The share of outputs that are correct against the reference. For classification and extraction, this is often the headline number, reported with per-category breakdowns, because an average can hide a category that fails badly.
- **Faithfulness.** Whether the claims in an output are supported by the source material provided. This matters most in retrieval-based systems. An answer can be accurate in the abstract and still unfaithful to the documents it was given.
- **Latency.** The time from request to usable result. Measure the tail (for example, the 95th percentile), since a fast median can hide users who wait a long time.
- **Cost per task.** Tokens consumed multiplied by the price of each model call, summed across all the steps a task takes. Agents and multi-step workflows multiply this quickly, so count every call, including retries and judge calls.
- **Task success.** The end-to-end outcome a user cares about: the ticket was resolved, the form was filled correctly, the question was answered. This is the metric that connects technical scores to value.

Report these together. A system that gains two points of accuracy while doubling latency and cost may be a bad trade, and only the combined view shows that.

### Safety and reliability

Language models accept instructions and data in the same channel, and that single fact causes most of the security problems in applied AI.

**Prompt injection** occurs when text in the input, such as a web page, an email, or a retrieved document, contains instructions that the model follows instead of the developer's intent. A support bot that summarizes customer emails may obey an instruction hidden in one of them. Defences work in layers:

- Treat all retrieved and user-supplied text as data, and say so explicitly in the prompt.
- Restrict what the system can do. An agent that cannot send email cannot be tricked into sending email. Limit tool permissions to the minimum the task needs.
- Require confirmation before consequential actions such as payments, deletions, or external messages.
- Test with adversarial inputs as part of the evaluation set. Injection attempts belong in the set, not only in a separate security review.

No single filter reliably stops injection, so do not rely on one. Design so that a successful injection has limited effect.

**Data leakage** happens when the system reveals information it should not. Sources include sensitive material placed in the context, data from one user's session appearing in another's, and training or logging pipelines that retain private text. Keep the context limited to what the current request needs, enforce access control on retrieved documents before they reach the model rather than trusting the model to withhold them, and decide deliberately what gets logged.

**Harmful output** covers content that is offensive, dangerous, or simply wrong in ways that cause harm. Apply output checks appropriate to the domain: a medical application needs different guardrails from a marketing copy generator. Where an output drives a decision, validate it against rules the model cannot override.

Reliability is the everyday counterpart to these concerns. Models occasionally time out, return malformed output, or refuse valid requests. Handle these explicitly with retries, fallbacks to simpler behaviour, and clear messages to the user, rather than letting an error propagate into a silent failure.

### Monitoring, logging, and feedback in production

An evaluation set measures the system before release. Production shows what happens after, where the inputs are less tidy and the stakes are real. Monitoring closes that loop.

Log enough to reconstruct any decision: the input, the prompt version, the model and its settings, the retrieved context, the output, and the cost and latency of each step. Logs of this kind contain user data, so apply the same retention and access rules as any other sensitive store.

Watch the signals that drift first. Track output-format error rates, refusal rates, the distribution of input types, the share of answers users reject or correct, and cost per task. A sudden change in any of these usually means something changed upstream, such as a model update, a new kind of input, or a broken retrieval index.

Feedback closes the cycle. Give users a simple way to signal that an answer was wrong, and route those cases into the evaluation set. Sample a steady stream of ordinary traffic for human review. Over time, the evaluation set should grow from the failures the system actually meets.

### Cost, latency, and model selection

The most capable model is rarely the right default. Smaller and cheaper models often handle classification, extraction, and routing well, and reserve the largest model for the steps that need it. Model selection is therefore a tradeoff among quality, latency, and cost, and the evaluation set is what makes the tradeoff visible. Run the same suite against two or three candidate models and compare their scores against their prices and response times.

Caching, batching, and shorter prompts reduce cost without changing behaviour. Measure before and after, because a shorter prompt that loses an instruction can quietly reduce accuracy.

### Deployment and versioning

Treat each model, prompt, and configuration as a versioned artifact. A change to any one of them can change behaviour, so record which versions produced which outputs. Roll changes out gradually, comparing a candidate against the current version on live or replayed traffic before switching everyone over, and keep the ability to revert quickly.

Model providers update their models, sometimes without changing the name you call. Pin versions where the provider allows it, rerun the evaluation set on a schedule, and treat a score change without a change on your side as an incident to investigate.

### Putting it together

A deployed AI system is never finished. It is a loop: measure against a representative set, release a change behind a controlled rollout, watch production signals, feed failures back into the set, and repeat. The teams that do this well are not the ones with the most sophisticated models. They are the ones who can tell, with evidence, whether the system is working today, and who notice quickly when it stops.