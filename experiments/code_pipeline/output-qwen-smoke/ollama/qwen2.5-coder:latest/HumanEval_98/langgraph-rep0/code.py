def count_upper_vowels_at_even_indices(input_string):
    if not isinstance(input_string, str):
        raise ValueError("Input must be a string")
    
    uppercase_vowels = 'AEIOU'
    return sum(1 for i, char in enumerate(input_string) if i % 2 == 0 and char in uppercase_vowels)