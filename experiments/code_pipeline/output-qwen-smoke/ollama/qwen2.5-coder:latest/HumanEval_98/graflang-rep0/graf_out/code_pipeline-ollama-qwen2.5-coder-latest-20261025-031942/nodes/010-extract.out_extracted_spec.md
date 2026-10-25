### Specification

#### Purpose
The purpose of this function is to count the number of uppercase vowels located at even indices within a given string.

#### Inputs
1. **s (string)**: The input string upon which the function operates. The string must not be empty and must contain only alphabetic characters.

#### Outputs
The function returns an integer value representing the count of uppercase vowels found at even indices in the input string.

#### Behaviour
1. The function iterates over the input string `s`, examining only the characters at even indices (0, 2, 4, ...).
2. For each character at an even index, it checks if the character is an uppercase vowel (i.e., 'A', 'E', 'I', 'O', 'U').
3. If the character is an uppercase vowel, the count is incremented by one.
4. The function returns the total count of uppercase vowels found at even indices.

#### Edge Cases
- If the input string `s` is empty, the function should return 0, as there are no characters to check.
- If there are no uppercase vowels at even indices, the function should return 0.

#### Assumptions
- The input string `s` consists solely of alphabetic characters.
- The indices of characters in the string are zero-based, meaning the first character is at index 0, the second at index 1, and so on.
- The function assumes that the input string is correctly formatted and does not contain any non-alphabetic characters.