## Chapter 1: Foundations of Applied AI Systems: Models as Components, Not Oracles

- **Key concepts to cover**
  - Applied AI as systems engineering: a model is one stochastic component inside a pipeline with deterministic parts, interfaces, and failure handling
  - Formal framing of a model as a conditional distribution p(y | x, θ) and what "correctness" means for a component whose outputs are samples, not functions
  - Decomposing an application into stages (retrieval, generation, tool use, validation, aggregation) and specifying each stage's contract: input type, output type, error modes
  - Calibration and uncertainty at the system level: why a model's self-reported confidence is often a poor signal, and the difference between epistemic and aleatoric uncertainty as they show up in deployed behaviour
  - Measuring components versus measuring systems: task-level accuracy, interface-level validity (e.g. schema conformance), and end-to-end outcome metrics, and why they can disagree
  - Evaluation design: held-out sets, contamination risk, the limits of LLM-as-judge scoring, and the conditions under which an offline benchmark predicts online performance
  - Cost, latency, and variance as first-class design constraints, including how repeated sampling trades compute for reliability and where that trade stops paying off
  - Evidence quality: which claims in applied AI rest on controlled comparisons and which rest on anecdote or leaderboard movement, and what is still contested about how to measure them

- **Learning objectives**
  - After this chapter the reader can decompose a proposed AI application into components with explicit input/output contracts and identify which contract violations a downstream stage cannot detect.
  - After this chapter the reader can state the conditions under which an offline evaluation is a valid predictor of system behaviour, and name at least two ways such a prediction can fail.
  - After this chapter the reader can design a measurement plan that separates component-level, interface-level, and end-to-end metrics, and explain why a gain at one level may not transfer to another.
  - After this chapter the reader can estimate the cost-reliability trade-off of repeated sampling with voting or verification, and state the assumptions under which the trade-off is favourable.

## Chapter 2: Composing and Controlling Models in Agentic and Grounded Systems

- **Key concepts to cover**
  - Grounding as conditioning: retrieval-augmented generation viewed as a change of the conditional distribution, with the retriever's recall and precision bounding what the generator can use
  - Failure decomposition in RAG: retrieval failure, context-utilisation failure, and generation failure, and how to attribute errors among them
  - Tool use and agent loops as sequential decision processes: action spaces, observation feedback, termination, and the compounding of per-step error rates over long horizons
  - Verification and critique loops (self-refinement, reranking, process reward models, external verifiers): when they reduce error, when they amplify it through correlated mistakes, and what independence assumptions they rely on
  - Structured output and constrained decoding: the formal guarantee they provide (syntactic validity) versus what they do not guarantee (semantic correctness, faithfulness)
  - Prompt and context as an optimisation surface: sensitivity to ordering and formatting, the status of automated prompt optimisation results, and the risk of overfitting prompts to a dev set
  - Safety and reliability boundaries in deployed systems: permission scoping for tools, prompt-injection as an untrusted-input problem, and the limits of guardrail classifiers
  - Open problems and contested questions: whether agent reliability scales with model capability or with harness design, the reproducibility crisis in reported agent benchmarks, and the unresolved evaluation of long-horizon behaviour

- **Learning objectives**
  - After this chapter the reader can attribute an end-to-end failure in a retrieval-augmented or agentic system to retrieval, context use, or generation, using a stated diagnostic procedure.
  - After this chapter the reader can model an agent loop's success probability as a function of per-step reliability and horizon length, and state the independence assumption this model requires.
  - After this chapter the reader can judge whether a verification or critique stage will reduce error in a given system, by checking whether its errors are correlated with the generator's.
  - After this chapter the reader can specify the security and reliability boundaries of a tool-using system, distinguishing guarantees from constrained decoding, permission scoping, and classifier-based guardrails, and state what each one does not protect against.