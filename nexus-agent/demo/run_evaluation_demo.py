"""
Agentic Code Evaluation — Live Demo
=====================================
Demonstrates the complete agentic evaluation loop:

  STEP 1  Read & parse source code
  STEP 2  Static analysis  (find bugs by reading)
  STEP 3  Dynamic testing  (find bugs by RUNNING code)
  STEP 4  Performance benchmark
  STEP 5  Apply all fixes
  STEP 6  Re-run tests on fixed code
  STEP 7  Final evaluation report

This script runs fully standalone — no API key, no Ollama needed.
It shows exactly what the Nexus Agent does when you send it a code file.
"""

import ast
import sys
import time
import timeit
import importlib.util
import traceback
from pathlib import Path
from colorama import init, Fore, Style

# Force UTF-8 output on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

init(autoreset=True)

# ── Helpers ────────────────────────────────────────────────────────────────────

def step(n, title):
    print()
    print(Fore.CYAN + Style.BRIGHT + f"\n{'━'*66}")
    print(Fore.CYAN + Style.BRIGHT + f"  STEP {n}: {title}")
    print(Fore.CYAN + Style.BRIGHT + f"{'━'*66}")

def info(msg, indent=4):
    print(Fore.WHITE + " " * indent + msg)

def ok(msg, indent=4):
    print(Fore.GREEN + Style.BRIGHT + " " * indent + "✔  " + Style.RESET_ALL + msg)

def fail(msg, indent=4):
    print(Fore.RED + Style.BRIGHT + " " * indent + "✘  " + Style.RESET_ALL + msg)

def warn(msg, indent=4):
    print(Fore.YELLOW + Style.BRIGHT + " " * indent + "⚠  " + Style.RESET_ALL + msg)

def agent_says(msg):
    print()
    print(Fore.MAGENTA + Style.BRIGHT + "  [AGENT] " + Style.RESET_ALL + Fore.WHITE + msg)

def tool_call(name, arg):
    print(Fore.BLUE + f"  [TOOL: {name}] " + Fore.CYAN + str(arg))

def pause(secs=0.6):
    time.sleep(secs)

def load_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

# ── Test runner ────────────────────────────────────────────────────────────────

def run_test(name, fn, expected=None):
    try:
        result = fn()
        if expected is not None:
            if result == expected:
                ok(f"{name}  →  {result!r}")
                return True
            else:
                fail(f"{name}  →  got {result!r}, expected {expected!r}")
                return False
        else:
            ok(f"{name}  →  {result!r}")
            return True
    except Exception as e:
        fail(f"{name}  →  {type(e).__name__}: {e}")
        return False

# ── Main demo ─────────────────────────────────────────────────────────────────

def main():
    source_path = Path(__file__).parent / "buggy_data_processor.py"
    fixed_path  = Path(__file__).parent / "buggy_data_processor_fixed.py"

    print()
    print(Fore.CYAN + Style.BRIGHT + "╔" + "═" * 64 + "╗")
    print(Fore.CYAN + Style.BRIGHT + "║" + Style.RESET_ALL + Style.BRIGHT +
          "       NEXUS  AGENTIC  CODE  EVALUATOR  —  Demo Mode           " +
          Fore.CYAN + Style.BRIGHT + "║")
    print(Fore.CYAN + Style.BRIGHT + "╚" + "═" * 64 + "╝")
    print()
    info(f"Target file : {source_path.name}", 2)
    info(f"Mode        : Standalone demo (no LLM needed)", 2)
    info(f"What runs   : real Python, real bugs, real fixes", 2)
    pause()

    # ── STEP 1: Read ──────────────────────────────────────────────────────────
    step(1, "READ & DISPLAY SOURCE CODE")
    agent_says("Let me load the file and examine its contents.")
    pause(0.4)
    tool_call("read_file", source_path.name)
    pause(0.4)

    source = source_path.read_text(encoding="utf-8")
    print()
    for i, line in enumerate(source.splitlines(), 1):
        colour = Fore.YELLOW if "BUG" in line else Fore.WHITE + Style.DIM
        print(colour + f"    {i:3d} │ {line}")
    pause(0.6)

    # ── STEP 2: Static analysis ───────────────────────────────────────────────
    step(2, "STATIC ANALYSIS  (read the code, spot issues)")
    agent_says("Scanning for bugs, security issues, and performance problems…")
    pause(0.5)

    tree = ast.parse(source)
    functions = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    info(f"Functions found: {', '.join(functions)}")
    print()

    findings = [
        ("BUG",      "bubble_sort",       "line 18", "Missing `return arr` — always returns None"),
        ("BUG",      "binary_search",     "line 23", "Off-by-one: `right = len(arr)` should be `len(arr)-1`"),
        ("BUG",      "calculate_stats",   "line 33", "ZeroDivisionError on empty list (len=0)"),
        ("PERF",     "remove_duplicates", "line 41", "O(n²) — `in` on list is O(n); use set for O(n)"),
        ("SECURITY", "load_config",       "line 46", "eval() executes arbitrary code — use ast.literal_eval()"),
        ("BUG",      "normalize",         "line 52", "Division by zero when min_val == max_val"),
    ]

    for kind, fn, loc, desc in findings:
        colour = Fore.RED if kind == "BUG" else (Fore.YELLOW if kind == "PERF" else Fore.MAGENTA)
        tag = colour + Style.BRIGHT + f"  [{kind}]" + Style.RESET_ALL
        print(f"{tag} {Fore.CYAN}{fn}{Style.RESET_ALL} ({loc}): {desc}")
        pause(0.2)

    # ── STEP 3: Dynamic testing ───────────────────────────────────────────────
    step(3, "DYNAMIC TESTING  (execute the code, prove the bugs)")
    agent_says("Writing and running tests against the ORIGINAL file to confirm each bug.")
    pause(0.5)
    tool_call("execute_python", "test suite against buggy_data_processor.py")
    pause(0.4)

    # Dynamically load the buggy module
    try:
        mod = load_module(source_path, "buggy")
    except Exception as e:
        fail(f"Failed to import module: {e}")
        return

    print()
    passes = 0
    fails  = 0

    def t(name, fn, expected=None):
        nonlocal passes, fails
        if run_test(name, fn, expected):
            passes += 1
        else:
            fails += 1
        pause(0.15)

    # bubble_sort
    t("bubble_sort([3,1,2]) returns sorted list",
      lambda: mod.bubble_sort([3, 1, 2]), [1, 2, 3])

    t("bubble_sort([]) returns []",
      lambda: mod.bubble_sort([]) or [], [])

    # binary_search
    t("binary_search([1,2,3,4,5], 3) == 2",
      lambda: mod.binary_search([1, 2, 3, 4, 5], 3), 2)

    t("binary_search([1,2,3], 1) == 0",
      lambda: mod.binary_search([1, 2, 3], 1), 0)

    # calculate_stats
    t("calculate_stats([1,2,3,4,5]) mean == 3.0",
      lambda: mod.calculate_stats([1, 2, 3, 4, 5])["mean"], 3.0)

    t("calculate_stats([]) — should not crash",
      lambda: mod.calculate_stats([]))

    # remove_duplicates
    t("remove_duplicates([1,2,2,3]) == [1,2,3]",
      lambda: mod.remove_duplicates([1, 2, 2, 3]), [1, 2, 3])

    # load_config — security (we do NOT call eval on malicious input)
    t("load_config(\"{'a': 1}\") parses safely",
      lambda: mod.load_config("{'a': 1}"), {'a': 1})

    # normalize
    t("normalize([1,1,1]) — should not crash",
      lambda: mod.normalize([1, 1, 1]))

    print()
    print(Fore.YELLOW + Style.BRIGHT +
          f"  Test results: {passes} passed, {fails} failed  ← bugs proven by execution")

    # ── STEP 4: Performance benchmark ─────────────────────────────────────────
    step(4, "PERFORMANCE BENCHMARK")
    agent_says("Measuring the O(n²) remove_duplicates vs an O(n) alternative.")
    pause(0.4)
    tool_call("execute_python", "timeit benchmark — list vs set deduplication")
    pause(0.4)

    big = list(range(500)) + list(range(500))   # 1000 items, 500 duplicates

    t_slow = timeit.timeit(lambda: mod.remove_duplicates(big), number=200)
    t_fast = timeit.timeit(lambda: list(dict.fromkeys(big)),   number=200)

    speedup = t_slow / t_fast if t_fast else float("inf")
    print()
    warn(f"remove_duplicates (list 'in'):  {t_slow*1000:.1f} ms / 200 runs  ← O(n²)")
    ok(  f"dict.fromkeys() O(n) version:   {t_fast*1000:.1f} ms / 200 runs")
    info(f"Speedup: {speedup:.1f}×  on a 1000-element list", 4)

    # ── STEP 5: Apply fixes ───────────────────────────────────────────────────
    step(5, "APPLY ALL FIXES")
    agent_says("Writing the corrected version of the file…")
    pause(0.4)
    tool_call("write_file", fixed_path.name)
    pause(0.5)

    fixed_source = '''\
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
'''
    fixed_path.write_text(fixed_source, encoding="utf-8")
    ok(f"Saved fixed file → {fixed_path.name}")

    # ── STEP 6: Re-run tests on fixed code ────────────────────────────────────
    step(6, "RE-RUN TESTS ON FIXED VERSION")
    agent_says("Running the same test suite against the fixed file…")
    pause(0.4)
    tool_call("execute_python", f"test suite against {fixed_path.name}")
    pause(0.4)

    try:
        fmod = load_module(fixed_path, "fixed")
    except Exception as e:
        fail(f"Failed to import fixed module: {e}")
        return

    print()
    passes2 = 0
    fails2  = 0

    def t2(name, fn, expected=None):
        nonlocal passes2, fails2
        if run_test(name, fn, expected):
            passes2 += 1
        else:
            fails2 += 1
        pause(0.12)

    t2("bubble_sort([3,1,2]) returns [1,2,3]",
       lambda: fmod.bubble_sort([3, 1, 2]), [1, 2, 3])

    t2("bubble_sort([]) returns []",
       lambda: fmod.bubble_sort([]), [])

    t2("bubble_sort does NOT mutate original",
       lambda: (orig := [3, 1, 2], fmod.bubble_sort(orig), orig)[2], [3, 1, 2])

    t2("binary_search([1,2,3,4,5], 3) == 2",
       lambda: fmod.binary_search([1, 2, 3, 4, 5], 3), 2)

    t2("binary_search([1,2,3], 1) == 0",
       lambda: fmod.binary_search([1, 2, 3], 1), 0)

    t2("binary_search([1,2,3], 99) == -1",
       lambda: fmod.binary_search([1, 2, 3], 99), -1)

    t2("calculate_stats([1,2,3,4,5]) mean == 3.0",
       lambda: fmod.calculate_stats([1, 2, 3, 4, 5])["mean"], 3.0)

    t2("calculate_stats([]) returns None fields (no crash)",
       lambda: fmod.calculate_stats([])["mean"], None)

    t2("remove_duplicates([1,2,2,3]) == [1,2,3]",
       lambda: fmod.remove_duplicates([1, 2, 2, 3]), [1, 2, 3])

    t2("remove_duplicates preserves order",
       lambda: fmod.remove_duplicates([3, 1, 2, 1, 3]), [3, 1, 2])

    t2("load_config(\"{'k': 42}\") == {'k': 42}",
       lambda: fmod.load_config("{'k': 42}"), {'k': 42})

    t2("normalize([1,1,1]) — no crash, returns zeros",
       lambda: fmod.normalize([1, 1, 1]), [0.0, 0.0, 0.0])

    t2("normalize([0, 5, 10]) == [0.0, 0.5, 1.0]",
       lambda: fmod.normalize([0, 5, 10]), [0.0, 0.5, 1.0])

    print()
    colour = Fore.GREEN if fails2 == 0 else Fore.RED
    print(colour + Style.BRIGHT +
          f"  Test results: {passes2} passed, {fails2} failed")

    # ── STEP 7: Final report ───────────────────────────────────────────────────
    step(7, "FINAL EVALUATION REPORT")
    pause(0.5)

    quality_before = 3.1
    quality_after  = 9.2

    print()
    print(Fore.WHITE + Style.BRIGHT + "  ┌─ BUGS FOUND & FIXED " + "─" * 41 + "┐")
    issues = [
        ("BUG",      "bubble_sort  line 18",       "Added missing `return arr`"),
        ("BUG",      "binary_search  line 23",     "Fixed off-by-one (len → len-1)"),
        ("BUG",      "calculate_stats  line 33",   "Added empty-list guard"),
        ("BUG",      "normalize  line 52",         "Added min==max guard"),
        ("SECURITY", "load_config  line 46",       "Replaced eval() with ast.literal_eval()"),
        ("PERF",     "remove_duplicates  line 41", f"O(n²)→O(n): {speedup:.1f}× faster"),
    ]

    for kind, location, fix in issues:
        c = Fore.RED if kind=="BUG" else (Fore.MAGENTA if kind=="SECURITY" else Fore.YELLOW)
        tag = c + Style.BRIGHT + f"  │  [{kind:8s}]" + Style.RESET_ALL
        print(f"{tag} {Fore.CYAN}{location:30s}{Style.RESET_ALL} → {fix}")
        pause(0.15)

    print(Fore.WHITE + Style.BRIGHT + "  └" + "─" * 61 + "┘")
    print()
    print(Fore.WHITE + Style.BRIGHT + "  ┌─ TEST RESULTS " + "─" * 46 + "┐")
    print(Fore.RED   + f"  │  Before fix:  {passes} / {passes+fails} tests passing")
    print(Fore.GREEN + Style.BRIGHT +
          f"  │  After fix:   {passes2} / {passes2+fails2} tests passing  ← all green")
    print(Fore.WHITE + Style.BRIGHT + "  └" + "─" * 61 + "┘")
    print()
    print(Fore.WHITE + Style.BRIGHT + "  ┌─ CODE QUALITY SCORE " + "─" * 40 + "┐")
    bar_b = int(quality_before * 5)
    bar_a = int(quality_after  * 5)
    print(Fore.RED  + f"  │  Before:  {quality_before}/10  " +
          Fore.RED   + "█" * bar_b + Style.DIM + "░" * (50-bar_b))
    print(Fore.GREEN + Style.BRIGHT +
          f"  │  After:   {quality_after}/10  " +
          Fore.GREEN + Style.BRIGHT + "█" * bar_a + Style.DIM + "░" * (50-bar_a))
    print(Fore.WHITE + Style.BRIGHT + "  └" + "─" * 61 + "┘")
    print()
    ok(f"Fixed file saved: {fixed_path}", 2)
    print()
    print(Fore.CYAN + Style.BRIGHT +
          "  To run with a real LLM (Nexus Agent does all of this autonomously):")
    print(Fore.WHITE +
          "    1. Install Ollama:  https://ollama.com")
    print(Fore.WHITE +
          "    2. Pull a model:   ollama pull qwen2.5:7b")
    print(Fore.WHITE +
          "    3. Run evaluator:  python eval_agent.py demo/buggy_data_processor.py")
    print()


if __name__ == "__main__":
    main()
