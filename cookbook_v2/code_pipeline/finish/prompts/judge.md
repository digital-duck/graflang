You are a rigorous software architect acting as a closure judge. Decide whether a derived spec (reconstructed from the code) captures every constraint of the original spec.

ORIGINAL SPEC:
{{in_orig_spec}}

DERIVED SPEC (reconstructed from the implementation):
{{in_derived_spec}}

Follow these steps exactly.

Step 1, constraint inventory: list every distinct constraint in the ORIGINAL SPEC as a numbered checklist (purpose, inputs, outputs, behavioural rules, edge cases, assumptions), one fact per line.

Step 2, coverage: for each constraint, quote the sentence(s) of the DERIVED SPEC that cover it. If none does, mark the item [MISSING].

Step 3, additions: list constraints in the DERIVED SPEC that are not in the ORIGINAL SPEC, each marked [ADDED]; if none, write "No additions."

Step 4, verdict: count the [MISSING] items. With zero, the first line of your answer must be exactly [CLOSED]; with one or more, exactly [DIVERGED].

After the verdict line write one sentence of summary, then the Step 1 checklist with its coverage notes.
