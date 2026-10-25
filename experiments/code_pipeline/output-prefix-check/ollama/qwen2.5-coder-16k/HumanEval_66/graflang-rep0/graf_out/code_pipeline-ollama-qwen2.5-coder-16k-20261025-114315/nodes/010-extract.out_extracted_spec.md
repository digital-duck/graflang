### Specification for `uppercaseAsciiSum(s)`

#### 1. Purpose:
The function `uppercaseAsciiSum(s)` is designed to calculate the sum of the ASCII values of all uppercase characters in a given string `s`.

#### 2. Inputs:
- **Parameters**:
  - `s`: A string (`str`)
- **Constraints**:
  - `s` can be empty (`""`).
  - `s` can contain any printable ASCII characters, including letters, digits, punctuation, and whitespace.

#### 3. Outputs:
- **Return Value**: An integer (`int`) representing the sum of the ASCII values of all uppercase characters in the string `s`.

#### 4. Behaviour:
- **Algorithm**:
  - The function iterates through each character `c` in the string `s`.
  - For each character `c`, it checks if the character is an uppercase letter using the `isupper()` method.
  - If the character is uppercase, its ASCII value (obtained using the `ord()` function) is added to a running total.
  - After iterating through all characters, the function returns the total sum of the ASCII values of the uppercase characters.
  
- **Edge Cases and Error Conditions**:
  - If the string `s` is empty, the function returns 0.
  - The function handles strings containing a mix of uppercase and lowercase letters, digits, punctuation, and whitespace. Only uppercase letters contribute to the sum.
  - The function assumes no errors will occur due to invalid input types or formats.

#### 5. Assumptions:
- The input string `s` will always be a valid Python string, including empty strings.
- The function will only consider uppercase ASCII characters for the sum calculation.
- The function assumes that the input string does not contain non-ASCII characters that could cause issues with `ord()` or `isupper()` methods.