"""Centralized settings loaded from environment."""
from __future__ import annotations
import os
from dataclasses import dataclass


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    # LLM
    llm_provider: str = "" # "" -> auto. anthropic|ollama|hf
    anthropic_model: str = "claude-3-5-sonnet-latest"
    ollama_model: str = "llama3.1"
    ollama_base_url: str = "http://localhost:11434"
    hf_model: str = "Qwen/Qwen2.5-3B-Instruct"
    hf_max_new_tokens: int = 512
    # Agent
    agent_model: str = "react"
    planner_max_steps: int = 6
    # Sandbox
    workspace: str = "."
    allow_shell: bool = False
    allow_python_repl: bool = False
    # MCP / browser
    enable_mcp: bool = False
    enable_browser: bool = False
    browser_preferred: str = "chromium" # chromium|firefox|webkit
    browser_headless: bool = True
    mcp_config: str = ""
    # Postgres MCP
    enable_postgres: bool = False
    pg_dsn: str = ""
    pg_readonly: bool = False
    pg_allow_ddl: bool = False

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            llm_provider=os.getenv("LLM_PROVIDER", ""),
            anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"),
            ollama_model=os.getenv("OLLAMA_MODEL", "llama3.1"),
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            hf_model=os.getenv("HF_MODEL", "Qwen/Qwen2.5-3B-Instruct"),
            hf_max_new_tokens=int(os.getenv("HF_MAX_NEW_TOKENS", "512")),
            agent_model=os.getenv("AGENT_MODEL", "react").strip().lower(),
            planner_max_steps=int(os.getenv("PLANNER_MAX_STEPS", "6")),
            workspace=os.getenv("AGENT_WORKSPACE", "."),
            allow_shell=_bool("ALLOW_SHELL", False),
            allow_python_repl=_bool("ALLOW_PYTHON_REPL", False),
            enable_mcp=_bool("ENABLE_MCP", False),
            enable_browser=_bool("ENABLE_BROWSER", False),
            browser_preferred=os.getenv("BROWSER_PREFERRED", "chromium"),
            browser_headless=_bool("BROWSER_HEADLESS", True),
            mcp_config=os.getenv("MCP_CONFIG", ""),
            enable_postgres=_bool("ENABLE_POSTGRES", False),
            pg_dsn=os.getenv("PG_DSN", ""),
            pg_readonly=_bool("PG_READONLY", False),
            pg_allow_ddl=_bool("PG_ALLOW_DDL", False),
        )
    

    def settings() -> Settings:
        """Fresh Settings each call - env may change between agent build."""
        return Settings.from_env()
    