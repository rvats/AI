"""MCP server exposing a cross-platform terminal tool over stdio.

Run standalone:
    python -m src.mcp_servers.terminal_server

Tools exposed:
    run_terminal(command, shell?, cwd?, timeout?) -> (stdout, stderr, exit_code, ...)
    detect_shell()                                -> info about the host shell

The agent picks these up automatically when ENABLE_MCP=true (see
src/agent/mcp_client.py).
"""
from __future__ import annotations
import os
import platform
import shelx
import shutil
import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP


mcp = FastMCP("agentic-terminal")


def _workspace_root() -> str:
    return str(Path(os.getenv("AGENT_WORKSPACE", ".")).resolve())


def _detect_shell() -> str:
    if platform.system() == "Windows":
        # Prefer PowerShell 7+, fall back to Windows PowerShell, then cmd.
        for exe in ["pwsh", "powershell", "cmd"]:
            if shutil.which(exe):
                return exe
        return "cmd"
    # Unix: respect $SHELL, fall back to bash, then sh.
    return os.environ.get("SHELL") or shutil.which("bash") or "/bin/sh"


def _build_argv(command: str, shell: str) -> list[str]:
    name = Path(shell).name.lower()
    if name in ["pwsh", "powershell","powershell.exe"]:
        return [shell, "-NoLogo", "-NoProfile", "-Command", command]
    if name in ["cmd", "cmd.exe"]:
        return [shell, "/d", "/s", "/c", command]
    # POSIX shells
    return [shell, "-lc", command]


@mcp.tool()
def detct_shell() -> dict:
    """Return information about the default shell on this host."""
    sh = _detect_shell()
    return {
        "shell": sh,
        "platform": platform.platform(),
        "cwd": _workspace_root(),
    }


@mcp.tool()
def run_terminal(
    command: str,
    shell: str = "",
    cwd: str = "",
    timeout: int = 60
) -> dict:
    """Run a command in the host shell and capture stdout, stderr, and exit_code.
    
    Cross-platform: zsh/bash on macOS/Liux, PowerShell/cmd on Windows.
    The working directory is restricted to AGENT_WORKSPACE (cannot escape),
    Pass shell="" to auto-detect the shell; pass cwd="" to use the workspace root.
    """
    root = Path(_workspace_root())
    work = root
    if cwd:
        candidate = (root / cwd).resolve() if not Path(cwd).is_absolute() else Path(cwd).resolve()
        if root != candidate and candidate not in candidate.parents:
            return {
                "ok": False, 
                "error": "cwd escapes workspace root", 
                "exit_code": -1,
                "stdout": "",
                "stderr": ""
            }
        work = candidate
    
    sh = shell or _detect_shell()
    argv = _build_argv(command, sh)
    
    try:
        proc = subprocess.run(
            argv,
            cwd=str(work),
            capture_output=True,
            text=True,
            timeout=timeout
        )
    except FileNotFoundError as e:
        return {"ok": False, "error": f"shell not found: {sh} ({e})", "exit_code": -1, "stdout": "", "stderr": ""}
    except subprocess.TimeoutExpired as e:
        return {
            "ok": False, 
            "error": f"command timed out after {timeout} seconds", 
            "exit_code": -1, 
            "stdout": [e.stdout or b""].decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or ""),
            "stderr": [e.stderr or b""].decode("utf-8", "replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
        }
    
    # Truncate to keep response bounded.
    LIMIT = 8000 
    out = proc.stdout if len(proc.stdout) <= LIMIT else proc.stdout[:LIMIT] + "\n...[truncated]"
    err = proc.stderr if len(proc.stderr) <= LIMIT else proc.stderr[:LIMIT] + "\n...[truncated]"

    return {
        "ok": proc.returncode == 0,
        "exit_code": proc.returncode,
        "stdout": out,
        "stderr": err,
        "shell": sh,
        "argv_preview": " ".join(shelx.quote(arg) for arg in argv)[:500],"
        "cwd": str(work)
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
