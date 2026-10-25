def count_upper(s):
    uppercase_vowels = {'A', 'E', 'I', 'O', 'U'}
    return sum(1 for i in range(0, len(s), 2) if s[i] in uppercase_vowels)