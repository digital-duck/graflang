## Chapter 2: Building a Useful System Around a Model

A model on its own is a clever guesser. Ask it a question and it answers from whatever it picked up during training. That knowledge may be out of date, incomplete, or simply not about your business. Most useful AI products are therefore not "a model" alone. They are a model wrapped in a few extra parts that supply the right information, shape the answer, and check the result. This chapter shows you those parts. By the end, you will be able to build a small question-answering tool over your own documents, and you will know how to tell whether it is working.

### From one call to a system

Think of a kitchen. The cook matters, but a restaurant meal also depends on the ingredients, the recipe, and a taste test before the plate leaves the kitchen. If the ingredients are poor, even a skilled cook makes a poor dish.

An AI system has the same shape:

- **Input**: the question, plus any data the system gathers to answer it. Think of this as the ingredients.
- **Model**: the component that reads the prompt (the instructions and context you give it) and writes an answer. This is the cook.
- **Checks**: code or a second review that inspects the answer before anyone sees it. This is the taste test.
- **Output**: the answer, delivered in a form the rest of the software can use.

When people say a system "works," they usually mean all four parts work together. A better model rarely fixes a poor supply of ingredients or a missing taste test.

### Grounding: give the model the facts

Suppose a customer asks, "Can I return a sale item after 30 days?" If you send only the question, the model falls back on general knowledge about returns. It may sound confident and still be wrong about your shop.

**Grounding** means putting the relevant facts into the prompt at the moment of the question. It is like handing a new shop assistant the returns policy card before they answer the phone. For example:

> Use only the policy below to answer the customer.
>
> Policy: Sale items may be returned within 14 days with a receipt. Final-sale items cannot be returned.
>
> Question: Can I return a sale item after 30 days?

Now the model has something specific to work from. It can answer "No, sale items are accepted for return only within 14 days," because the answer is in the text in front of it. It is no longer relying on memory alone.

### Retrieval: finding the right facts

Grounding is easy when the facts are short, like one policy card. Real documents are longer. Suppose you have a 10-page product manual and a user asks, "How do I reset the device?"

You could paste all 10 pages into every prompt, but that is slow and costly, and the model may miss the important lines buried in the middle. **Retrieval** solves this by finding only the useful parts. It works in three steps:

1. **Split** the manual into **passages**, which are chunks of text small enough to hand over in one go. A natural split is one passage per section. For example, a manual's "Setup" heading and its text become one passage, and its "Troubleshooting" heading and text become another.
2. **Search** the passages for the ones most related to the question. The simplest method counts shared words. A question about resetting shares the word "reset" with the "Troubleshooting" passage and not with the "Setup" passage, so troubleshooting scores higher. More advanced systems compare meanings, but the goal is the same: find the few passages that matter.
3. **Include** only those passages in the prompt, along with the question.

Here is the word-counting idea in plain terms. For each passage, count how many words it shares with the question. Keep the two passages with the highest counts. Those are the ones you send to the model. A few lines of code can do this, but the idea is the important part.

For a question about resetting, this might pick the "Resetting the device" and "Troubleshooting" sections. The model then answers from those two passages. Retrieval plus grounding is the core pattern behind most document question-answering tools.

### Structured output: answers the program can use

A person reads a paragraph and understands it. A program needs fields it can check and store. Imagine a paper form with labelled boxes: "Name," "Date," "Category." Each box holds one kind of answer, and a clerk can file the form without guessing. A free-text note, by contrast, might say anything in any order.

**Structured output** means asking the model to fill in a form like that. The usual format is **JSON**, a plain-text way of writing labelled fields, with names in quotes and values after a colon. If your system records a ticket's priority, a free-text reply might say "This looks urgent," but you need the word `high` so your code can act on it.

> Answer the question using the passages. Reply only with JSON in this form:
> `{"answer": text, "source_section": text, "confident": true or false}`

Your code can then read the labelled boxes like any other data:

```python
import json

reply = '{"answer": "Hold the power button for 10 seconds.", "source_section": "Resetting the device", "confident": true}'
data = json.loads(reply)  # turns the text into a labelled form
print(data["answer"])     # prints: Hold the power button for 10 seconds.
```

Models do not always follow the format, so the next section matters.

### Checking the output

Checks are the taste test. There are two kinds.

- **Rule checks** are code that tests the output against simple rules, a bit like a spell-checker. Does the reply parse as JSON? Is the `answer` box filled in? Is `source_section` one of the section names you supplied? If a check fails, the system can retry or flag the question for a person.
- **Review checks** are a second reader. A second model call, or a person, reads the first answer next to the passages and asks, "Is this answer supported by the text?" It is like a human proofreader who understands the meaning, not just the spelling. It is slower and costs more, so it is often kept for high-stakes answers.

Checks do not make the model right. They make wrong answers easier to notice and stop malformed ones from reaching your program.

### Hallucination: confident inventions

A **hallucination** is an answer that sounds fluent and certain but is not supported by the facts. Imagine a student who has not read the chapter but writes a confident essay anyway, using phrases that sound like the subject. That is roughly what happens when a model is asked something the supplied text does not cover. It produces a plausible reply from patterns it learned, not from your documents.

Why does this happen? A simplified picture helps here. The model is trained to produce likely continuations of text, so a likely-sounding answer comes easily. This is a simplification, not the whole story, but the key point holds: a likely-sounding answer is not the same as a true one. The model has no built-in step that says "I checked this against a source."

Grounding and retrieval reduce hallucination because they give the model a source to copy from. A required `source_section` field and a rule check that the section exists reduce it further. Yet none of these eliminate it. The model can still misread a passage, combine two passages wrongly, or invent a detail the passage does not contain. Treat hallucination as a rate to measure and manage, not a bug you can finally close.

Hallucination is most dangerous when the answer looks authoritative. A system that cites a section and quotes it confidently can still be wrong, which is why the next section matters.

### Evaluating the system

How do you know the system is good? Think of a quiz you write before a driving test. You know the right answers because you wrote them from the official handbook, and you use the quiz to see how well you, or the system, have learned the material. In this case, the test set is a list of questions, each paired with a known good answer taken from your documents. Twenty questions is a reasonable start.

Here is a small example:

| Question | Expected answer |
|---|---|
| How do I reset the device? | Hold the power button for 10 seconds. |
| What is the warranty period? | Two years from the purchase date. |
| Can I use the charger abroad? | Yes, with a plug adapter. |

Run the system on every question and count how many answers match. Then change something, such as a better search, a new prompt, or a different model, and run the same questions again. If the score rises, the change helped on this set. If it falls, undo it.

A test set has limits. Twenty questions cannot cover everything users will ask, and matching is hard to judge when answers are worded differently. Start with a small, honest set and grow it as you find failures.

### Cost, speed, and privacy

Every model call costs money and takes time. Providers, the companies that run model services, usually charge by the **token**. A token is a small chunk of text, often a short word or part of a long one. As a rough rule of thumb, one token is about three-quarters of a word, so 100 tokens is roughly 75 words. This is an approximate guide, and exact counts vary by model.

Retrieval helps here. Sending two relevant passages costs far less than sending a whole manual.

Let's work through a budget step by step, using made-up prices. Suppose:

1. Each question sends about 1,500 tokens to the model and gets back about 200.
2. Together, that is 1,700 tokens per question.
3. Your tool handles 1,000 questions a month, so that is 1,700 × 1,000 = 1,700,000 tokens a month.
4. Suppose the provider charges $0.01 per 1,000 tokens. Then 1,700,000 tokens is 1,700 thousands, so the bill is 1,700 × $0.01 = $17 a month.

If you double the passages, the input rises to 3,000 tokens per question and the bill climbs too. Keep retrieval focused.

Privacy needs the same attention. When you send text to a third-party model service, a company outside your own organisation, that text leaves your machine and is governed by that company's terms. Customer names, medical notes, or internal financial figures should not go into a prompt without a decision about whether that service is allowed to see them. Remove or mask personal details where you can, and read what your provider says it does with the data.

### A complete small project

Here is how the pieces combine into a question-answering tool over a few documents:

1. **Load and split** the documents into passages, one per section.
2. **Retrieve** the two or three passages most related to the question.
3. **Ask** the model, with grounding instructions and a required JSON format.
4. **Check** the reply. It must parse, contain a non-empty answer, and name a real source section. If it fails, retry once, then flag it.
5. **Test** with your question set, record the score, and repeat after every change.

Each step is small. The value comes from putting them together and measuring the result.

### Common mistakes

Each of these mistakes is easy to make, so it helps to name them early.

- **Assuming the model knows your documents.** It does not, unless you supply the text. Like a visitor who has never seen your office, it can only describe offices in general.
- **Sending everything.** Long prompts cost more, run slower, and can bury the relevant lines, like a useful note hidden in a thick stack of paper.
- **Trusting format as proof of accuracy.** Valid JSON can still contain a wrong answer. A neatly filled form can hold a wrong entry.
- **Skipping the test set.** Without it, you cannot tell whether a change helped or hurt. You are driving without a speedometer.
- **Believing hallucination can be eliminated.** It can be reduced and detected, not guaranteed away, much like no one proofreader catches every typo.

### Check your understanding

1. In the kitchen analogy, what plays the role of the ingredients in an AI system, and why does a good cook still need good ingredients?
2. Why does retrieving two relevant passages usually beat pasting an entire 10-page manual into the prompt? Give one reason about accuracy and one reason about cost.
3. A model returns valid JSON with a non-empty `answer`, but the answer is wrong. Which check would have caught it, and which kind of check would still miss it?
4. You change your search method and your test score drops from 16 out of 20 to 13. What should you do next, and what does this tell you about the value of a test set?

### Key takeaways

- A useful AI system is a model plus inputs, checks, and output. The model is one part.
- **Grounding** puts the facts in the prompt. **Retrieval** finds the right facts when the documents are large.
- **Structured output** lets your program use the answer reliably, and rule checks catch malformed replies.
- **Hallucination** is confident invention. Grounding and checks reduce it, but it cannot be fully prevented.
- A small **test set** lets you measure whether a change really improves the system.
- Cost and privacy depend on how much text you send and where it goes, so plan both before you build.