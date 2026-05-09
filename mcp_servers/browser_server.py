"""Backward-compat shim. Real code lives in src/mcp_local/servers/browser_server.py."""
from src.mcp_local.servers.browser_server import * # noqa: F401, F403
from src.mcp_local.servers.browser_server import main as _main # noqa: F401

if __name__ == "__main__":
    _main()
