REVISION_NEEDED
1. **Audience mismatch: the chapter is too heavy for intro.** Several terms are used before they are defined or without definition: "token" (used in Cost, speed, and privacy with no definition: "roughly per word or word fragment" comes too late and is never tied to the word), "retrieval" is introduced by name before it is defined in context, "JSON" is used in the Structured output section before any explanation, and "third-party model service" and "provider" are not explained. Define each at first use.

2. **Code blocks exceed the intro limit.** The `retrieve` function is a tight, dense definition using `sorted`, `lambda`, set intersection, and slicing. For intro, either remove it or replace it with a plain-language walkthrough (e.g. "count how many words each passage shares with the question, pick the top two") and at most a few lines. The `json.loads` example is acceptable but should be introduced with a plain analogy (a labelled form) before the code.

3. **Maths beyond the intro limit.** The budget calculation ("1,500 tokens … 1,700,000 tokens … multiply by price per thousand") is arithmetic, which is allowed, but it assumes the reader knows what a token costs. Walk through it with a concrete dollar figure or a worked step-by-step example so the reader can follow the multiplication.

4. **Missing everyday analogies before formalism.** "Structured output," "rule checks," "review checks," and "hallucination" each open with a definition or a formal description. Add a concrete everyday example before each formal term (e.g. a form with boxes to tick versus a free-text note; a spell-checker versus a human proofreader).

5. **Style is not consistently conversational.** Some paragraphs are dense and listy ("Input / Model / Checks / Output" bullets, the "Common mistakes" bullets). Keep the bullet structure but add a sentence of plain explanation under each so the chapter reads as a conversation, not a reference card.

6. **Table in "Evaluating the system" is a formalism-first device.** Introduce the idea of "a list of questions with known answers" as an everyday analogy (like a quiz you write before a driving test) before showing the table.

7. **Check-your-understanding question 2 asks for two reasons, but the chapter does not explicitly state the accuracy reason.** The chapter says retrieval "may miss the important lines in the middle," which is a reason about accuracy, but it is not framed as one. Make it explicit so the question can be answered from the text.

8. **Completeness: the chapter does not explain what a "passage" is or how a document is split.** Section 1 of the project says "split the documents into passages, one per section," but no example of splitting is given. Add a single concrete example (e.g. a manual's "Setup" and "Troubleshooting" headings becoming two passages).

9. **Accuracy: "Pricing is usually per token, roughly per word or word fragment" is imprecise.** Tokens are not reliably "words or fragments" in a way an intro reader can use; say "a token is a small chunk of text, often a short word or part of a long one, and a common rule of thumb is about three-quarters of a word per token" or similar, and mark it as an approximate rule of thumb.

10. **Accuracy: the claim that "the model is trained to produce likely continuations of text" is a simplification presented as a full explanation.** It is acceptable for intro, but flag that it is a simplification so the reader does not take it as the whole story.

11. **Heading and scope are correct.** The heading is "Chapter 2: Building a Useful System Around a Model" and the content is about that topic; no change needed there.