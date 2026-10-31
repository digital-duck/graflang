Review of `is_palindrome`:

- **Logic: `isalnum()` is Unicode-aware, so it keeps digits and non-ASCII letters.** That is probably intended, but it is worth confirming. Accented letters, CJK characters, and combining marks (which `isalnum()` may reject, so a decomposed "é" becomes "e" with the accent dropped) can change the result in ways the caller may not expect. Normalize with `unicodedata.normalize("NFKD", s)` or `"NFC"` before filtering if you want consistent behavior.

- **Logic: `str.lower()` is not always a one-to-one mapping.** Some characters change length or map to multiple characters under lowercasing (for example, `"İ".lower()` yields two code points). Use `casefold()` for case-insensitive comparison, which is the standard choice for this kind of matching.

- **Edge cases: empty and whitespace-only input.** `""`, `" "`, and `"!!!"` all return `True`. This is mathematically consistent, but if the function is used for validation, the caller should know that inputs with no alphanumeric content count as palindromes. Document this or handle it explicitly.

- **Robustness: no type checking.** Passing `None` raises `TypeError` from `for ch in s`. Passing a non-string iterable, such as a list of characters, works silently. Consider validating that `s` is a `str`, or annotate and document the expected type.

- **Efficiency: the full list is built and then reversed.** This costs O(n) extra memory and an extra copy. A two-pointer loop over the cleaned characters, or a comparison that stops at the first mismatch, avoids building the copy. This matters only for very large inputs.

- **Clarity: the function name and variable name are fine, but the behavior is not obvious from the signature.** Adding a docstring that states what "palindrome" means here (case-insensitive, ignores non-alphanumeric characters, Unicode-aware) would make the contract explicit. The parameter `s` could be `text` for readability, though that is a minor point.

- **Clarity: `cleaned` is a list, not a string.** The name suggests a string. Either join it (`"".join(...)`) or name it for what it is. Comparing a list to its reverse works, but a string comparison is easier to read.