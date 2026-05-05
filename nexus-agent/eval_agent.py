"""
eval_agent.py — Agentic Code Evaluator
=======================================
Sends a code file to Nexus Agent and streams a full agentic evaluation:
  1. Read & static analysis
  2. Write & run tests → find real bugs via execution
  3. Fix all issues
  4. Re-run tests to verify fixes
  5. Benchmark performance
  6. Generate a final report

Usage:
  python eval_agent.py demo/buggy_data_processor.py
  python eval_agent.py demo/buggy_data_processor.py --server http://localhost:8000
"""

import sys
import json
import time
import argparse
import requests
from colorama import init, Fore, Back, Style

init(autoreset=True)   # Windows-safe ANSI colors

SERVER = "http://localhost:8000"

# ── Pretty print helpers ───────────────────────────────────────────────────────

BAR = "─" * 64

def header():
    print()
    print(Fore.CYAN + Style.BRIGHT + "╔" + "═" * 64 + "╗")
    print(Fore.CYAN + Style.BRIGHT + "║" + Style.RESET_ALL +
          Style.BRIGHT + "        NEXUS  AGENTIC  CODE  EVALUATOR              " +
          "        " + Fore.CYAN + Style.BRIGHT + "║")
    print(Fore.CYAN + Style.BRIGHT + "╚" + "═" * 64 + "╝" + Style.RESET_ALL)
    print()

def section(title):
    print()
    print(Fore.YELLOW + Style.BRIGHT + f"  ▶  {title}")
    print(Fore.YELLOW + "  " + BAR[:60])

def agent_text(text):
    # Print character by character for streaming feel
    sys.stdout.write(Fore.WHITE + text + Style.RESET_ALL)
    sys.stdout.flush()

def tool_start(name):
    icons = {
        "read_file": "📄", "execute_python": "🐍",
        "write_file": "✍️", "list_directory": "📁",
        "web_search": "🌐", "get_system_info": "💻",
    }
    icon = icons.get(name, "🔧")
    print()
    print(Fore.BLUE + Style.BRIGHT + f"\n  ┌─ {icon}  TOOL: {name}")

def tool_call(name, args):
    for k, v in args.items():
        val = str(v)
        if len(val) > 80:
            val = val[:77] + "..."
        print(Fore.BLUE + f"  │  {k}: " + Fore.CYAN + val)

def tool_result(name, result):
    lines = result.strip().split("\n")
    print(Fore.BLUE + "  │")
    print(Fore.BLUE + "  │  " + Fore.GREEN + Style.BRIGHT + "Result:")
    for line in lines[:20]:          # show up to 20 lines
        print(Fore.BLUE + "  │  " + Fore.GREEN + Style.DIM + line)
    if len(lines) > 20:
        print(Fore.BLUE + "  │  " + Fore.GREEN + Style.DIM +
              f"  ... ({len(lines) - 20} more lines)")
    print(Fore.BLUE + "  └" + "─" * 40)

def error_msg(msg):
    print()
    print(Fore.RED + Style.BRIGHT + "  ✗ ERROR: " + msg)
    print()

def done_msg():
    print()
    print(Fore.GREEN + Style.BRIGHT + "  ✔  Evaluation complete.")
    print(Fore.GREEN + "  " + BAR[:60])
    print()

# ── Evaluation prompt ──────────────────────────────────────────────────────────

def build_prompt(filepath: str) -> str:
    return f"""Perform a complete AGENTIC CODE EVALUATION of the file: {filepath}

Follow these steps in order — use tools at every step:

STEP 1 — READ THE CODE
  Use read_file to load and display the source code.

STEP 2 — STATIC ANALYSIS
  Carefully read through the code and list every issue you can see:
  bugs, missing return values, exception risks, security flaws, performance problems.

STEP 3 — DYNAMIC TESTING (most important)
  Write a Python test script and use execute_python to RUN it.
  The tests must cover: normal cases, edge cases (empty input, duplicates, zero), boundary values.
  Show the actual test output — failing tests prove the bugs are real.

STEP 4 — BENCHMARK PERFORMANCE
  Use execute_python to measure the speed of inefficient functions.
  Compare against optimized alternatives using timeit.

STEP 5 — FIX ALL ISSUES
  Write a corrected version of the file. Use write_file to save it as:
  demo/buggy_data_processor_fixed.py
  Fix every bug found. Replace eval() with ast.literal_eval(). Optimize O(n²) to O(n).

STEP 6 — RE-RUN TESTS ON FIXED VERSION
  Use execute_python to run the same test suite against the fixed file.
  All tests must pass — show the green output.

STEP 7 — FINAL REPORT
  Produce a clearly formatted evaluation report with:
  - List of all bugs found (with line numbers)
  - Security vulnerabilities
  - Performance improvements made
  - Test results: before and after
  - Overall code quality score (0-10) before and after

Be thorough and actually execute code at each step. Do not skip any step.
"""

# ── Stream the SSE response ────────────────────────────────────────────────────

def run_evaluation(filepath: str, server: str):
    header()
    print(Fore.WHITE + Style.BRIGHT + f"  File:    " + Fore.CYAN + filepath)

    # Get current backend info
    try:
        cfg = requests.get(f"{server}/api/config", timeout=5).json()
        backend = cfg.get("backend", "unknown")
        model = cfg.get("ollama_model") if backend == "ollama" else cfg.get("anthropic_model", "?")
        print(Fore.WHITE + Style.BRIGHT + f"  Backend: " + Fore.MAGENTA + f"{backend}  |  {model}")
        print(Fore.WHITE + Style.BRIGHT + f"  Server:  " + Fore.WHITE + server)
        print()

        if backend == "ollama":
            ol = requests.get(f"{server}/api/ollama/models", timeout=5).json()
            if not ol.get("running"):
                print(Fore.RED + Style.BRIGHT + "  ✗ Ollama is not running.")
                print(Fore.YELLOW + "    Start it: " + Fore.WHITE + "ollama serve")
                print(Fore.YELLOW + "    Pull model: " + Fore.WHITE + f"ollama pull {model}")
                sys.exit(1)
        elif backend == "anthropic" and not cfg.get("has_anthropic_key"):
            print(Fore.RED + Style.BRIGHT + "  ✗ No Anthropic API key configured.")
            print(Fore.YELLOW + "    Open " + Fore.WHITE + f"{server}" +
                  Fore.YELLOW + " → ⚙ Settings → add your key")
            sys.exit(1)

    except requests.ConnectionError:
        print(Fore.RED + Style.BRIGHT + f"  ✗ Cannot connect to Nexus Agent at {server}")
        print(Fore.YELLOW + "    Start it: " + Fore.WHITE + "python main.py")
        sys.exit(1)

    section("Sending evaluation task to agent…")
    print()

    prompt = build_prompt(filepath)
    current_tool_name = None
    current_text = ""
    in_text = False

    try:
        with requests.post(
            f"{server}/api/chat",
            json={"message": prompt},
            stream=True,
            timeout=300,
        ) as resp:
            resp.raise_for_status()
            buf = ""

            for raw in resp.iter_content(chunk_size=None, decode_unicode=True):
                buf += raw
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if not line.startswith("data: "):
                        continue
                    try:
                        data = json.loads(line[6:])
                    except Exception:
                        continue

                    t = data.get("type")

                    if t == "text":
                        if not in_text:
                            print()
                            print(Fore.MAGENTA + Style.BRIGHT + "  [AGENT] " + Style.RESET_ALL, end="")
                            in_text = True
                        agent_text(data["content"])
                        current_text += data["content"]

                    elif t == "tool_start":
                        in_text = False
                        current_text = ""
                        current_tool_name = data["name"]
                        tool_start(data["name"])

                    elif t == "tool_call":
                        tool_call(data["name"], data.get("input", {}))

                    elif t == "tool_result":
                        in_text = False
                        tool_result(data["name"], data.get("result", ""))
                        current_tool_name = None

                    elif t == "error":
                        error_msg(data.get("message", "Unknown error"))
                        return

                    elif t == "done":
                        done_msg()
                        return

    except KeyboardInterrupt:
        print()
        print(Fore.YELLOW + "\n  Interrupted by user.")
    except Exception as e:
        error_msg(str(e))

# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agentic Code Evaluator")
    parser.add_argument("file", nargs="?", default="demo/buggy_data_processor.py",
                        help="Python file to evaluate")
    parser.add_argument("--server", default=SERVER, help="Nexus Agent server URL")
    args = parser.parse_args()

    run_evaluation(args.file, args.server)
