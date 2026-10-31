## Chapter 1: Foundations of Applied AI Systems: Models as Components, Not Oracles

If you have ever used a spreadsheet formula that sometimes returns the wrong answer and sometimes returns a different answer for the same inputs, you have already met the core problem of applied AI. The difference is that a model's randomness is built into what it is, and the things around it (retrieval, parsing, validation, the user interface) have to be engineered to cope with that randomness. This chapter sets up the vocabulary and the habits of mind that the rest of the book depends on. Get these right and the later chapters on agents, verification and prompt optimisation read as obvious consequences. Get them wrong and you will spend months debugging a "bad model" that was really a bad interface.

### 1. Applied AI is systems engineering

A language model on its own is a function from text to text, with a twist: it is stochastic. Given the same prompt, it can produce different outputs. An application built around a model is a pipeline. Some stages are deterministic (reading a file, parsing JSON, looking up a row in a database). Some are stochastic (the model call itself). The engineering work is in the joints between them: what each stage promises to produce, what it accepts as input, and what happens when a promise is broken.

**Worked example.** Consider a system that reads a customer email and decides whether to issue a refund. A naive design sends the email to a model and asks, "Should we refund this?" The output is free text. A downstream script then searches the text for the word "yes". This design has three weak joints: the model may say "Yes, but I would not refund…", the model may refuse to answer, and the script may match "yes" inside "yesterday". None of these failures is the model being stupid. They are failures of the interface between a stochastic component and a deterministic one.

A better design specifies the contract: the model receives the email and must return a JSON object with a field `decision` restricted to `{refund, no_refund, escalate}` and a field `reason` of at most 200 characters. The parser rejects anything else, and a rejection triggers a defined fallback (retry once, then escalate to a human). Now the model can still be wrong about refunds, but it cannot be wrong about the shape of its answer without the system noticing.

How is that shape guarantee obtained? There are two common mechanisms, and they are not equivalent:

- **Parse-and-retry.** You ask for JSON, check the result, and if the check fails, call the model again, up to a fixed budget. The model's sampling distribution is untouched. The cost is latency and money for each retry, and the guarantee is conditional: once the budget is spent you have "valid JSON or an explicit failure", and the failure path must be handled.
- **Grammar-constrained decoding.** At each step, the decoder masks out any token that would take the output outside a grammar, such as one derived from a JSON schema. Every completed output then parses, with no retries. But the guarantee covers syntax only. The masking also changes the distribution: probability mass is removed from disallowed tokens and the rest is renormalised, so the output can differ from what the model would have produced unconstrained, and a grammar that forces an unlikely token early can push the rest of the output into odd territory. It is also unavailable on some hosted APIs.

The rest of this chapter assumes that every stage with a format contract says which of these it uses, because the two offer different guarantees and different failure modes.

### 2. A model as a conditional distribution

The cleanest formal picture of a model is a conditional probability distribution. Write the model as p(y | x, θ), where x is the input (the prompt and any context), θ are the fixed parameters of the model, and y is the output. Calling the model means drawing a sample y ~ p(y | x, θ). Temperature, top-p and similar settings reshape this distribution; they do not change its basic nature.

One caveat matters in practice. Setting temperature to 0 does not always make a call deterministic. On many hosted services, batching, floating-point behaviour across hardware, and server-side changes can produce different text for the same prompt. Treat "same prompt, same output" as a property to measure, not one to assume.

This framing changes what "correctness" means. A deterministic function f has a correct output f(x), and you can check whether a given run matches it. A component whose outputs are samples has no single correct output for many inputs. What you can ask instead is:

- **Per-sample validity:** the probability that a sampled y satisfies the specification S, written P(S(y) | x).
- **Task-level reliability:** the probability that the system as a whole achieves its goal. Formally, if D is the distribution of inputs the system actually receives, reliability is the expectation

  R = E_{x ~ D}[ P(system output is correct | x) ].

  This is an average over inputs, weighted by how often they occur. It is not a property of the model alone. Change the mix of inputs and R changes, even if the model is identical.

For the refund example, P(valid JSON | x) might be 0.97 and P(correct decision | x) might be 0.85 on average. Those are different numbers with different consequences, and a single "accuracy" figure hides both. The 0.85 is also only meaningful for a particular mix of emails. The same system might score 0.95 on routine "where is my order" messages and 0.60 on angry, multi-part complaints. If your test set is mostly routine messages and your production traffic is mostly complaints, the reported number is an honest figure for the wrong question.

### 3. Decomposing an application into stages

Most real applications are chains or graphs of stages. The common kinds are:

- **Retrieval:** select candidate documents or data for a query.
- **Generation:** produce text, code or a structured answer.
- **Tool use:** call an external function (search, calculator, database).
- **Validation:** check the output against rules or a schema.
- **Aggregation:** combine several outputs into one.

For each stage, write a contract with three parts: the **input type** (what it must receive), the **output type** (what it guarantees to return), and the **error modes** (the ways it can fail, and what the next stage will see when it does). For any stage whose output type includes a format, also write down the mechanism that enforces the format, as discussed in section 1.

The reason this matters is that a downstream stage can only detect violations that it checks for. A validator that checks JSON syntax will catch a missing brace but not a hallucinated customer ID that happens to be well-formed. A generator that is told to "cite sources" will produce citations that look plausible but point to documents the retriever never returned. These are contract violations the downstream stage cannot see, because its check does not cover that property.

**Worked example.** A three-stage pipeline: retrieve five passages, generate an answer, validate that the answer's format is right. Suppose the retriever returns passages that are semantically related but do not contain the answer (a recall failure). The generator, asked to answer from the passages, will often produce a fluent answer from its own memory and attribute it to the passages. The validator, which checks format, passes it. The end user sees a confident, well-formatted, wrong answer. The contract "output is grounded in the retrieved passages" was never specified, so no stage was responsible for enforcing it. Writing that contract, and giving some stage the job of checking it, is the design task.

### 4. Calibration and uncertainty

Suppose a model answers a batch of questions and attaches a confidence to each. Calibration asks a simple question: when the model says 90%, is it right about 90% of the time? For a concrete case, imagine that across 200 answers where the model stated 95% confidence, only 160 were correct, an accuracy of 80%. The model is overconfident by 15 points in that bin. The number it reports is not a probability of correctness in any useful sense, at least for this task.

Whether a model is calibrated depends on how it was tuned, how the prompt asks for confidence, the task, and the domain. A model can be well calibrated on multiple-choice trivia and badly calibrated on open-ended legal questions. Tuning that rewards fluent, helpful answers can also push the model toward sounding certain. So the right default is to measure calibration on your own task rather than assume it.

Two lines of work give confidence signals, and each has limits:

- **Verbalised confidence.** You ask the model to state a number or a category ("high, medium, low") alongside its answer. This works with any API and is easy to add. Its limits are that the stated values tend to cluster at round numbers, they shift when the wording of the question changes, and they can be informative for ranking answers within a task while their absolute values mean little.
- **Token-probability confidence.** You read the probabilities the model assigned to the answer tokens. This is less sensitive to phrasing and can carry more information. Its limits are that it needs access to token-level probabilities, which many hosted APIs do not expose. For multi-token answers, the probability of a sequence depends on how it was tokenised and phrased, so two equivalent answers can receive different scores. And a tuned model's token probabilities may be distorted relative to its underlying knowledge.

Two kinds of uncertainty are worth distinguishing, because in principle they call for different responses in deployment:

- **Aleatoric uncertainty** is irreducible noise in the task itself: the input does not determine a single right answer. A summary of an ambiguous document can legitimately vary.
- **Epistemic uncertainty** is the model's ignorance: it lacks knowledge that a better model, or retrieval of the right document, would supply.

The difficulty is that these are hard to tell apart from samples alone. It is tempting to say that sampling many outputs will reveal aleatoric uncertainty, because genuinely ambiguous inputs produce varied answers. But variation in samples reflects the model's own dispersion, which can be high for reasons unrelated to the task. A miscalibrated model can be perfectly consistent on an ambiguous input, giving the same wrong reading every time. And a high-variance response does not prove the input is ambiguous. No standard estimator separates the two decompositions from samples alone, and the decomposition itself is contested for large language models, where the notion of a single "true" conditional distribution is not well defined. So treat the labels as useful vocabulary for thinking about the problem, not as quantities you can read off a dashboard.

In a deployed system, the practical question is which response to make. Dispersion that looks like task ambiguity might suggest presenting a range or asking for clarification. Dispersion that looks like missing knowledge might suggest retrieving more, using a stronger model, or escalating. Because the two cannot be cleanly separated, it is safer to test which response actually helps on labelled cases than to choose by theory.

### 5. Measuring components, interfaces and systems

There are at least three levels at which you can measure an AI application, and they can disagree:

- **Component (task-level) accuracy:** does the generator produce the right answer on a benchmark of isolated inputs?
- **Interface-level validity:** does the output satisfy the contract, such as schema conformance, citation format, or length limits?
- **End-to-end outcome:** does the user get what they needed, measured by task success, complaint rate, or a downstream business metric?

A gain at one level may not transfer to another. A prompt change that raises component accuracy by five points may lower schema validity by three points, and the net effect on end-to-end success depends on how often the parser rejects outputs and what the fallback costs. A model that is more accurate but more verbose may fail length constraints more often. A retriever upgrade that improves recall may increase the amount of distracting context, lowering the generator's accuracy on the passages it is given.

**Design guidance.** A measurement plan should report all three levels for every change, and should record the failure rate at each stage, so that a gain at one level cannot hide a loss at another.

### 6. Evaluation design

An offline evaluation is a held-out set of inputs with reference labels or a scoring method, used to predict how the system will behave on real traffic. Think of it as a rehearsal. A rehearsal predicts the performance only if the rehearsal resembles the show.

**A concrete failure.** A support team builds a 300-item evaluation set by copying clean, well-formed questions from the help centre. The new model scores 92% on it. In production, a large share of messages arrive with typos, several questions in one message, and quoted text from earlier emails. The model's accuracy on those messages is 71%. The evaluation was not wrong about the clean questions; it was measuring a different population. This is the representativeness condition in practice.

An offline evaluation is useful only under certain conditions:

- **Representativeness:** the evaluation inputs are drawn from the same distribution as production inputs, in the sense of the expectation in section 2. Clean benchmark questions do not predict performance on messy multi-part customer messages.
- **No contamination:** the model has not seen the evaluation items during training or prompt development. If the model was trained on a public benchmark, its score measures memorisation as much as capability. The same applies to prompts tuned repeatedly against one dev set, which gradually overfits to it.
- **Stable scoring:** the scoring method agrees with human judgement on the properties that matter.
- **Stable system:** the model version, prompts, retrieval index and tools in the evaluation match those in production. A score from last month's model says little about this month's.

LLM-as-judge scoring, where a model rates another model's output, is widely used because it is cheap. Its limits are real. Judges have position and length biases, may favour outputs in their own style, and can disagree with humans on exactly the cases that matter most. For example, a judge asked to score two answers may prefer whichever is longer, even when the shorter one is correct and the longer one contains a subtle error. Judge scores should be validated against a sample of human labels, with agreement reported, before they are trusted for decisions.

Offline evaluation can fail to predict online behaviour in several ways: the user population shifts, users adapt to the system, the evaluation misses rare but costly failures, or the scoring rewards properties users do not care about. Naming these in advance is part of the evaluation design.

### 7. Cost, latency and variance as design constraints

Because a model call is a sample, you can trade compute for reliability. The simplest version is repeated sampling with majority voting: draw k samples and return the most common answer. The arithmetic is simple but its assumptions are strict, so we set them out per input.

Fix an input x. Let p_x be the probability that a single sample is correct for that input. Suppose the k samples are **conditionally independent given x**. Then the majority vote is correct with probability

q_x = P( Binomial(k, p_x) > k/2 ) for an odd k on a binary decision.

Two things follow. First, if p_x > 1/2, q_x rises toward 1 as k grows. Second, if p_x < 1/2, q_x falls toward 0. A voting scheme does not help an input that the model usually gets wrong; it makes that input's answer more reliably wrong. Overall reliability is the expectation of q_x over the input distribution, E_x[q_x].

This is where average accuracy can mislead. Suppose a classifier is correct 75% of the time on average. That can happen with every input at p_x = 0.75, or with 75% of inputs at p_x = 0.9 and 25% at p_x = 0.3. The average is the same; the voting behaviour is very different.

**Worked example.** Take the first case, every input at p_x = 0.75, with independence. A majority of 9 calls is correct with probability about 0.95. Now take the second case, same average. For the 75% of inputs with p_x = 0.9, a majority of 9 is correct about 99% of the time. For the 25% with p_x = 0.3, it is correct only about 10% of the time. The overall vote accuracy is roughly 0.75 × 0.99 + 0.25 × 0.10, or about 77%. Nine calls buy you two points of improvement over a single call, not twenty.

The independence condition is also strong. Errors on a single input are often shared across samples, because the model makes the same systematic misreading each time. If the errors are correlated, the samples are not independent and the binomial calculation overstates the gain. In the extreme, if every sample on x makes the same mistake, extra samples are not a benefit at all.

Cost and latency scale linearly with k, while the benefit saturates. Going from 1 to 5 samples may be a large gain; going from 15 to 50 may be negligible once the errors are correlated. Verification (having a second call check the first) has a similar profile, and its benefit depends on whether the checker makes different mistakes from the generator, a point developed in Chapter 2.

**Worked example, continued.** A classification step costs 2 cents per call and is correct 80% of the time on average. Voting over 5 calls costs 10 cents. If the errors are independent for every input (p_x = 0.8 throughout), the vote is correct about 94% of the time. Now suppose 80% of inputs have p_x = 0.95 and 20% have p_x = 0.2, which also averages 80%. The vote is correct on the easy inputs about 99.9% of the time and on the hard ones only about 6%, so overall accuracy is about 81%, at five times the cost. The first measurement you need is per-input success: whether a meaningful share of inputs sit below one half, and whether repeated calls on the same hard input give independent answers. Without that, the trade-off cannot be estimated.

### 8. Evidence quality

Claims about applied AI vary enormously in how well they are supported. A rough ordering, from strongest to weakest:

1. **Controlled comparisons** with a fixed evaluation set, multiple runs with reported variance, and a stated baseline. These are the best evidence available, though they still depend on the representativeness conditions above.
2. **Ablation studies** that remove one component and measure the change. Useful, but sensitive to the other components being held fixed.
3. **Leaderboard movement** on public benchmarks. Informative about relative standing at a point in time, but vulnerable to contamination, overfitting to the benchmark, and small score differences that fall within noise.
4. **Single-run demonstrations and anecdotes.** Valuable for generating hypotheses, weak as evidence for a claim about typical behaviour.

A recurring problem is that the noise in an LLM comparison is often as large as the difference being claimed. Consider a test set of 500 items on which a system scores about 80%. Because the test set is a finite sample from the wider population of inputs, the standard error of that accuracy, from item sampling alone, is about sqrt(0.8 × 0.2 / 500), or roughly 1.8 points. Compare two systems on independent test sets and the standard error of their difference is about 2.5 points, so a two-point gain from one run is within noise. Comparing both systems on the same items (a paired comparison) reduces this, which is one reason to prefer paired designs.

Item-sampling error is separate from run-to-run variance. Even on a fixed set of items, rerunning the same system can produce different scores because of sampling and nondeterminism. A credible comparison reports both: the spread across several runs on the same items, and an interval that reflects how many items were tested. Reporting the spread across several seeds or runs is the minimum; reporting item-level uncertainty is the next step.

What is still contested is how to measure these things well. There is no agreed standard for measuring the reliability of a stochastic component under realistic traffic, no consensus on how far LLM judges can be trusted for open-ended tasks, and real disagreement about how much offline gains predict deployed outcomes. Practitioners should treat these as open questions and state their measurement choices explicitly.

### Common mistakes

- **Treating the model as the system.** Most failures attributed to "the model" are interface, retrieval or validation failures. Write the contracts first.
- **Trusting self-reported confidence** as a probability of correctness without checking it against outcomes on your own task.
- **Reporting one number.** A single accuracy figure hides validity, component and end-to-end effects that often move in different directions.
- **Assuming independence** in repeated sampling or multi-stage checking when errors are in fact systematic, or assuming the average accuracy describes every input.
- **Tuning on the test set.** Repeated prompt iteration against one evaluation set quietly turns it into a dev set.
- **Ignoring variance.** Two-point differences from single runs, or from a few hundred items, are frequently within noise.

### Questions to check your understanding

1. A refund stage is specified to return JSON with `decision` and `reason` fields. Assume it enforces this with grammar-constrained decoding. It therefore guarantees syntax, but not semantics. Name two kinds of error it still cannot detect, and say which downstream stage (if any) could catch each. Then say what would change if the stage used parse-and-retry instead.
2. You have an offline benchmark on which a new model scores 4 points higher than the old one. Give two concrete reasons, specific to your application, why this might not predict a better end-to-end result. Then say what sample size you would need before a 4-point gap on one run would be clearly larger than item-sampling error.
3. A classifier is correct 75% of the time per call on average, and you plan a majority vote of 9 calls. If every input has p_x = 0.75 and the calls are independent, the vote is correct about 95% of the time. What must be true for the vote to deliver anything close to that figure in practice? Describe a test that would show whether it holds, and say what result would tell you the errors are concentrated on a subset of inputs.
4. A colleague says, "The model reports 95% confidence, so we can route its answers without review." List what you would need to know about calibration before accepting this, including whether the confidence is verbalised or taken from token probabilities, and what you would measure to check it.

### Key takeaways

- A model is a stochastic component, p(y | x, θ). Its correctness is a probability, not a property of a single output, and task-level reliability is an expectation over the inputs your system actually receives.
- Each stage needs an explicit contract: input type, output type, error modes, and the mechanism that enforces the format. A downstream stage can only catch the violations it checks for.
- Measure at three levels (component, interface, end-to-end) and expect them to disagree.
- An offline evaluation predicts deployed behaviour only when its inputs are representative, uncontaminated, scored reliably, and match the production system. Report the item-sampling error as well as run-to-run variance.
- Repeated sampling trades cost for reliability only when, for each input, the success probability exceeds one half and the errors are conditionally independent given that input. Systematic errors turn extra samples into expensive agreement with a wrong answer.
- Much of what is claimed about applied AI rests on weak evidence, and the measurement methods themselves are still contested. State your methods, report the variance, and check calibration on your own task rather than trusting the model's own report.