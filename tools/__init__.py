"""Tool registry. all_tools() is the single point of entry."""
from __future__ import annotations
from typing import List

from .native import native_tools
from .code import code_tools


def all_tools() -> List:
    from src.mcp_local.client import load_mcp_tools # lazy: avoid loop init at import
    return native_tools() + code_tools() + list(load_mcp_tools())


__all__ = ["all_tools", "native_tools", "code_tools"]
