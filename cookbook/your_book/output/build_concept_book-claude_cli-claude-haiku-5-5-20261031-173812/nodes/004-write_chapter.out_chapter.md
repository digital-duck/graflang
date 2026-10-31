## Chapter 1: From Models to Systems: The Anatomy of an AI Application

A model that answers a question well in a notebook is not yet an application. Many teams discover this the hard way. The demo works on the first ten examples, the stakeholders are impressed, and then the system goes to real users, who ask things nobody anticipated, paste in messy text, and expect the same answer tomorrow that they got today. The distance between those two moments is the subject of this book, and this chapter maps it.

### The gap between a demo and a production system

A demo shows that a model *can* do something. A production system has to show that it *does* that thing reliably, for the people who depend on it, under conditions the builder did not control. The difference is less about the model and more about everything wrapped around it.

Consider a demo that summarizes customer emails. It takes one email, sends it to a model, and prints a summary. In production, that same feature must handle emails in twelve languages, emails that are empty, emails that contain attached spreadsheets pasted as text, and emails that try to instruct the model to ignore its instructions. It must log what happened, return results in a format the ticketing system can read, and degrade gracefully when the model provider is slow or down. None of those requirements are visible in the demo, and most of the engineering effort lives in them.

A useful rule: **the model is one component; the application is the design around it.**

### The core components

Most AI applications, however sophisticated, are assembled from a small set of parts:

- **Model.** The language model (or other model) that produces the raw response. You choose it, but you usually do not control its internals. You control what you send it and how you interpret what comes back.
- **Prompt.** The instructions and framing that tell the model its role, its task, and the rules it must follow. The prompt is where most of your design intent is expressed in natural language.
- **Context.** The information the model needs to do the task but does not already have: the user's document, the record being classified, the conversation so far. Context is supplied per request.
- **Tools.** External capabilities the model can request, such as a database lookup, a calculator, or a search call. The model decides *that* a tool is needed; your code decides *how* it runs.
- **Memory.** Information that persists beyond a single request, such as user preferences, earlier conversations, or the state of a multi-step job. Memory is something your application stores and selectively reintroduces; the model does not remember anything between calls on its own.
- **Output handling.** The code that receives the model's response, checks it, parses it, and decides what happens next. This is often the most underestimated component. A model's text is not a trustworthy data structure until your code has verified it.

These components interact in a simple pattern. Your application assembles a prompt from instructions, context, and any relevant memory, sends it to the model, and receives a response. If the response requests a tool, the application runs the tool and sends the result back. Finally, output handling validates the answer and acts on it. Every part of that loop is a place where design decisions, and failures, can occur.

### Inputs, outputs, and probabilistic responses

A model does not look up an answer. It generates one token at a time, choosing each next token from a probability distribution shaped by everything before it. Two consequences follow directly.

First, **the same input can produce different outputs.** Ask the same question twice and you may get two different phrasings, two different emphases, or occasionally two different conclusions. Sampling settings such as temperature influence how much this happens, but even at low settings, outputs are not guaranteed to be identical across calls, across model versions, or across provider infrastructure changes.

Second, **a fluent answer is not evidence of a correct one.** The model is optimized to produce plausible text. Plausible and true usually overlap, but not always, and the model does not signal which case it is in. A confident tone tells you nothing about accuracy.

These are not bugs to be fixed away. They are properties of the material you are building with, and they change what good design looks like. You design around them by constraining outputs, validating them, measuring them, and keeping humans or deterministic checks in the loop where errors are costly.

### Deterministic and non-deterministic parts

A practical way to organize an AI application is to sort its steps into two kinds.

**Deterministic parts** behave the same way every time: reading a file, parsing JSON, applying a business rule, calling a database with a fixed query, enforcing a permission check, formatting a date. Conventional code is good at these, and you should keep them conventional. They are cheap, testable, and predictable.

**Non-deterministic parts** involve the model: interpreting free text, deciding which category something belongs to, drafting a reply, choosing which tool to call next. These steps are where AI adds value, and where variability enters.

Good application design keeps the boundary between the two sharp. Let the model make the judgments it is suited for, then pass its output through deterministic code that checks it before anything irreversible happens. A common mistake is to let the model's output flow straight into a database write or an outgoing email, with no check in between. That boundary is where most production incidents begin.

### Common application patterns

Most AI features fall into a handful of patterns. Recognizing the pattern early tells you what the model must do, and therefore how to evaluate it.

- **Classification** assigns an input to one of a fixed set of labels: routing a support ticket, flagging spam, tagging a document by topic. The output space is small and well-defined, which makes classification one of the easiest patterns to evaluate.
- **Extraction** pulls structured fields out of unstructured text: names, dates, amounts, and identifiers from an invoice or a contract. The output is a record that can be checked against the source.
- **Generation** produces new text from a brief: a product description, a draft reply, a report section. The output space is open, so evaluation depends on criteria such as accuracy, tone, and compliance rather than exact match.
- **Retrieval-augmented question answering** answers a question using documents the model was not trained on, fetched at request time. The model composes the answer from retrieved passages. You will study this pattern in depth in Chapter 3.
- **Agents** decide, over several steps, which actions to take and when to stop. The model is not only producing an answer but directing a process. Agents offer the most flexibility and the most room for things to go wrong; Chapter 4 covers them in detail.

Notice that these patterns increase in autonomy and in difficulty to evaluate, roughly in the order listed. A classifier with a fixed label set is far easier to reason about than an agent that chooses its own path. Start with the simplest pattern that solves the problem.

### Choosing whether AI is the right tool

Not every problem deserves a model. Before reaching for one, ask whether the task has the properties that make AI useful and whether conventional code would serve better.

AI tends to suit a problem when the input is unstructured or varied (natural language, images, messy documents), when the rules are hard to write down exhaustively but easy to recognize by example, when a reasonably good answer is valuable and a perfect one is not required, and when a human could do the task but the volume makes that impractical.

Conventional code tends to suit a problem when the rules are known and stable, when the input is structured, when the answer must be exactly right every time, when the result must be fully explainable to an auditor, or when the operation is cheap to do deterministically. A tax calculation, a unit conversion, and a permission check belong in ordinary code. Using a model for them adds cost and variability for no benefit.

Many good systems combine both: conventional code handles the structured, certain parts, and a model handles the parts that require interpretation. The question is not "AI or not?" but "which part of this problem needs judgment, and which part needs precision?"

### Why the same input can produce different outputs, and what that implies

The variability described above has direct design consequences, and they are worth stating plainly:

- **Do not treat a single response as a fact.** Build in validation, and where stakes are high, check the output against the source or against another signal.
- **Design outputs to be constrained.** A response forced into a schema with a fixed set of labels is far easier to check than free prose. Constraint is one of your strongest tools.
- **Measure, do not assume.** Because outputs vary, one good result proves little. You need many representative inputs and a way to score the results, which is the subject of Chapter 5.
- **Plan for the bad case.** Some fraction of responses will be wrong, malformed, or off-topic. Decide in advance what the application does then: retry, fall back to a simpler path, ask a human, or return an honest "I don't know."

The shift in mindset is from *the model returns the answer* to *the system produces a checked answer, and the model is one of its inputs.* Everything that follows in this book is a way of making that shift concrete.