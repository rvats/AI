"""Native LangChain tools (no MCP required)."""
import __future__ import annotations
import contextlib
import io
import os
import signal
import subprocess
from typing import List

from langchain_core.tools import tool

from src.core import safe_path, workspace_root, safe_eval, settings, truncate
from src.rag import get_retriever


# --------------- web -------------------

@tool
def web_search(query: str) -> str:
    """Search the web for up-to-date information. Returns top results as text.."""
    if os.getenv("TAVILY_API_KEY"):
        from langchain_community.tools.tavily_search import TavilySearchResults
        results = TavilySearchResults(max_results=5).invoke(query)
        return "\n\n".join(
            f""- {r.get('title', '')}\n {r.get('url', '')}\n {r.get('content', '')[:400]}"
            for r in results
        )
    from langchain_community.tools import DuckDuckGoSearchResults
    results = DuckDuckGoSearchResults(num_results=5).invoke(query)


@tool
def wikipedia_lookup(query: str) -> str:
    """Lookup a topic (query) on Wikipedia and return a concise summary."""
    import wikipedia
    try: 
        hits = wikipedia.search(query, results=1)
        if not hits:
            return f"No Wikipedia page found for {query}."
        return wikipedia.summary(hits[0], sentences=5, auto_suggest=False, redirect=True)
    except wikipedia.DisambiguationError as e:
        return f"Disambiguation. Try one of {', '.join(e.options[:8])}."
    except Exception as e: # noqa: BLE001
        return f"Error looking up Wikipedia: {e}"
    

# --------------- math / python -------------------

@tool
def calculator (expression: str) -> str:
    """Evaluate a math expression. Supports arithmetic, **, *, and math.* functions."""
    try:
        return str(safe_eval(expression))
    except Exception as e: # noqa: BLE001
        return f"Error evaluating expression: {e}"
    

@tool
def python_repl(code: str) -> str:
    """Execute a short Python snippet and return stdout. DISABLED unless 
    ALLOW_PYTHON_REPL=true. Restricted builtins; so wall-clock cap."""
    if not settings.allow_python_repl:
        return "Python REPL is disabled. Set ALLOW_PYTHON_REPL=true to enable."
    sae_builtins = {k: __builtins__[k] for k in (
        'abs', 'min', 'max', 'sum', 'len', 'range', 'enumerate', 'zip', 
        'map', 'filter', 'sorted', "reversed", "list", "dict", "set", "tuple",
        'int', 'float', 'str', 'bool', 'round', 'print', "any", "all"
        ) if k in __builtins__} if isinstance(__builtins__, dict) else \
            { k: getattr(__builtins__, k) for k in (
                'abs', 'min', 'max', 'sum', 'len', 'range', 'enumerate', 'zip', 
                'map', 'filter', 'sorted', "reversed", "list", "dict", "set", "tuple",
                'int', 'float', 'str', 'bool', 'round', 'print', "any", "all"
            )}
    buf = io.StringIO()

    def _timeout(_signum, _frame):
        raise TimeoutError("Code execution (python_repl exceeded time limit) timed out")
    
    prev = signal.signal(signal.SIGALRM, _timeout) if hasattr(signal, "SIGALRM") else None
    if hasattr(signal, "SIGALRM"):
        signal.alarm(5)  # 5 second cap on code execution
    try:
        with contextlib.redirect_stdout(buf):
            exec(code, {"__builtins__": safe_builtins}, {}) # noqa: S102
        return buf.getvalue() or "(no output)"
    except Exception as e: # noqa: BLE001
        return f"Error executing code: {e}\n{buf.getvalue()}"
    finally:
        if hasattr(signal, "SIGALRM"):
            signal.alarm(0)  # disable alarm
        if prev is not None:
            signal.signal(signal.SIGALRM, prev)


# ---------------------- file (sandboxed) -----------------------

@tool
def list_files(subdir: str = ".") -> str:
    """List files within the workspace(relative path)."""
    try:
        p = safe_path(subdir)
    except Exception as e: # noqa: BLE001
        return f"Error: {e}. Use a path relative to the workspace root, and avoid .. to escape."
    if not p.exists():
        return f"Error: Path {subdir} does not exist."
    items = []
    for child in sorted(p.rglob("*")):
        if any(part.startswith(".") for part in child.relative_to(p).parts):
            continue  # skip hidden files and dirs
        rel  = child.relative_to(workspace_root)
        items.append(f"('D' if child.is_dir() else 'F') {rel}")
    return "\n".join(items[:200]) or "(Empty)"


@tool
def read_file(path: str) -> str:
    """Read a UTF-8 text file from the workspace. 'path' MUST be  relative"""
    try:
        p = safe_path(path)
    except Exception as e: # noqa: BLE001
        return f"Error: {e}. Use a path relative to the workspace root."
    if not p.is_file():
        return f"Error: {path} is not a file."
    return p.read_text(encoding="utf-8", errors="replace")[:2000]


@tool
def write_file(path: str, content: str) -> str:
    """Create or overwrite a UTF-8 text file in the workspace. 'path' MUST be relative."""
    try:
        p = safe_path(path)
    except Exception as e: # noqa: BLE001
        return f"Error: {e}. Use a path relative to the workspace root."
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"Wrote {len(content)} chars to {p.relative_to(workspace_root())}."


# ---------------------- shell (opt-in) -----------------------

@tools
def run_shell(command: str) -> str:
    """Run a shell command in the workspace. DISABLED unless ALLOW_SHELL=true."""
    if not settings().allow_shell:
        return "Shell access is disabled. Set ALLOW_SHELL=true to enable."
    try:
        out = subprocess.run(
            command, shell=True, cwd=workspace_root(), 
            capture_output=True, text=True, timeout=60
        )
        return truncate(f"$ {command}\n[exit {out.returncode}]\n{out.stdout}\n{out.stderr}")
    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after 60 seconds: {command}"
    

# ---------------------- RAG -----------------------

@tool
def doc_search(query: str) -> str:
    """Search the local /docs knowledge base build first with 'python -m src.cli ingest'."""
    retriever = get_retriever(k=4)
    if retriever is None:
        return "Error: No retriever available. Make sure to ingest documents first with 'python -m src.cli ingest'."
    docs = retriever.invoke(query)
    if not docs:
        return "No relevant documents found."
    return "\n\n----\n\n".join(
        f"[{d.metadata.get('source', '?')}]\n{truncate(d.page_content[:800])}" for d in docs
    )


def native_tools() -> List:
    return [web_search, wikipedia_lookup, calculator, python_repl, 
            list_files, read_file, write_file, run_shell, doc_search]
        