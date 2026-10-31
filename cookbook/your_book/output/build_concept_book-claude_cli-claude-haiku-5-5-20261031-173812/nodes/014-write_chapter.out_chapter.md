## Chapter 3: Context, Retrieval, and Knowledge

A model knows only two things when it answers you: what it learned during training, and what you put in front of it at the moment of the request. Training gives it broad general knowledge, but that knowledge is frozen at a cutoff date, incomplete for your domain, and silent about your private documents. Everything else must arrive through the context. This chapter is about deciding what goes into that context, and how to fetch the right material when the model cannot hold everything at once.

### Context windows and their limits

The context window is the total amount of text a model can read in a single call: your instructions, the conversation so far, any documents you attach, and the space reserved for the answer. It is measured in tokens, the sub-word units a model processes, where a token is roughly three-quarters of an English word. Windows have grown large, but a larger window does not remove the need for judgment, for three reasons.

- **Cost and latency scale with input.** Every token you send is billed and adds time before the first word of the answer appears.
- **Attention is uneven.** Models tend to use material near the beginning and end of a long input more reliably than material buried in the middle. A fact on page 300 of a 400-page dump may simply be missed.
- **Noise competes with signal.** Irrelevant passages do not sit harmlessly in the background. They can pull the answer toward themselves, or lead the model to blend two sources that disagree.

The practical question is therefore not "will it fit?" but "what does this specific question need?" Include the material that bears on the answer, leave out what does not, and state the question clearly so the model knows what to look for. Put stable instructions first, then the evidence, then the question. If you cannot say why a passage is in the window, that passage probably should not be there.

### Embeddings and semantic similarity

Keyword search finds documents that contain the words you typed. It fails when the author used different words: a query for "reducing downtime" misses a document about "improving availability." An **embedding** addresses this. It is a function that maps a piece of text to a vector of numbers, typically a few hundred to a few thousand dimensions, such that texts with similar meaning land close together in that space.

Closeness is usually measured by cosine similarity, the angle between two vectors. Two passages about the same idea point in nearly the same direction, even when they share no vocabulary. This is what makes **semantic search** possible: embed every chunk of your corpus once, embed the query at search time, and return the chunks whose vectors are nearest to the query's.

Embeddings have limits you should respect:

- They capture topical similarity well and specific facts poorly. A query about "the 2024 contract" and a passage about "the 2025 contract" may score very similarly.
- Different embedding models produce incompatible spaces. Vectors from one model cannot be compared with vectors from another, so changing the model means re-indexing everything.
- Negation and qualifiers are often weakly represented. "Services that do not require login" can retrieve passages about login.

Treat embedding similarity as a ranking signal, not a proof of relevance. Its job is to shortlist candidates cheaply; judging whether a candidate actually answers the question is a separate step.

### Retrieval-augmented generation (RAG)

Retrieval-augmented generation is the pattern that connects a model to your knowledge. Instead of asking the model to remember your documents, you retrieve the relevant parts at question time and place them in the context with an instruction to answer from them. A basic pipeline has four stages:

1. **Chunking.** Split documents into pieces small enough to be specific and large enough to be self-contained. A chunk that reads "It increased by 12 percent" is useless without the sentence naming the subject. Common strategies split on headings or paragraphs, with a modest overlap so that ideas spanning a boundary are not severed. Chunks of a few hundred tokens are a reasonable starting point, but the right size depends on the document type, and you should test it.
2. **Indexing.** Compute an embedding for each chunk and store it, along with metadata such as source, section, date, and version. The metadata matters later: it is what lets you filter, cite, and expire content.
3. **Retrieval.** At question time, embed the query and fetch the top-k most similar chunks. Many systems combine this with keyword search, since exact identifiers such as product codes or error messages are often better matched lexically.
4. **Grounding.** Assemble the retrieved chunks into the prompt with explicit labels, and instruct the model to answer only from them, to say when they do not contain the answer, and to cite the chunk each claim comes from.

Each stage can fail independently. A pipeline that answers poorly is usually failing at one identifiable stage, which is why it helps to log what was retrieved, not only what was answered.

### Retrieval quality: precision, recall, and reranking

Retrieval is an information-retrieval problem with well-understood metrics, and borrowing them makes debugging concrete.

- **Precision** asks what fraction of the retrieved chunks were actually relevant. Low precision means the model is handed noise.
- **Recall** asks what fraction of all relevant chunks were retrieved. Low recall means the answer exists in your corpus but never reached the model.

The two trade off against each other through k. Retrieving more chunks raises recall and usually lowers precision. Retrieving fewer does the opposite.

A common and effective remedy is **reranking**. First retrieve a generous candidate set, say twenty or fifty chunks, using the cheap embedding search. Then pass the query and each candidate to a more accurate scorer, often a cross-encoder model that reads the pair together, and keep only the best few. The expensive scorer runs on a small set, so the cost stays manageable while precision improves substantially.

When answers are poor, diagnose before you tune:

- If the right chunk is absent from the retrieved set, recall is the problem: adjust chunking, increase k, or add keyword search.
- If the right chunk is present but ranked low or buried among distractors, precision or ranking is the problem: add reranking or tighten the filters.
- If the right chunk is present and prominent but the answer is still wrong, the problem is generation: the instructions, the ordering, or the model's handling of conflicting passages.

Build a small set of questions with known source passages so that you can measure these separately. Without that, retrieval tuning becomes guesswork.

### Citing sources and reducing hallucination through grounding

A model asked a question it cannot answer from its context will often produce a fluent answer anyway. Grounding reduces this tendency by making the evidence explicit and the expected behavior explicit.

Several practices help:

- **Label each chunk** with an identifier and its source, so the model can refer to it.
- **Require citations** in a fixed format, such as a bracketed identifier after each claim, and reject answers whose citations do not match a retrieved chunk.
- **Permit abstention.** Instruct the model to reply that the sources do not say, rather than guess. Without this permission, the model is pushed toward answering.
- **Separate claims from quotations.** Where exact wording matters, ask for a short verbatim quote alongside the paraphrase, which makes checking faster.

Citation does not guarantee faithfulness. A model can cite a real chunk and still misstate what it says. Verifying that a cited claim is supported by its source is an evaluation task, covered in the chapter on evaluation and safety, but the design that makes verification possible starts here: keep the chunk identifiers and the claims linked.

### Keeping knowledge current: updating indexes and handling stale data

An index is a snapshot. The moment a policy changes or a product is discontinued, the index begins to mislead. Keeping it current is an engineering responsibility, not a one-time task.

- **Incremental updates.** Re-embed only changed or new documents, identified by content hash or modification time, rather than rebuilding the whole index.
- **Deletions.** Removing a source must remove its chunks. Orphaned chunks are a common source of answers that cite withdrawn material.
- **Versioning.** Record which embedding model and chunking configuration produced each index. When either changes, the whole index must be rebuilt, because vectors from different configurations are not comparable.
- **Freshness in the answer.** Store dates in the metadata and, where age matters, surface them to the model and the user. An answer based on a three-year-old price list should say so.
- **Priority over retrieval.** When a question concerns something that changes often, prefer a live source, such as an API or a database query, over a static index. RAG is strongest for relatively stable bodies of text. For fast-moving facts, the retrieval step can call a tool instead, which is the subject of the next chapter.

Stale data is rarely noticed by the people who built the system and frequently noticed by the people who use it. Schedule a review of the index contents, not only of the code that populates it.

### Summary

The model's answers are shaped less by its general knowledge than by what you place in front of it. Context windows bound how much you can include and reward careful selection. Embeddings let you find passages by meaning. A RAG pipeline turns those capabilities into a chain of chunking, indexing, retrieval, and grounding, each of which can be measured and repaired independently. Grounding and citation make answers checkable, and index maintenance keeps them true over time. The next chapter turns from what the model reads to what it can do: calling tools, taking steps, and coordinating several of them.