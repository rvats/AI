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

