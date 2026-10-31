import unittest

from palindrome import is_palindrome


class IsPalindromeTests(unittest.TestCase):
    def test_classic_phrase_with_punctuation_and_case(self):
        self.assertTrue(is_palindrome("A man, a plan, a canal: Panama"))

    def test_simple_word(self):
        self.assertTrue(is_palindrome("racecar"))

    def test_mixed_case_word(self):
        self.assertTrue(is_palindrome("RaceCar"))

    def test_not_a_palindrome(self):
        self.assertFalse(is_palindrome("race a car"))

    def test_digits(self):
        self.assertTrue(is_palindrome("12321"))
        self.assertFalse(is_palindrome("12345"))

    def test_ignores_spaces_case_and_punctuation(self):
        self.assertTrue(is_palindrome("Was it a car or a cat I saw?"))

    def test_differs_only_in_punctuation(self):
        self.assertTrue(is_palindrome("No 'x' in Nixon"))
        self.assertTrue(is_palindrome("ab-ba"))
        self.assertFalse(is_palindrome("ab-bc"))

    def test_empty_string(self):
        self.assertTrue(is_palindrome(""))

    def test_no_letters_or_digits(self):
        self.assertTrue(is_palindrome(" .,!? "))

    def test_single_character(self):
        self.assertTrue(is_palindrome("a"))

    def test_even_length_palindromes(self):
        self.assertTrue(is_palindrome("abba"))
        self.assertTrue(is_palindrome("noon"))
        self.assertFalse(is_palindrome("abab"))

    def test_mixed_letters_and_digits(self):
        self.assertTrue(is_palindrome("1a1"))
        self.assertTrue(is_palindrome("a1 1a"))
        self.assertFalse(is_palindrome("1a2"))

    def test_combining_mark_is_ignored_after_nfc(self):
        # "e" + combining acute + "e": after NFC the accent is part of a
        # composed character, which is not ASCII, so it is skipped.
        self.assertTrue(is_palindrome("e\u0301e"))
        # Composed and decomposed forms of the same text behave the same.
        self.assertEqual(
            is_palindrome("\u00e9ab"),
            is_palindrome("e\u0301ab"),
        )

    def test_non_ascii_letters_are_ignored(self):
        self.assertTrue(is_palindrome("\u00e9a\u00e9"))  # "éaé"
        self.assertFalse(is_palindrome("\u00e9ab"))  # "éab" -> "ab"
        self.assertFalse(is_palindrome("ab\u00e9c"))  # "abc"

    def test_numeric_symbols_are_ignored(self):
        self.assertTrue(is_palindrome("1\u00b2 1"))  # "1² 1" -> "11"
        self.assertFalse(is_palindrome("1\u00bd2"))  # "1½2" -> "12"

    def test_non_palindrome_differing_only_in_case_folded_characters(self):
        self.assertFalse(is_palindrome("Ab"))
        self.assertTrue(is_palindrome("Aa"))

    def test_non_string_input_raises_type_error(self):
        with self.assertRaises(TypeError):
            is_palindrome(None)
        with self.assertRaises(TypeError):
            is_palindrome(123)


if __name__ == "__main__":
    unittest.main()
