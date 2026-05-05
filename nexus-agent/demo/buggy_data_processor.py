"""
DataProcessor — a small analytics utility.
Contains several intentional bugs, performance issues, and security flaws.
The Agentic AI evaluator will find and fix them automatically.
"""


def bubble_sort(arr):
    """Sort a list using bubble sort."""
    n = len(arr)
    for i in range(n):
        for j in range(0, n - i - 1):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
    # BUG 1: No return statement — always returns None


def binary_search(arr, target):
    """Find index of target in a sorted list, or -1 if not found."""
    left, right = 0, len(arr)          # BUG 2: should be len(arr) - 1
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
    """Return mean, median, min, max of a list of numbers."""
    # BUG 3: crashes with ZeroDivisionError on empty list
    mean = sum(numbers) / len(numbers)
    sorted_nums = sorted(numbers)
    n = len(sorted_nums)
    median = (sorted_nums[n // 2 - 1] + sorted_nums[n // 2]) / 2 if n % 2 == 0 else sorted_nums[n // 2]
    return {"mean": mean, "median": median, "min": min(numbers), "max": max(numbers)}


def remove_duplicates(lst):
    """Return list with duplicates removed, preserving order."""
    # BUG 4 (performance): O(n²) — 'in' on a list is O(n)
    result = []
    for item in lst:
        if item not in result:
            result.append(item)
    return result


def load_config(config_string):
    """Parse a configuration string into a Python dict."""
    # BUG 5 (security): eval() executes arbitrary code!
    return eval(config_string)


def normalize(values, min_val=None, max_val=None):
    """Scale values to [0, 1] range."""
    if min_val is None:
        min_val = min(values)
    if max_val is None:
        max_val = max(values)
    # BUG 6: no guard when min_val == max_val (division by zero)
    return [(v - min_val) / (max_val - min_val) for v in values]
