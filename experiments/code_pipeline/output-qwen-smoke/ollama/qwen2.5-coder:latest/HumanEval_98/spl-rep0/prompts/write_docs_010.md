# Prompt: write_docs [call 010]

- model: `qwen2.5-coder:latest`
- max_tokens: 2048
- temperature: 0.7

---


You are a technical writer generating developer documentation for python code.

Original specification:
Implement the following Python function. Return the complete function, including its signature and any imports it needs.


def count_upper(s):
    """
    Given a string s, count the number of uppercase vowels in even indices.
    
    For example:
    count_upper('aBCdEf') returns 1
    count_upper('abcdefg') returns 0
    count_upper('dBBE') returns 0
    """

Implemented python code:
def count_upper(s):
    """
    Given a string s, count the number of uppercase vowels in even indices.
    
    For example:
    count_upper('aBCdEf') returns 1
    count_upper('abcdefg') returns 0
    count_upper('dBBE') returns 0
    """
    vowels = 'AEIOU'
    count = 0
    for i in range(0, len(s), 2):
        if i % 2 == 0 and s[i] in vowels:
            count += 1
    return count

Write clear, complete documentation in Markdown. Include:

## Overview
One paragraph describing what this code does and why.

## Function / Class Reference
For each public function or class: signature, description, parameters, return value, example usage.

## Edge Cases & Assumptions
Any notable constraints, limitations, or assumptions the implementation makes.

## Usage Example
A short, runnable python example demonstrating typical use.

Be concise and accurate. Do not pad with filler.
