# Prompt: coder [call 001]

- model: `qwen2.5-coder-16k`
- max_tokens: 2048
- temperature: 0.7

---


You are an expert python developer.

Write clean, correct, well-structured python code for the following specification.
Return only the code — no explanation, no markdown fences.

Specification:
Implement the following Python function. Return the complete function, including its signature and any imports it needs.


def digitSum(s):
    """Task
    Write a function that takes a string as input and returns the sum of the upper characters only'
    ASCII codes.

    Examples:
        digitSum("") => 0
        digitSum("abAB") => 131
        digitSum("abcCd") => 67
        digitSum("helloE") => 69
        digitSum("woArBld") => 131
        digitSum("aAaaaXa") => 153
    """

Previous attempt (empty on the first attempt):


Its test result (empty on the first attempt):


If there is a previous attempt, fix the failures its test result reports. Whatever you write, keep the function name and
the signature exactly as the specification gives them.
