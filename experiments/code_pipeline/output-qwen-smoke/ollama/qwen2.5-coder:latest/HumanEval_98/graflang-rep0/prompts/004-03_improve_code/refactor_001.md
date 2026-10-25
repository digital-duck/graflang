# Prompt: refactor [call 001]

- model: `qwen2.5-coder:latest`
- max_tokens: 2048
- temperature: 0.7

---


You are an expert python developer improving code based on feedback.

Original code:
def count_upper(s):
    """
    Given a string s, count the number of uppercase vowels in even indices.
    
    For example:
    count_upper('aBCdEf') returns 1
    count_upper('abcdefg') returns 0
    count_upper('dBBE') returns 0
    """
    uppercase_vowels = {'A', 'E', 'I', 'O', 'U'}
    count = 0
    for i in range(0, len(s), 2):
        if s[i] in uppercase_vowels:
            count += 1
    return count

Review feedback:
- **Logic Error**: The function is intended to count uppercase vowels at even indices but does not check if the character is actually an uppercase vowel. It counts any character that is in the set of uppercase vowels.
- **Edge Case**: The function does not handle empty strings or strings with no uppercase vowels at even indices, which could result in an incorrect count of zero.
- **Poor Naming**: The variable `s` could be more descriptive, such as `input_string`, to indicate its role in the function.

Test failures (if any):


Rewrite the code addressing all feedback and fixing all test failures.
Return only the improved python code — no explanation, no markdown fences.
