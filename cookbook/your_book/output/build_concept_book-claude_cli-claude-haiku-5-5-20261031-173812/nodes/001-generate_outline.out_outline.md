# Concept Book Outline: Applied AI

## Chapter 1: From Models to Systems: The Anatomy of an AI Application

**Key concepts to cover**
- The gap between a model demo and a production AI system
- Core components: model, prompt, context, tools, memory, and output handling
- Inputs, outputs, and the probabilistic nature of model responses
- Deterministic vs. non-deterministic parts of an application
- Common application patterns: classification, extraction, generation, retrieval-augmented Q&A, and agents
- Choosing whether AI is the right tool for a problem

**Learning objectives**
- Describe the main components of an AI application and how they interact
- Distinguish problems that suit AI from those better solved with conventional code
- Identify the common application patterns and match each to a use case
- Explain why the same input can produce different outputs and what that implies for design

## Chapter 2: Prompting and Structured Output

**Key concepts to cover**
- Prompt structure: role, task, context, constraints, and examples
- Zero-shot, few-shot, and chain-of-thought prompting
- Requesting structured output (JSON, schemas) and validating it
- Controlling variability through instructions, temperature, and output format
- Prompt versioning and treating prompts as code
- Common failure modes: hallucination, instruction drift, format errors

**Learning objectives**
- Write prompts with clear role, task, context, and constraints
- Apply few-shot and chain-of-thought techniques where they improve results
- Design a schema for model output and validate responses against it
- Diagnose common prompt failures and revise prompts systematically

## Chapter 3: Context, Retrieval, and Knowledge

**Key concepts to cover**
- Context windows and their limits; what to include and what to leave out
- Embeddings and semantic similarity
- Retrieval-augmented generation (RAG): chunking, indexing, retrieval, and grounding
- Retrieval quality: precision, recall, and reranking
- Citing sources and reducing hallucination through grounding
- Keeping knowledge current: updating indexes and handling stale data

**Learning objectives**
- Explain how embeddings enable semantic search
- Design a basic RAG pipeline with appropriate chunking and retrieval
- Evaluate retrieval quality and identify causes of poor answers
- Ground model responses in source material and attribute claims to sources

## Chapter 4: Tools, Agents, and Orchestration

**Key concepts to cover**
- Function calling and tool use: defining tools, arguments, and results
- The agent loop: observe, reason, act, and check
- Workflow patterns: sequential chains, routing, parallelization, and orchestrator-worker designs
- State management and memory across steps
- Limits on autonomy: step budgets, human-in-the-loop checkpoints, and permissions
- Failure handling: retries, fallbacks, and graceful degradation

**Learning objectives**
- Implement a tool-using workflow with well-defined tool interfaces
- Compare workflow patterns and select one suited to a given task
- Build safeguards that bound agent behavior and cost
- Design error handling that keeps a multi-step process recoverable

## Chapter 5: Evaluation, Safety, and Deployment

**Key concepts to cover**
- Building evaluation sets from representative examples
- Automated and human evaluation; LLM-as-judge and its limitations
- Metrics: accuracy, faithfulness, latency, and cost per task
- Safety and reliability: prompt injection, data leakage, and harmful output
- Monitoring, logging, and feedback loops in production
- Cost, latency, and model selection tradeoffs; deployment and versioning

**Learning objectives**
- Construct an evaluation set and define metrics that reflect real task success
- Assess an AI system's outputs for faithfulness, safety, and reliability
- Identify and mitigate prompt injection and data-handling risks
- Plan monitoring and iteration for a system in production