You are a skilled technical writer. Write one chapter of a concept book.

Subject: {{in_subject}}
Audience: {{in_audience}}
Style of explanation: {{in_style}}

The audience is one of four levels (if the value given is none of these words, read it as a description of the learner and pick the closest level):
- intro: no background in the field. Define every term at its first use. Put an everyday analogy or a concrete example before any formalism. No maths beyond arithmetic and no more than a few lines of code. Short paragraphs.
- intermediate: knows the basics and does not need them defined. Use worked examples, some maths and code, connect ideas across topics, and name the usual pitfalls.
- advanced: a practitioner. Use precise terminology, state assumptions, conditions, failure modes and trade-offs, and include derivations or non-trivial code where they teach something.
- research: works at or near the frontier, with graduate-level background. Give formal definitions and claims together with their conditions, compare competing approaches and the quality of the evidence, say what is not yet known or is contested, and point to primary work by name only when you are sure it exists; otherwise describe the line of work without a citation.

Book outline:
{{in_outline}}

Write chapter {{in_chapter_number}} of {{in_num_chapters}}: the chapter the outline heads "Chapter {{in_chapter_number}}". Cover that chapter's key concepts and learning objectives, and only those. Do not write any other chapter, and do not repeat material that belongs to the other chapters. Write for this audience, in this style, throughout.

Give the chapter this shape, adapting the headings to the style:
- the heading exactly as the outline gives it ("## Chapter {{in_chapter_number}}: <title from the outline>"), then a short opening that says why the chapter matters to this reader
- the ideas, one section each, with at least one worked example
- the usual mistakes or misconceptions (for the research audience: the open questions and disagreements instead)
- three or four questions for the reader to check their own understanding
- key takeaways

Reply with the chapter text only: no preamble, no closing questions or offers.
