REVISION_NEEDED

1. **Add a prompt-injection paragraph.** The chapter stresses user-supplied context but never says that such text can contain instructions the model may follow. The only related sentence says delimiters make this "harder." Add a short section covering untrusted input: delimiters reduce the risk but do not remove it, the model should be told to treat tagged content as data, the model should have no more tools or permissions than the task needs, and outputs should be validated before use.

2. **Fix the label mismatch in the strong prompt.** The prompt asks for one of `positive`, `negative`, or `mixed`, then says to return `unclear`, which is a fourth label. Either list all four labels in the instruction or say that `unclear` is a fallback outside the three sentiment labels.

3. **Correct the few-shot example.** The pair described ("a review that praises the product but complains about shipping" and "a neutral review") does not clearly teach "mixed." A neutral review is also close to `unclear`, so the example confuses two boundaries. Use a mixed review and a clearly positive or clearly negative one, or show the mixed case against an `unclear` case, and say which boundary each example teaches.

4. **Soften unsupported general claims.**
   - "Three failure modes account for most prompt problems" is asserted without evidence. Say "three common failure modes" or drop "most."
   - "Moving critical constraints to the end (where they are more salient)" is stated as fact. Present it as a heuristic to test on your own prompts.

5. **Qualify the schema-enforcement example.** The claim that enforcement may skip `maxLength` depends on the provider. Write "some providers do not enforce every keyword, such as `maxLength`" so readers do not take it as a rule about all APIs.

6. **Check cross-references.** "Chapter 3" (grounding) and "Chapter 5" (building an evaluation set) must match the book's actual contents. I could not verify them from this text alone.