## Chapter 2: Prompting and Structured Output

A prompt is the part of an AI application you can change most quickly, and that is exactly why it deserves care. A single sentence edit can shift an application's behavior across thousands of requests. Treat the prompt as an interface specification, not a casual string: it states what the model should do, what it should know, what it must avoid, and what shape its answer should take. This chapter shows how to write prompts that do those jobs reliably, how to get machine-readable output you can trust, and how to diagnose and fix the failures that appear when the prompt is not doing its job.

### Anatomy of a prompt

Most effective prompts contain five parts. You do not always need all five, but knowing them gives you a checklist when a prompt underperforms.

- **Role** tells the model what perspective to adopt: "You are a contracts paralegal reviewing vendor agreements." A role sets tone and domain vocabulary. It does not add knowledge the model lacks, so do not rely on it to make the model an expert.
- **Task** states the action in concrete terms. "Summarize" is vague; "List the three payment obligations in this contract, each in one sentence" is specific enough to check.
- **Context** supplies the material the model needs: the document, the customer's history, the product catalog excerpt. Context is where most application-specific information lives, and it is also where prompts become long and expensive.
- **Constraints** define the boundaries: length limits, what to exclude, what to do when the answer is unknown, and how to format the result.
- **Examples** show the desired input-output behavior directly. They are often the most powerful part of a prompt, and they are discussed below.

Separate these parts visibly. Headings, XML-style tags such as `<document>...</document>`, or clearly labeled sections help the model distinguish instructions from data. This matters most when the context contains user-supplied text, because a clear boundary makes it harder for that text to be read as instructions.

A weak prompt and a strong one for the same task show the difference:

> Weak: "Read this review and tell me about the sentiment."

> Strong: "You are a customer-support analyst. Classify the sentiment of the review inside `<review>` tags as `positive`, `negative`, or `mixed`. Base the label only on the review text. If the review is not about a product, return `unclear`. Respond with the label only."

The strong version tells the model exactly what to output, what to ignore, and what to do at the edges. It is also far easier to test.

### Zero-shot, few-shot, and chain-of-thought

These three techniques differ in how much guidance you give the model before asking for the answer.

**Zero-shot prompting** gives instructions with no examples. It works well for tasks the model handles routinely, such as translation or simple classification with clear categories. Its weakness is ambiguity: when your definition of a category differs from the model's default, zero-shot results drift.

**Few-shot prompting** includes a handful of worked examples. Examples communicate edge-case rules more efficiently than prose. Suppose "mixed" sentiment confuses the model. Two examples, one showing a review that praises the product but complains about shipping and one showing a neutral review, will often resolve the confusion faster than another paragraph of definitions. Keep the set small, cover the hard cases, and keep the examples' format identical to what you want the model to produce. Order can matter, so vary the examples' labels rather than presenting all the positives first. Few-shot examples also consume context, so they are a cost as well as a benefit.

**Chain-of-thought (CoT) prompting** asks the model to reason through intermediate steps before giving its final answer. It improves results on multi-step problems such as arithmetic, multi-clause logic, or deciding among several policy rules. You can request it explicitly ("Work through the steps, then give the final answer on a line beginning `Answer:`") or demonstrate it in a few-shot example.

CoT is not free. It increases output tokens and latency, and it does not help simple lookups or classifications. Its visible reasoning can also be verbose or unhelpful to end users. A practical pattern separates the two: let the model reason in a scratchpad section, then parse only the final answer field. Whether you show or hide the reasoning depends on the application, but you should always measure whether CoT actually improves the result on your task, not assume it does.

### Structured output: asking for shape, then checking it

Applications rarely want free prose. They want a label to route on, a record to store, or fields to pass to the next step. Requesting structured output, most commonly JSON, turns the model's answer into data a program can use.

Start by designing the schema before writing the prompt. A schema is a contract. For a support-ticket extractor it might specify:

```json
{
  "type": "object",
  "required": ["category", "priority", "summary"],
  "properties": {
    "category": {"type": "string", "enum": ["billing", "technical", "account", "other"]},
    "priority": {"type": "integer", "minimum": 1, "maximum": 4},
    "summary": {"type": "string", "maxLength": 200}
  },
  "additionalProperties": false
}
```

Constrained choices (`enum`), numeric ranges, and required fields catch many errors that free text would hide. Name fields clearly, and avoid nesting deeper than the task needs.

Many model APIs offer structured-output or tool-schema features that enforce the schema during generation. Use them when available, but do not stop there. Even with enforcement, you still need to validate the response in your own code, for three reasons: the enforcement may not cover every constraint (a `maxLength` or a cross-field rule, for example), the schema may change over time, and the response may be truncated or refused. Validation should:

1. Parse the output, catching syntax errors.
2. Check the schema, catching missing fields and wrong types.
3. Check semantic rules the schema cannot express, such as "`end_date` must not precede `start_date`."
4. Decide what happens on failure: retry with the validation error included in the prompt, fall back to a default, or route to a human.

Make the retry bounded. Re-asking an unbounded number of times is a cost and latency trap. Log every failure with the raw output so you can see which constraint the model keeps violating, since that pattern usually points to a prompt problem.

### Controlling variability

Model outputs vary, and you control that variation at three levels.

**Instructions** are the primary lever. A prompt that says "answer in at most two sentences, using only the provided document" narrows the output more than any setting does.

**Temperature** (and related sampling parameters) controls randomness in token selection. Low temperature makes outputs more repeatable; high temperature makes them more varied. For classification, extraction, and anything you need to reproduce, use low temperature. For brainstorming or creative drafting, higher values help. Lower temperature does not guarantee identical outputs, and some providers do not expose it for every model, so do not build a system that depends on exact repeatability.

**Output format** constrains variability structurally. A label drawn from an enum has far less variation than a free sentence. The more of the output you pin to a format, the easier downstream handling becomes.

The right combination depends on the task, and the only reliable way to choose is to measure. Run the same prompt across a set of representative inputs several times and check how often the outputs agree and how often they are correct.

### Prompts as code

A prompt that changes an application's behavior is part of the application's code and should be handled the same way. That means:

- **Version it.** Store prompts in files or a registry with identifiers and version numbers, so every output can be traced to the prompt that produced it.
- **Review changes.** A prompt edit deserves the same review as a code change, because its effects are equally broad.
- **Test it.** Keep a set of inputs with expected outputs, and run the set whenever the prompt changes. Chapter 5 covers building that set in detail.
- **Keep prompts separate from logic.** Templates with named placeholders make it clear what varies per request and what is fixed.
- **Record the model and parameters.** A prompt's behavior depends on the model it runs against. When you upgrade the model, rerun your tests before assuming the old prompt still works.

Versioning prompts is cheap and pays off the first time a regression appears in production and you need to know exactly what changed.

### Failure modes and how to diagnose them

Three failure modes account for most prompt problems.

**Hallucination** is the model producing plausible content that is not supported by its inputs or by fact. It appears when the prompt asks for information the context does not contain, when the model is pushed to answer when it should decline, or when the request invites invention, such as "cite three studies on this." Diagnosis starts with a question: is the needed information in the context? If not, the fix is usually to add the information, or to instruct the model to answer "not in the provided text" when it cannot find support. Grounding techniques are covered in Chapter 3.

**Instruction drift** is a gradual departure from the requested behavior. The model follows the first few instructions and neglects later ones, or its output style slides over a long conversation or a long document. Drift is often a sign that the prompt is too long, its constraints conflict, or the important instructions are buried. Fixes include shortening the prompt, moving critical constraints to the end (where they are more salient) or repeating them, removing contradictions, and splitting one overloaded prompt into several focused steps.

**Format errors** are outputs that fail the schema or parsing: invalid JSON, a missing field, prose wrapped around the JSON, or an enum value that is not in the list. They are usually fixable by being more explicit about the format, providing one example of the exact output, and using structured-output features where the provider supports them. Track format error rates separately from correctness, because a format error stops the pipeline entirely, while a wrong answer may go unnoticed.

When a prompt fails, resist the urge to make a broad rewrite. Change one thing, rerun the test set, and compare the result. A systematic process is the only way to know whether a revision helped, and it is the basis for the evaluation discipline developed in Chapter 5.

### Putting it together

Good prompting is a design activity with a clear sequence. Define the output contract first: the schema, the allowed values, and the failure behavior. Write the prompt with the five parts, add a few examples for the hard cases, and use reasoning steps only where they measurably help. Keep the output at a low-variability setting for tasks that need repeatable answers. Validate every response against the contract, retry within a fixed budget, and log the failures. Finally, version the prompt like code and test it against representative inputs, so that each change is a deliberate improvement rather than a guess.