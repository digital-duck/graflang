def digitSum(s: str) -> int:
    """Task
    Write a function that takes a string as input and returns the sum of the upper characters only
    ASCII codes.

    Parameters:
    s (str): The input string from which the sum of ASCII values of upper-case characters will be calculated.

    Returns:
    int: The sum of ASCII values of the upper-case characters in the input string.

    Raises:
    TypeError: If the input is not a string.

    Examples:
    digitSum("") => 0
    digitSum("abAB") => 131
    digitSum("abcCd") => 67
    digitSum("helloE") => 69
    digitSum("woArBld") => 131
    digitSum("aAaaaXa") => 153
    """
    if not isinstance(s, str):
        raise TypeError("Input must be a string")
    return sum(ord(char) for char in s if char.isupper())