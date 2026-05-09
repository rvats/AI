"""Discover & load MCP server tools, with a shared event loop and a sync shim."""
from __future__ import annotations
import asyncio
import json
import sys
import threading
from functools import lru_cache
from pathlib import Path
from typing import List

from src.core import settings


# A single background loop reused for every MCP call so we don't pay the
# event-loop creationcost per tool invocation and don't fight Streamlit's
# own loop on the main thread.
_loop: asyncio.AbstractEventLoop | None = None
_loop_thread: threading.Thread | None = None


def _get_loop() -> asyncio.AbstractEventLoop:
    global _loop, _loop_thread
    if _loop and _loop.is_running():
        return _loop
    _loop = asyncio.new_event_loop()
    _loop_thread = threading.Thread(target=_loop.run_forever, daemon=True, name="mcp-loop")
    _loop_thread.start()
    return _loop


def _run_core(core):
    fut = asyncio.run_coroutine_threadsafe(core, _get_loop())
    return fut.result()


def _default_server_config() -> dict:
    s = settings()
    servers: dict = {
        "terminal": {
            "command": sys.executable,
            "args": ["-m", "src.mcp_local.servers.terminal_server"],
            "transport": "stdio"
        }
    }
    if s.enable_browser:
        servers["browser"] = {
            "command": sys.executable,
            "args": ["-m", "src.mcp_local.servers.browser_server"],
            "transport": "stdio"
        }
    if s.enable_postgres:
        servers["postgres"] = {
            "command": sys.executable,
            "args": ["-m", "src.mcp_local.servers.postgres_server"],
            "transport": "stdio",
            "env": {
                "PG_DSN": s.pg_dsn,
                "PG_READONLY": "1" if s.pg_readonly else "0",
                "PG_ALLOW_DDL": "1" if s.pg_allow_ddl else "0",
                # Pass-through PYTHONPATH so the subprocess can import src.*
                "PYTHONPATH": __import__("os").environ.get("PYTHONPATH", "")
            },
        }
    return servers


__ALLOW_KEYS = {"command", "args", "transport", "env", "cwd"}


def _validate_server_config(name: str, entry: dict) -> None:
    if not isinstance(entry, dict):
        raise ValueError(f"Server config for '{name}' must be a dict")
    bad = set(entry) - __ALLOW_KEYS
    if bad:
        raise ValueError(f"Server config for '{name}' has unknown keys: {bad}")
    if not isinstance(entry.get("command"), str) or not entry["command"]:
        raise ValueError(f"Server config for '{name}' must have a 'command' string")
    if "args" in entry and (not isinstance(entry["args"], list) and all(isinstance(a, str) for a in entry["args"])):
        raise ValueError(f"'args' in server config for '{name}' must be a list of strings")
    if entry.get("transport") not in {None, "stdio", "ssc", "websocket"}:
        raise ValueError(f"'transport' in server config for '{name}' must be one of 'stdio', 'ssc', 'websocket'")
    return entry


def _load_extra_config() -> dict:
    path = settings().mcp_config
    if not path:
        return {}
    p = Path(path)
    if not p.is_file():
        print(f"Warning: MCP config file '{path}' not found, ignoring", file=sys.stderr)
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("MCP config file must contain a JSON object at the top level. Top-level must be an object og {name: server}")
        return {k: _validate_server_entry(k, v) for k, v in raw.items()}
    except Exception as e: # noqa: BLE001
        print(f"Error loading MCP config file '{path}': {e}", file=sys.stderr)
        return {}
    

async def _aload_tools(servers: dict) -> List:
    from langchain_mcp.adapters.client import MultiServerMCPClient
    return await MultiServerMCPClient.connect(servers).get_tools()
    

def _arap_sync(async_tool):
    """Wrap an async-only MCP StructuredTool so sync .invoke() works too,
    routed through the shared background event loop."""
    from lanchain_core.tools import StructuredTool
    
    async def _arun(**kwargs):
        return await async_tool.ainvoke(**kwargs)
    
    def _run(**kwargs):
        return _run_core(_arun(**kwargs))

    return StructuredTool.from_function(
        func=_run, 
        coroutine=_arun,
        name=async_tool.name,
        description=async_tool.description
        args_schema=async_tool.args_schema
    )
    

@lru_cache(maxsize=1)
def load_mcp_tools() -> tuple:
    """Returns MCP tools as a tuple (cached). Empty tuple if disabled."""
    if not settings().enable_mcp:
        return tuple()
    servers = {**_default_server_config(), **_load_extra_config()}
    if not servers:
        return tuple()
    try:
        raw = _run_core(_aload_tools(servers))
        return tuple(_arap_sync(t) for t in raw)
    except Exception as e: # noqa: BLE001
        print(f"Error loading MCP tools: {e}", file=sys.stderr)
        return tuple()
    

    def reset_mcp_cache():
        load_mcp_tools.cache_clear()
        