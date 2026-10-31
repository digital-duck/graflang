## Chapter 2: Building a Useful System Around a Model

A model on its own is a clever guesser. Ask it a question and it answers from whatever it absorbed during training, which may be out of date, incomplete, or simply not about your business. Most useful AI products are therefore not "a model." They are a model wrapped in a few extra parts that supply the right information, shape the answer, and check the result. This chapter shows you those parts. By the end you will be able to build a small question-answering tool over your own documents, and you will know how to tell whether it is working.

### From one call to a system

Think of a kitchen. The cook (the model) is important, but a restaurant meal also depends on the ingredients you buy, the recipe the cook follows, and a taste test before the plate leaves the kitchen. If the ingredients are wrong, a skilled cook still makes a poor dish.

An AI system has the same shape:

- **Input**: the question, plus any data the system gathers for it.
- **Model**: the component that reads the prompt and writes an answer.
- **Checks**: code or a second review that inspects the answer before anyone sees it.
- **Output**: the answer, delivered in a form the rest of the software can use.

When people say a system "works," they usually mean all four parts work together. A better model rarely fixes a bad ingredient supply or a missing taste test.

### Grounding: give the model the facts

Suppose a customer asks, "Can I return a sale item after 30 days?" If you send only the question, the model guesses based on general knowledge about returns. It may sound confident and be wrong about your shop.

**Grounding** means putting the relevant facts into the prompt at the moment of the question. For example:

> Use only the policy below to answer the customer.
>
> Policy: Sale items may be returned within 14 days with a receipt. Final-sale items cannot be returned.
>
> Question: Can I return a sale item after 30 days?

Now the model has something specific to work from. It can answer "No, returns on sale items are accepted only within 14 days," because the answer is in the text in front of it. The model is no longer relying on memory alone.

### Retrieval: finding the right facts

Grounding works well when the facts are short, as in a single policy. Real documents are longer. Suppose you have a 10-page product manual and a user asks, "How do I reset the device?"

Pasting all 10 pages into every prompt is slow and costly, and the model may miss the important lines in the middle. **Retrieval** solves this in three steps:

1. **Split** the manual into passages, for example one per section.
2. **Search** the passages for the ones most related to the question. Simple search matches on words; more advanced systems compare meanings. Either way, the goal is the same: find the few passages that matter.
3. **Include** only those passages in the prompt, along with the question.

Here is a tiny sketch of the idea, with the search done by simple word matching:

```python
def retrieve(question, passages, k=2):
    words = set(question.lower().split())
    scored = sorted(passages, key=lambda p: -len(words & set(p.lower().split())))
    return scored[:k]
```

For a question about resetting, this might pick the "Resetting the device" and "Troubleshooting" sections. The model then answers from those two passages. Retrieval plus grounding is the core pattern behind most document question-answering tools.

### Structured output: answers the program can use

A person reads a paragraph. A program needs fields it can check and store. If your system must record a ticket's category and priority, asking for free text is risky: the model might write "This looks urgent" when you expected `high`.

**Structured output** means you ask for a fixed format, usually JSON with named fields:

> Answer the question using the passages. Reply only with JSON in this form:
> `{"answer": string, "source_section": string, "confident": true or false}`

Your code can then read the answer like any other data:

```python
import json

reply = '{"answer": "Hold the power button for 10 seconds.", "source_section": "Resetting the device", "confident": true}'
data = json.loads(reply)
print(data["answer"])
```

Models do not always follow the format, so the next section matters.

### Checking the output

Two simple checks catch many problems:

- **Rule checks**: code tests the output. Does it parse as JSON? Is `answer` present and non-empty? Is `source_section` one of the section names you supplied? If a check fails, the system can retry or flag the question for a person.
- **Review checks**: a second model call (or a person) reads the first answer alongside the passages and asks, "Is this answer supported by the text?" This is slower and costs more, so it is often reserved for high-stakes answers.

Checks do not make the model right. They make wrong answers easier to notice and stop malformed ones from reaching your program.

### Hallucination: confident inventions

A **hallucination** is an answer that sounds fluent and certain but is not supported by the facts. A model that has been asked a question with no relevant text available may produce a plausible-sounding reply built from patterns in its training, not from your documents.

Why does this happen? The model is trained to produce likely continuations of text, and a likely-sounding answer is not the same as a true one. It has no built-in step that says "I checked this against a source."

Grounding and retrieval reduce hallucination because they give the model a source to copy from. Structured output with a `source_section` field and a rule check that the section exists reduces it further. Yet none of these eliminate it. The model can still misread a passage, combine two passages wrongly, or invent a detail that the passage does not contain. Treat hallucination as a rate to measure and manage, not a bug you can finally close.

Hallucination is most dangerous when the answer looks authoritative. A system that cites a section number and quotes it confidently can still be wrong, which is why the next section matters.

### Evaluating the system

How do you know the system is good? Build a **test set**: a small list of questions, each with a known good answer taken from your documents. Twenty questions is a reasonable start.

| Question | Expected answer |
|---|---|
| How do I reset the device? | Hold the power button for 10 seconds. |
| What is the warranty period? | Two years from the purchase date. |
| Can I use the charger abroad? | Yes, with a plug adapter. |

Run the system on every question and count how many answers match. Then change something (a better search, a new prompt, a different model) and run the same questions again. If the score rises, the change helped on this set. If it falls, undo it.

A test set has limits. Twenty questions cannot cover everything users will ask, and matching is hard to judge when answers are worded differently. Start with a small, honest set and grow it as you find failures.

### Cost, speed, and privacy

Every model call costs money and takes time. Pricing is usually per token, roughly per word or word fragment in the prompt and the reply. Retrieval helps here: sending two relevant passages costs far less than sending a whole manual.

A simple budget makes this concrete. Suppose each question sends about 1,500 tokens and gets back about 200. If your tool handles 1,000 questions a month, that is 1,700,000 tokens. Multiply by your provider's price per thousand tokens to estimate the monthly bill. Doubling the passages doubles the input cost, so keep retrieval focused.

Privacy needs the same attention. When you send text to a third-party model service, that text leaves your machine and is governed by the provider's terms. Customer names, medical notes, or internal financial figures should not go into a prompt without a decision about whether that service is allowed to see them. Remove or mask personal details where you can, and check what your provider does with the data.

### A complete small project

Here is how the pieces combine into a question-answering tool over a few documents:

1. **Load and split** the documents into passages, one per section.
2. **Retrieve** the two or three passages most related to the question.
3. **Ask** the model, with grounding instructions and a required JSON format.
4. **Check** the reply: it must parse, contain a non-empty answer, and name a real source section. If it fails, retry once, then flag it.
5. **Test** with your question set, record the score, and repeat after every change.

Each step is small. The value comes from putting them together and measuring the result.

### Common mistakes

- **Assuming the model knows your documents.** It does not, unless you supply the text.
- **Sending everything.** Long prompts cost more, run slower, and can bury the relevant lines.
- **Trusting format as proof of accuracy.** Valid JSON can still contain a wrong answer.
- **Skipping the test set.** Without it, you cannot tell whether a change helped or hurt.
- **Believing hallucination can be eliminated.** It can be reduced and detected, not guaranteed away.

### Check your understanding

1. In the kitchen analogy, what plays the role of the ingredients in an AI system, and why does a good cook still need good ingredients?
2. Why does retrieving two relevant passages usually beat pasting an entire 10-page manual into the prompt? Name one reason about accuracy and one about cost.
3. A model returns valid JSON with a non-empty `answer`, but the answer is wrong. Which check would have caught it, and which kind of check would still miss it?
4. You change your search method and your test score drops from 16 out of 20 to 13. What should you do next, and what does this tell you about the value of a test set?

### Key takeaways

- A useful AI system is a model plus inputs, checks, and output. The model is one part.
- **Grounding** puts the facts in the prompt; **retrieval** finds the right facts when the documents are large.
- **Structured output** lets your program use the answer reliably, and rule checks catch malformed replies.
- **Hallucination** is confident invention. Grounding and checks reduce it, but it cannot be fully prevented.
- A small **test set** lets you measure whether a change really improves the system.
- Cost and privacy depend on how much text you send and where it goes, so plan both before you build.