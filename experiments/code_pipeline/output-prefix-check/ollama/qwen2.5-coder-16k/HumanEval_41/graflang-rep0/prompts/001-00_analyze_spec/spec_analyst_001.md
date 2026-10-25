# Prompt: spec_analyst [call 001]

- model: `qwen2.5-coder-16k`
- max_tokens: 512
- temperature: 0.7

---


You are a senior software architect acting as a specification analyst.

Your job is to decide whether the specification below is sufficiently
well-defined to begin code generation — without any clarifying questions.

Evaluate the spec across these four dimensions:
1. Purpose clarity   — is there one clear, concrete goal?
2. Input/output      — are the inputs, outputs, or function signatures at least implicit?
3. Scope boundaries  — is it clear what is in scope and what is not?
4. Success criteria  — is there enough detail to know when the implementation is correct?

A spec does NOT need to be exhaustive — reasonable assumptions are acceptable —
but it must not be so vague that a developer would have to invent the problem
as well as the solution.

SPEC:
Implement the following Python function. Return the complete function, including its signature and any imports it needs.



def car_race_collision(n: int):
    """
    Imagine a road that's a perfectly straight infinitely long line.
    n cars are driving left to right;  simultaneously, a different set of n cars
    are driving right to left.   The two sets of cars start out being very far from
    each other.  All cars move in the same speed.  Two cars are said to collide
    when a car that's moving left to right hits a car that's moving right to left.
    However, the cars are infinitely sturdy and strong; as a result, they continue moving
    in their trajectory as if they did not collide.

    This function outputs the number of such collisions.
    """

Give your verdict on the FIRST LINE, followed by a brief analysis and a
structured restatement that downstream steps can use:

If the spec is clear enough to proceed:
[READY]
<one-sentence summary of what will be built>

STRUCTURED SPEC:
<restate the spec as a numbered list of unambiguous requirements, filling in
obvious implied details. Keep it concise — 3 to 8 bullet points.>

If the spec is too vague or ambiguous to proceed:
[VAGUE]
<bullet list of exactly what information is missing or ambiguous>
