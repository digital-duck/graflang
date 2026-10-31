## Chapter 1: From Models to Systems: The Anatomy of an AI Application

A model that answers a question well in a notebook is not yet an application. Many teams discover this the hard way. The demo works on the first ten examples, the stakeholders are impressed, and then the system goes to real users, who ask things nobody anticipated, paste in messy text, and expect the same answer tomorrow that they got today. The distance between those two moments is the subject of this book, and this chapter maps it.

### The gap between a demo and a production system

A demo shows that a model *can* do something. A production system has to show that it *does* that thing reliably, for the people who depend on it, under conditions the builder did not control. The difference is less about the model and more about everything wrapped around it.

Consider a demo that summarizes customer emails. It takes one email, sends it to a model, and prints a summary. In production, that same feature must handle emails in twelve languages, emails that are empty, emails that contain attached spreadsheets pasted as text, and emails that try to instruct the model to ignore its instructions. That last case, prompt injection, is a security concern and not only a quality problem: text inside the input can be written to override the application's own instructions. The feature must also log what happened, return results in a format the ticketing system can read, and degrade gracefully when the model provider is slow or down. None of those requirements are visible in the demo, and most of the engineering effort lives in them.

A useful rule: **the model is one component; the application is the design around it.**

### The core components

Most AI applications, however sophisticated, are assembled from a small set of parts:

- **Model.** The language model (or other model) that produces the raw response. You choose it, but you usually do not control its internals. You control what you send it and how you interpret what comes back.
- **Prompt.** The instructions and framing that tell the model its role, its task, and the rules it must follow. The prompt is where most of your design intent is expressed in natural language.
- **Context.** The information the model needs to do the task but does not already have: the user's document, the record being classified, the conversation so far. Context is supplied per request.
- **Tools.** External capabilities the model can request, such as a database lookup, a calculator, or a search call. The model decides *that* a tool is needed; your code decides *how* it runs.
- **Memory.** Information that persists beyond a single request, such as user preferences, earlier conversations, or the state of a multi-step job. The model does not remember anything between calls on its own, so your application stores memory and selectively reintroduces it into the context. Reintroduced memory consumes part of the context budget, and it can mislead the model if it is stale or wrong, so what you store and when you resend it are design decisions.
- **Output handling.** The code that receives the model's response, checks it, parses it, and decides what happens next. This is often the most underestimated component, and it is treated in its own section below.

These components interact in a simple pattern. Your application assembles a prompt from instructions, context, and any relevant memory, sends it to the model, and receives a response. If the response requests a tool, the application runs the tool and sends the result back. Finally, output handling validates the answer and acts on it. Every part of that loop is a place where design decisions, and failures, can occur.

### Output handling in practice

Consider an application that extracts an invoice's vendor, date, and total into a JSON object. The model returns text that looks like JSON. Output handling must first parse it, which can fail if the model wrapped the object in a sentence of commentary. Next it validates the object against a schema: the date must be a real date, the total must be a number, and the required fields must be present. Suppose the total arrives as the string `"1,240.00 EUR"`. Validation fails.

The application then has several options, and choosing among them is part of the design. It can retry the request once with the validation error included in the prompt, which often fixes a format slip but costs latency and money. If the retry also fails, it can fall back to a simpler path, such as a rule-based extractor that handles the common invoice layouts. If neither succeeds, it can route the invoice to a human reviewer and record the failure for later analysis. The application should never write the unvalidated record into the accounting system. Each of these choices shapes what users experience, and the same pattern of parse, validate, retry, fall back, and escalate recurs in every later chapter.

### Inputs, outputs, and probabilistic responses

A model does not look up an answer. It generates one token at a time, choosing each next token from a probability distribution shaped by everything before it. We call this behavior *probabilistic*: the output is a sample from a distribution, not a value read from storage. The rest of this chapter uses that term for the model's responses, and reserves *deterministic* and *non-deterministic* for the parts of the application discussed later.

Two consequences follow directly.

First, **the same input can produce different outputs.** Ask the same question twice and you may get two different phrasings, two different emphases, or occasionally two different conclusions. Sampling settings control how much this happens. Temperature is the main one: at temperature 0 the model always picks the most probable token, which reduces variability but does not guarantee identical outputs. Providers' serving infrastructure, batching, and model updates can still change results from one call to the next, and a higher temperature increases variation further. The practical rule is that lower temperature makes outputs more repeatable, not that it makes them fixed.

Second, **plausible text is usually true, but the model does not signal when it is not.** The model is optimized to produce fluent, likely text. Most of the time, likely text is also accurate, but the model gives no reliable indication of which answers are the exceptions. A confident tone tells you nothing about accuracy.

These are not bugs to be fixed away. They are properties of the material you are building with, and they change what good design looks like. You design around them by constraining outputs, validating them, measuring them, and keeping humans or deterministic checks in the loop where errors are costly.

### Deterministic and non-deterministic parts

A practical way to organize an AI application is to sort its steps into two kinds.

**Deterministic parts** behave the same way every time, given the same inputs: reading a file, parsing JSON, applying a business rule, calling a database with a fixed query, enforcing a permission check, formatting a date. Conventional code is good at these, and you should keep them conventional. They are cheap, testable, and predictable.

**Non-deterministic parts** are steps whose result can vary between runs, because they involve the model: interpreting free text, deciding which category something belongs to, drafting a reply, choosing which tool to call next. These steps are where AI adds value, and where variability enters.

Good application design keeps the boundary between the two sharp. Let the model make the judgments it is suited for, then pass its output through deterministic code that checks it before anything irreversible happens. A common mistake is to let the model's output flow straight into a database write or an outgoing email, with no check in between. That boundary is a common source of production incidents.

### Common application patterns

Most AI features fall into a handful of patterns. Recognizing the pattern early tells you what the model must do, and therefore how to evaluate it.

- **Classification** assigns an input to one of a fixed set of labels: routing a support ticket, flagging spam, tagging a document by topic. The output space is small and well-defined, which makes classification one of the easiest patterns to evaluate.
- **Extraction** pulls structured fields out of unstructured text: names, dates, amounts, and identifiers from an invoice or a contract. The output is a record that can be checked against the source.
- **Generation** produces new text from a brief: a product description, a draft reply, a report section. The output space is open, so evaluation depends on criteria such as accuracy, tone, and compliance rather than exact match.
- **Retrieval-augmented question answering** answers a question using documents the model was not trained on. The application first searches a document store for passages relevant to the question, then places those passages in the context, and the model composes the answer from them. The model still generates the answer; retrieval only supplies the material it works from. You will study this pattern in depth in Chapter 3.
- **Agents** decide, over several steps, which actions to take and when to stop. The model is not only producing an answer but directing a process. Agents offer the most flexibility and the most room for things to go wrong; Chapter 4 covers them in detail.

These patterns are commonly described as rising in autonomy and in difficulty to evaluate, and that ordering is a rough heuristic rather than a strict law. Classification and extraction are usually easier to check than open-ended generation, and a retrieval system's difficulty depends heavily on the quality of its document store and search. Agents are generally the hardest to evaluate because each step can change what the next step sees. Start with the simplest pattern that solves the problem.

### Choosing whether AI is the right tool

Not every problem deserves a model. Before reaching for one, ask whether the task has the properties that make AI useful and whether conventional code would serve better.

AI tends to suit a problem when the input is unstructured or varied (natural language, images, messy documents), when the rules are hard to write down exhaustively but easy to recognize by example, when a reasonably good answer is valuable and a perfect one is not required, and when a human could do the task but the volume makes that impractical.

Conventional code tends to suit a problem when the rules are known and stable, when the input is structured, when the answer must be exactly right every time, when the result must be fully explainable to an auditor, or when the operation is cheap to do deterministically. A tax calculation, a unit conversion, and a permission check belong in ordinary code. Using a model for them adds cost and variability for no benefit.

Even when the task suits AI, practical constraints can decide the question. **Cost** matters because every call is billed, and a feature that runs on every record in a large dataset can cost more than the value it creates. **Latency** matters because a model call often takes seconds, which may be acceptable for a drafting tool and unacceptable in a checkout flow. **Privacy and data residency** matter because sending text to an external provider may be prohibited for some data, which can rule out a hosted model or require a self-hosted one. These constraints often eliminate options before accuracy is even considered, so check them early.

Many good systems combine both: conventional code handles the structured, certain parts, and a model handles the parts that require interpretation. The question is not "AI or not?" but "which part of this problem needs judgment, and which part needs precision?"

### Why the same input can produce different outputs, and what that implies

The variability described above has direct design consequences, and they are worth stating plainly:

- **Do not treat a single response as a fact.** Build in validation, and where stakes are high, check the output against the source or against another signal.
- **Design outputs to be constrained.** A response forced into a schema with a fixed set of labels is far easier to check than free prose. Constraint is one of your strongest tools.
- **Measure, do not assume.** Because outputs vary, one good result proves little. You need many representative inputs and a way to score the results, which is the subject of Chapter 5.
- **Plan for the bad case.** Some fraction of responses will be wrong, malformed, or off-topic. Decide in advance what the application does then: retry, fall back to a simpler path, ask a human, or return an honest "I don't know."
- **Treat input text as untrusted.** Documents, emails, and web pages can contain instructions aimed at the model, such as the injected instruction in the customer-email example. Keep application rules outside the model's reach, limit what tools the model can invoke, and never let model output alone authorize a sensitive action. Chapter 5 covers prompt injection in detail.

The shift in mindset is from *the model returns the answer* to *the system produces a checked answer, and the model is one of its inputs.* Everything that follows in this book is a way of making that shift concrete.