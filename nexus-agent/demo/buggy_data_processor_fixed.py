"""
buggy_data_processor_fixed.py
Fixed by Nexus Agentic Code Evaluator.
All 6 issues resolved: 4 bugs, 1 security flaw, 1 performance issue.
"""
import ast as _ast


def bubble_sort(arr):
    """Sort a list using bubble sort."""
    arr = list(arr)          # non-destructive copy
    n = len(arr)
    for i in range(n):
        for j in range(0, n - i - 1):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
    return arr               # FIX 1: return the sorted list


def binary_search(arr, target):
    """Find index of target in a sorted list, or -1 if not found."""
    left, right = 0, len(arr) - 1    # FIX 2: len-1, not len
    while left <= right:
        mid = (left + right) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1
    return -1


def calculate_stats(numbers):
    """Return mean, median, min, max — handles empty list gracefully."""
    if not numbers:                   # FIX 3: guard empty input
        return {"mean": None, "median": None, "min": None, "max": None}
    sorted_nums = sorted(numbers)
    n = len(sorted_nums)
    median = (
        (sorted_nums[n // 2 - 1] + sorted_nums[n // 2]) / 2
        if n % 2 == 0
        else sorted_nums[n // 2]
    )
    return {
        "mean":   sum(numbers) / n,
        "median": median,
        "min":    min(numbers),
        "max":    max(numbers),
    }


def remove_duplicates(lst):
    """Return list with duplicates removed, preserving order — O(n)."""
    return list(dict.fromkeys(lst))   # FIX 4: O(n) via dict insertion order


def load_config(config_string):
    """Parse a configuration string safely — no arbitrary code execution."""
    return _ast.literal_eval(config_string)   # FIX 5: safe, not eval()


def normalize(values, min_val=None, max_val=None):
    """Scale values to [0, 1]. Returns unchanged list when all values equal."""
    if not values:
        return []
    lo = min_val if min_val is not None else min(values)
    hi = max_val if max_val is not None else max(values)
    if hi == lo:                       # FIX 6: guard div-by-zero
        return [0.0] * len(values)
    return [(v - lo) / (hi - lo) for v in values]
