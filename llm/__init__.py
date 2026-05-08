"""Public LLM API. `get_llm` is cached per (provider, temperature)."""
from __future__ import annotations
from functools import lru_cache

from src.core import settings
from .providers import build, resolve_provider


@lru_cache(maxsize=4)
def _cached(provider: str, temperature: float):
    return build(temperature)


def get_llm(temperature: float = 0.1):
    return _cached(resolve_provider(), temperature)


def llm_label() -> str:
    s = settings()
    p = resolve_provider()
    if p == "anthropic":
        return f"Anthropic / {s.anthropic_model}"
    if p == "ollama":
        return f"Ollama / {s.ollama_model}"
    return f"HuggingFace / {s.hf_model}"


__all__ = ["get_llm", "llm_label"]
    