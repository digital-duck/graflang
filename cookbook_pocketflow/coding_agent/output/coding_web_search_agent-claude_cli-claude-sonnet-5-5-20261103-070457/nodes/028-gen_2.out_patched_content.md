def two_sum(nums, target):
    """Find two numbers in nums that sum to target; return their indices."""
    seen = {}
    for i, n in enumerate(nums):
        complement = target - n
        if complement in seen:
            return [seen[complement], i]
        seen[n] = i
    return []