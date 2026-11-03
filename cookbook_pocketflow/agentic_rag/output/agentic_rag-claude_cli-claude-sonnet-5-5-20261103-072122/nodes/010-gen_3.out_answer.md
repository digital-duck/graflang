The context you gave me doesn't define retrieval-augmented generation (RAG) or say when to use it. The project notes don't mention it by name. Below is a general-knowledge answer, which goes beyond the provided context, followed by the one place the repo does something similar.

## What RAG is

RAG gives an LLM relevant information at query time instead of relying only on what it learned in training. The usual flow:

1. **Index**: split your documents into chunks and store them, typically as embeddings, with keyword search (e.g. BM25) as an option.
2. **Retrieve**: for a user query, find the most relevant chunks.
3. **Augment**: put those chunks into the prompt.
4. **Generate**: the model answers using the retrieved text.

## When to use it

- **Private or domain-specific knowledge** that the model wasn't trained on, such as internal docs, codebases, or tickets.
- **Fresh or changing data**, since you update the index rather than retrain the model.
- **Large corpora** that don't fit in the context window.
- **Traceable answers**, because you can cite which chunks were used.
- **Reducing hallucination** on factual questions, by grounding answers in retrieved text.

## When not to use it

- The whole corpus fits comfortably in the context window. Just include it.
- The task is about style, format, or behavior rather than knowledge. Prompting or fine-tuning fits better.
- The answer needs reasoning across the entire corpus (e.g. "summarize everything"). Retrieval of a few chunks can miss the picture.
- Retrieval quality will be poor, for example with very small or unstructured data. Bad retrieval gives confidently wrong answers.

## Related pieces in this repo

The project notes describe a RAG-like pattern in the Create feature. `graf create` finds similar recipes using `graphlang/recipe_index.py` and `embedding.py` (meaning via dd-embed plus BM25, one entry per recipe) and puts them into the LLM prompt as examples (`find_examples`). That is retrieval followed by augmented generation. The `QUERY` node, which reads a file confined to the graph's folder, could also feed retrieved text into a `GENERATE` node. Whether a dedicated retrieval node type exists, I can't say from this context.

If you want to build RAG as a GraphLang workflow, tell me and I'll check the code for how best to wire it.