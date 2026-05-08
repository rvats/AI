"""Workspace sandbox helpers shared by every tool."""
from __future__ import annotations
import os
import subprocess
from pathlib import Path
from typing import Optional

# LLMs hallucinate these absolute prefixes; strip them and treat the remainder.
# as relative to the workspace root.
_FAKE_ABS_PREFIXES = ("/workspace/", "/workspace", "/mnt/data/", "/sandbox/", "/app/")


def workspace_root() -> Path:
    return Path(os.getenv("AGENT_WORKSPACE", ".")).resolve()


def normalize(rel: str) -> str:
    s = (rel or "").strip()
    if "\x00" in s:
        raise ValueError("Path cannot contain null bytes")
    for prefix in _FAKE_ABS_PREFIXES:
        if s == prefix.rstrip("/") or s.startswith(prefix):
            s = s[len(prefix):]
            break
    if s.startswith("/"):
        s = s.lstrip("/")
    if s.startswith("./"):
        s = s[2:]
    return s or "."


def safe_path(rel: str) -> Path:
    """ Resolve `rel` under the workspace, refusing to escape it (incl, via symlinks)."""
    root = workspace_root()
    s = normalize(rel)
    candidate = (root / s).resolve()
    if root != candidate and root not in candidate.parents:
        raise ValueError(f"Path {rel} resolves outside the workspace")
    return candidate


def truncate(text: str, limit: int = 8000) -> str:
    return text if len(text) <= limit else text[:limit] + "\n...[truncated]"


def run_subprocess(
        argv: list[str],
        cwd: Optional[Path] = None,
        timeout: int = 60,
        input_text: Optional[str] = None
    ) -> dict:
    """Sandboxed subprocess wrapper. Returns ok/exit_code/stdout/stderr/argv."""
    try:
        proc = subprocess.run(
            argv,
            cwd=str(cwd) if cwd else str(workspace_root()),
            capture_output=True,
            text=True,
            timeout=timeout,
            input=input_text
        )
    except FileNotFoundError as e:
        return {"ok": False, "error": f"Command not found: {argv[0]} ({e})", 
                "exit_code": -1, "stdout": "", "stderr": ""}
    except subprocess.TimeoutExpired as e:
        return {
            "ok": False, 
            "error": f"Command timed out after {timeout} seconds", 
            "exit_code": -1, 
            "stdout": (e.stdout if isinstance(e.stdout, str) else (e.stdout or b"").decode("utf-8", "replace")),
            "stderr": (e.stderr if isinstance(e.stderr, str) else (e.stderr or b"").decode("utf-8", "replace"))
        }
    return {
        "ok": proc.returncode == 0,
        "exit_code": proc.returncode,
        "stdout": truncate(proc.stdout),
        "stderr": truncate(proc.stderr),
        "argv": argv
    }
