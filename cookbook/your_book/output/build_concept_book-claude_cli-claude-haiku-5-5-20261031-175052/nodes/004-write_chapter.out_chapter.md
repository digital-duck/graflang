## Chapter 1: What Applied AI Is, and How a Model Turns Input into Output

You use applied AI more often than you might think. When your email quietly moves junk messages out of your inbox, when a voice assistant understands "set a timer for ten minutes," or when a shopping site suggests a kettle after you bought a teapot, something is making a judgement about your data. This chapter explains what is happening in those moments. Once you can see the pattern, you can read a product claim about "AI" and ask sensible questions about it, and you can start building a small tool yourself.

### What applied AI is

*Applied AI* means using AI models to solve a real problem. It is different from *researching* new models, which is what scientists at AI labs spend their time on. An applied AI project starts with a problem, such as "stop spam reaching people's inboxes," and asks whether a model can help solve it.

Three everyday examples:

- **Spam filters** decide whether an incoming email is junk.
- **Voice assistants** turn your speech into text, work out what you wanted, and carry out the request.
- **Recommendation lists** guess which products or videos you are likely to want next.

None of these needs a machine that thinks like a person. Each needs a model that does one job well.

### What a model is, in plain terms

A *model* is a function. That is a fancy word for a machine that takes an input and produces an output:

- Input: an email. Output: "spam" or "not spam."
- Input: a photo. Output: "cat," "dog," or "muffin."
- Input: a sentence. Output: a score from 1 to 5 for how positive it sounds.

Think of a sorting clerk at a post office who has handled millions of letters. Show the clerk an envelope and they glance at the address style, the stamp, and the handwriting, then send it to the right bin in a moment. They are not reasoning from first principles about each letter. They have learned patterns from experience. A model works the same way: it has learned patterns from examples, and it applies them quickly to new inputs.

### Training versus inference

A model's life has two phases.

- **Training** is the learning phase. The model is shown many examples and adjusts itself so its answers improve. This happens once, or occasionally when someone wants to update the model. It can take hours, days, or longer, and it is usually done by the people who build the model.
- **Inference** is the using phase. You give the trained model a new input and it produces an output. This happens every time someone asks a question. It is usually fast, often a fraction of a second.

An exam analogy helps. Studying for an exam is training: you practise, make mistakes, and correct them. Sitting the exam is inference: you apply what you learned to questions you have not seen before. You do not study during the exam, and the learned knowledge is what you carry into it.

### Learning from examples

How does a model improve? Imagine you want a spam filter. You collect 10,000 emails and label each one by hand: "spam" or "not spam." This labelled collection is your *training data*.

The training process goes roughly like this:

1. Show the model an email whose label you know.
2. Let it guess.
3. If the guess is wrong, nudge the model so it is a little more likely to get that email right next time.
4. Repeat for all 10,000 emails, many times over.

To judge progress, you hold back some labelled emails the model has never seen. Its score on those is simply the fraction it gets right. If it classifies 930 of 1,000 unseen emails correctly, its accuracy is 93%. Counting correct answers is the only arithmetic you need to understand the idea.

### Predictions are guesses, not facts

A model does not output the truth. It outputs a *prediction*, often with a confidence score: "spam, 97% sure." That score is a probability estimate, and it can be wrong.

A famous example in the field: a photo classifier shown a picture of a blueberry muffin with chocolate chips may say "chihuahua." The muffin and the dog's face share a pattern of small dark spots on a light background, and the model, having learned from the photos it was shown, can be confidently mistaken. The output looks exactly as authoritative as a correct one, which is why you should treat every model output as a prediction to be checked, especially when the stakes are high.

### Large language models

A *large language model* (LLM) is a model specialised in text. Its core training task is simple to state: given some text, predict the next word. Read the sentence "The capital of France is" and the model is trained to expect "Paris."

That sounds modest, but the training data is enormous: a large share of the written text available online, books, and more. To predict the next word well across all those subjects, the model has to pick up grammar, facts, writing styles, and common patterns of reasoning. This is why an LLM can answer questions, write a summary, or draft an email. It is still predicting words, but it has learned that a good answer to a question is usually a sequence of words that reads like one.

### Prompts: asking well

A *prompt* is the text you send to a language model: the instruction, the context, and any examples you provide. The quality of the prompt strongly affects the quality of the answer.

Compare two requests.

**Vague:**
> Summarise this.

**Clear:**
> Summarise the paragraph below in two sentences for a non-expert reader. Keep the names of people and places. Do not add opinions.
>
> [paragraph]

The vague version leaves the model to guess the length, the audience, and what matters. It may return a single sentence, a long paragraph, or a list of bullet points. The clear version tells the model the length, the reader, what to keep, and what to avoid. The model has less to guess, so its output is more likely to match what you actually wanted. A good habit is to state the task, the audience, the format, and any constraints.

### A first working example

You can ask a language model to summarise text with a few lines of Python. This example uses the Anthropic SDK; you will need an API key set as the environment variable `ANTHROPIC_API_KEY`, and `pip install anthropic`.

```python
import anthropic

client = anthropic.Anthropic()
paragraph = "Applied AI means using models to solve real problems. ..."  # paste any text here

reply = client.messages.create(
    model="claude-haiku-5-5",
    max_tokens=200,
    messages=[{"role": "user", "content":
        "Summarise the paragraph below in two sentences for a non-expert reader.\n\n" + paragraph}],
)
print(reply.content[0].text)
```

Run it. The script sends your text to the model (the request is the *inference* step), then reads back the answer from the response. Every model call costs a small amount of money, so keep your test inputs short while you learn.

### Common misconceptions

**"The AI understands things the way people do."** A model learns statistical patterns from text or images. It can produce answers that look like understanding, and often they are useful, but the mechanism is different from human comprehension. It can fail in ways a person would not, such as confidently answering a question that has a false premise.

**"The model knows facts it was never shown."** A model can only reflect what was in its training data, up to the date that data was collected. It does not look things up unless you connect it to a search tool or a document you supply. If you ask about yesterday's news, a model without that connection may give an old answer or an invented one. You will see how to supply your own facts in Chapter 2.

**"More data always helps."** More data helps when it is relevant, correctly labelled, and varied. Ten thousand carefully labelled emails can beat a million scraped ones with wrong labels. Duplicated or biased data can make a model worse at the cases you care about. Quality and fit to the task matter as much as quantity.

### Check your understanding

1. Give two everyday examples of applied AI that were not in this chapter, and for each say what the model's input and output are.
2. A friend says, "We trained the model last night, so now it's ready to answer customers." Which phase are they describing, and what is the difference between that phase and what happens when a customer asks a question?
3. A model labels a photo of a dog as "cat" with 88% confidence. Why is the confidence figure not proof that the answer is correct?
4. Rewrite this vague prompt so a language model is more likely to give you a useful answer: "Tell me about dogs." Explain which parts of your rewrite help.

### Key takeaways

- Applied AI uses models to solve a specific real problem; it is not the same as inventing new models.
- A model is a function: it takes an input and produces an output, based on patterns learned from examples.
- Training happens once and learns from labelled examples; inference happens every time the model is used.
- Model outputs are predictions with probabilities, and they can be confidently wrong.
- A large language model predicts the next word, which lets it answer questions and write text, but it only knows what it was trained on.
- A clear prompt states the task, audience, format, and constraints, and usually gets a better answer than a vague one.
- Calling a model from code takes only a few lines; the model's answer is a prediction you should check.