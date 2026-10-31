## Chapter 1: Foundations of Applied AI Systems: Models as Components, Not Oracles

If you have ever used a spreadsheet formula that sometimes returns the wrong answer and sometimes returns a different answer for the same inputs, you have already met the core problem of applied AI. The difference is that a model's randomness is built into what it is, and the things around it (retrieval, parsing, validation, the user interface) have to be engineered to cope with that randomness. This chapter sets up the vocabulary and the habits of mind that the rest of the book depends on. Get these right and the later chapters on agents, verification and prompt optimisation read as obvious consequences. Get them wrong and you will spend months debugging a "bad model" that was really a bad interface.

### 1. Applied AI is systems engineering

A language model on its own is a function from text to text, with a twist: it is stochastic. Given the same prompt, it can produce different outputs. An application built around a model is a pipeline. Some stages are deterministic (reading a file, parsing JSON, looking up a row in a database). Some are stochastic (the model call itself). The engineering work is in the joints between them: what each stage promises to produce, what it accepts as input, and what happens when a promise is broken.

**Worked example.** Consider a system that reads a customer email and decides whether to issue a refund. A naive design sends the email to a model and asks, "Should we refund this?" The output is free text. A downstream script then searches the text for the word "yes". This design has three weak joints: the model may say "Yes, but I would not refund…", the model may refuse to answer, and the script may match "yes" inside "yesterday". None of these failures is the model being stupid. They are failures of the interface between a stochastic component and a deterministic one.

A better design specifies the contract: the model receives the email and must return a JSON object with a field `decision` restricted to `{refund, no_refund, escalate}` and a field `reason` of at most 200 characters. The parser rejects anything else, and a rejection triggers a defined fallback (retry once, then escalate to a human). Now the model can still be wrong about refunds, but it cannot be wrong about the shape of its answer without the system noticing.

### 2. A model as a conditional distribution

The cleanest formal picture of a model is a conditional probability distribution. Write the model as p(y | x, θ), where x is the input (the prompt and any context), θ are the fixed parameters of the model, and y is the output. Calling the model means drawing a sample y ~ p(y | x, θ). Temperature, top-p and similar settings reshape this distribution; they do not change its basic nature.

This framing changes what "correctness" means. A deterministic function f has a correct output f(x), and you can check whether a given run matches it. A component whose outputs are samples has no single correct output for many inputs. What you can ask instead is:

- **Per-sample validity:** the probability that a sampled y satisfies the specification S, written P(S(y) | x).
- **Task-level reliability:** the probability that the system as a whole achieves its goal, which depends on that validity and on how the rest of the pipeline reacts to invalid samples.

For the refund example, P(valid JSON | x) might be 0.97 and P(correct decision | x) might be 0.85. Those are different numbers with different consequences, and a single "accuracy" figure hides both.

### 3. Decomposing an application into stages

Most real applications are chains or graphs of stages. The common kinds are:

- **Retrieval:** select candidate documents or data for a query.
- **Generation:** produce text, code or a structured answer.
- **Tool use:** call an external function (search, calculator, database).
- **Validation:** check the output against rules or a schema.
- **Aggregation:** combine several outputs into one.

For each stage, write a contract with three parts: the **input type** (what it must receive), the **output type** (what it guarantees to return), and the **error modes** (the ways it can fail, and what the next stage will see when it does).

The reason this matters is that a downstream stage can only detect violations that it checks for. A validator that checks JSON syntax will catch a missing brace but not a hallucinated customer ID that happens to be well-formed. A generator that is told to "cite sources" will produce citations that look plausible but point to documents the retriever never returned. These are contract violations the downstream stage cannot see, because its check does not cover that property.

**Worked example.** A three-stage pipeline: retrieve five passages, generate an answer, validate that the answer's format is right. Suppose the retriever returns passages that are semantically related but do not contain the answer (a recall failure). The generator, asked to answer from the passages, will often produce a fluent answer from its own memory and attribute it to the passages. The validator, which checks format, passes it. The end-user sees a confident, well-formatted, wrong answer. The contract "output is grounded in the retrieved passages" was never specified, so no stage was responsible for enforcing it. Writing that contract, and giving some stage the job of checking it, is the design task.

### 4. Calibration and uncertainty

When a model reports a confidence ("I am 90% sure"), that number is usually a poor signal of its probability of being right. Models trained to produce fluent, helpful text tend to sound confident regardless of accuracy. Verbalised confidence can be useful for ranking within a task, but its absolute values often do not match observed accuracy, and they shift when the prompt or the model changes.

Two kinds of uncertainty are worth distinguishing, because they call for different responses in deployment:

- **Aleatoric uncertainty** is irreducible noise in the task itself: the input does not determine a single right answer (for example, a summary of an ambiguous document can legitimately vary). Sampling many outputs will show it. More data about the model does not remove it.
- **Epistemic uncertainty** is the model's ignorance: it lacks knowledge that a better model, or retrieval of the right document, would supply. Sampling can show inconsistency that signals it, but consistency is not proof of knowledge (a model can be consistently wrong).

In a deployed system, the practical question is which response to make. Aleatoric variance suggests you should present a range or ask for clarification. Epistemic uncertainty suggests you should retrieve more, use a stronger model, or escalate. Treating all disagreement among samples as one kind of problem leads to the wrong fix.

### 5. Measuring components, interfaces and systems

There are at least three levels at which you can measure an AI application, and they can disagree:

- **Component (task-level) accuracy:** does the generator produce the right answer on a benchmark of isolated inputs?
- **Interface-level validity:** does the output satisfy the contract, such as schema conformance, citation format, or length limits?
- **End-to-end outcome:** does the user get what they needed, measured by task success, complaint rate, or downstream business metric?

A gain at one level may not transfer to another. A prompt change that raises component accuracy by five points may lower schema validity by three points, and the net effect on end-to-end success depends on how often the parser rejects outputs and what the fallback costs. A model that is more accurate but more verbose may fail length constraints more often. A retriever upgrade that improves recall may increase the amount of distracting context, lowering the generator's accuracy on the passages it is given.

**Design guidance.** A measurement plan should report all three levels for every change, and should record the failure rate at each stage, so that a gain at one level cannot hide a loss at another.

### 6. Evaluation design

An offline evaluation is a held-out set of inputs with reference labels or a scoring method, used to predict how the system will behave on real traffic. It is useful only under certain conditions:

- **Representativeness:** the evaluation inputs are drawn from the same distribution as production inputs. A benchmark of clean, well-formed questions does not predict performance on typo-filled, multi-part customer messages.
- **No contamination:** the model has not seen the evaluation items during training or prompt development. If the model was trained on a public benchmark, its score measures memorisation as much as capability. The same applies to prompts tuned repeatedly against one dev set, which gradually overfits to it.
- **Stable scoring:** the scoring method agrees with human judgement on the properties that matter.
- **Stable system:** the model version, prompts, retrieval index and tools in the evaluation match those in production. A score from last month's model says little about this month's.

LLM-as-judge scoring, where a model rates another model's output, is widely used because it is cheap. Its limits are real. Judges have position and length biases, may favour outputs in their own style, and can disagree with humans on exactly the cases that matter most. Judge scores should be validated against a sample of human labels, with agreement reported, before they are trusted for decisions.

Offline evaluation can fail to predict online behaviour in several ways: the user population shifts, users adapt to the system, the evaluation misses rare but costly failures, or the scoring rewards properties users do not care about. Naming these in advance is part of the evaluation design.

### 7. Cost, latency and variance as design constraints

Because a model call is a sample, you can trade compute for reliability. The simplest version is repeated sampling with majority voting: draw k samples and return the most common answer. If each sample is independently correct with probability p > 0.5 on a binary decision, the majority is correct with probability that rises with k. For p = 0.7 and k = 5, a simple binomial calculation gives roughly 0.84; for k = 15 it is about 0.95.

The assumptions behind that calculation are strong. The samples must be **independent** given the input, which they are not if the model has a systematic bias: if the model is wrong 30% of the time because of a consistent misreading, voting over 15 samples will converge confidently on the wrong answer. The per-sample accuracy must be above chance, and the answers must be drawn from a discrete set that can be counted.

Cost and latency scale linearly with k, while the benefit saturates. Going from 1 to 5 samples may be a large gain; going from 15 to 50 may be negligible once the errors are correlated. Verification (having a second call check the first) has a similar profile, and its benefit depends on whether the checker makes different mistakes from the generator, a point developed in Chapter 2.

**Worked example.** Suppose a classification step costs 2 cents per call and is correct 80% of the time. Voting over 5 calls costs 10 cents and, if errors are independent, raises accuracy to about 94%. If the true error rate is concentrated on a class of inputs the model systematically misreads, the same 5 calls may raise accuracy only to 81%, at five times the cost. The first measurement you need is whether the errors are independent. Without it, the trade-off cannot be estimated.

### 8. Evidence quality

Claims about applied AI vary enormously in how well they are supported. A rough ordering, from strongest to weakest:

1. **Controlled comparisons** with a fixed evaluation set, multiple runs with reported variance, and a stated baseline. These are the best evidence available, though they still depend on the representativeness conditions above.
2. **Ablation studies** that remove one component and measure the change. Useful, but sensitive to the other components being held fixed.
3. **Leaderboard movement** on public benchmarks. Informative about relative standing at a point in time, but vulnerable to contamination, overfitting to the benchmark, and small score differences that fall within run-to-run noise.
4. **Single-run demonstrations and anecdotes.** Valuable for generating hypotheses, weak as evidence for a claim about typical behaviour.

A recurring problem is that the variance of an LLM system across runs is often comparable to the difference between two approaches. A two-point gain from a single run may be noise. Reporting the spread across several seeds or runs is the minimum for a credible comparison.

What is still contested is how to measure these things well. There is no agreed standard for measuring the reliability of a stochastic component under realistic traffic, no consensus on how far LLM judges can be trusted for open-ended tasks, and real disagreement about how much offline gains predict deployed outcomes. Practitioners should treat these as open questions and state their measurement choices explicitly.

### Common mistakes

- **Treating the model as the system.** Most failures attributed to "the model" are interface, retrieval or validation failures. Write the contracts first.
- **Trusting self-reported confidence** as a probability of correctness without checking it against outcomes.
- **Reporting one number.** A single accuracy figure hides validity, component and end-to-end effects that often move in different directions.
- **Assuming independence** in repeated sampling or multi-stage checking when errors are in fact systematic.
- **Tuning on the test set.** Repeated prompt iteration against one evaluation set quietly turns it into a dev set.
- **Ignoring variance.** Two-point differences from single runs are frequently within noise.

### Questions to check your understanding

1. A structured-output stage guarantees that every response parses as valid JSON with the required fields. Name two kinds of error it still cannot detect, and say which downstream stage (if any) could.
2. You have an offline benchmark on which a new model scores 4 points higher than the old one. Give two concrete reasons, specific to your application, why this might not predict a better end-to-end result.
3. A classifier is correct 75% of the time per call. You plan to use a majority vote of 9 calls. What must be true about the errors for this to reach roughly 90% or better, and how would you test whether it holds?
4. A colleague says, "The model reports 95% confidence, so we can route its answers without review." List what you would need to know about calibration before accepting this.

### Key takeaways

- A model is a stochastic component, p(y | x, θ). Its correctness is a probability, not a property of a single output.
- Each stage needs an explicit contract: input type, output type, and error modes. A downstream stage can only catch the violations it checks for.
- Measure at three levels (component, interface, end-to-end) and expect them to disagree.
- An offline evaluation predicts deployed behaviour only when its inputs are representative, uncontaminated, scored reliably, and match the production system.
- Repeated sampling trades cost for reliability, but only when errors are independent. Systematic errors make extra samples expensive agreement with the wrong answer.
- Much of what is claimed about applied AI rests on weak evidence, and the measurement methods themselves are still contested. State your methods and report variance.