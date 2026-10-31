## Chapter 1: What Applied AI Is, and How a Model Turns Input into Output

Key concepts to cover:
- Applied AI defined: using AI models to solve a real problem, as opposed to researching new models. A spam filter, a voice assistant, and a product-recommendation list are everyday examples.
- What a model is, in plain terms: a function that takes an input (text, an image, a number) and produces an output (a label, a sentence, a score). Analogy: a well-trained sorting clerk who has seen millions of examples and now makes quick judgements.
- Training versus inference: learning from examples happens once (training); using the learned model happens every time someone asks (inference). Analogy: studying for an exam versus sitting it.
- Learning from examples: showing a model labelled data (emails marked "spam" or "not spam") and adjusting it until its guesses improve. Keep this concrete, with no formulas beyond counting correct answers.
- Predictions are guesses, not facts: models output probabilities and can be confidently wrong. Example: a photo classifier calling a muffin a chihuahua.
- Large language models (LLMs) at a high level: a model that predicts the next word in a sentence, trained on huge amounts of text, which is why it can answer questions and write summaries.
- Prompts: the instructions and context you give a language model. Show a short before-and-after example, such as a vague request versus a clear one, and why the clear one gets a better result.
- A first working example: calling a language model from a few lines of Python to summarise a paragraph (a short snippet, no more than a few lines).
- Common misconceptions: AI "understands" the way people do; a model "knows" facts it was never shown; more data always helps.

After this chapter the reader can:
- Explain in their own words what applied AI is and give two examples from daily life.
- Describe the difference between training a model and using a trained model.
- Explain why a model's output is a prediction that can be wrong, and give an example.
- Write a clear prompt for a simple task and explain why it works better than a vague one.
- Run a short script that sends text to a language model and reads back the answer.

## Chapter 2: Building a Useful System Around a Model

Key concepts to cover:
- From a single model call to a system: the model is one component among data input, checks, and output. Analogy: a kitchen, where the model is the cook but ingredients, recipes, and taste-testing matter too.
- Grounding: giving the model the facts it needs at the moment of the question, so it does not rely on memory alone. Example: pasting a company's refund policy into the prompt before asking a customer question.
- Retrieval in plain terms: searching your own documents for the relevant passages and including them in the prompt. Include a simple walkthrough, such as answering questions about a 10-page manual.
- Structured output: asking for answers in a fixed format (for example, JSON with named fields) so the rest of the program can use them reliably.
- Checking the output: simple tests, such as confirming a required field is present, and a second review step where the model or a person checks the first answer.
- Hallucination: confident invented answers. Explain why it happens, how grounding and checks reduce it, and why it is never fully eliminated.
- Evaluating a system: building a small set of test questions with known good answers, and measuring how often the system gets them right before and after a change.
- Cost, speed, and privacy basics: each call costs money and time; sending personal data to a third-party service needs thought. Keep this practical, with a simple budgeting example.
- A complete small project: a question-answering tool over a few documents, with retrieval, a structured answer, and a basic test.

After this chapter the reader can:
- Describe the parts of an AI system beyond the model and say what each one does.
- Explain grounding and retrieval, and use them to answer questions from a document they supply.
- Ask a model for structured output and check that the output is valid.
- Recognise hallucination, explain why checks reduce it, and say why it cannot be fully prevented.
- Build a small set of test questions and use it to compare two versions of a system.