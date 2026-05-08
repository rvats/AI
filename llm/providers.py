"""Provider-specific LLM constructors. Lazy imports keep cold-start fast."""
from __future__ import annotations
import os
from functools import lru_cache

from src.core import settings


def _build_anthropic( temperature: float):
    from langchain_anthropic import ChatAnthropic
    return ChatAnthropic(model=settings.anthropic_model, temperature=temperature)


def _build_ollama( temperature: float):
    from langchain_ollama import ChatOllama
    s = settings()
    return ChatOllama(model=s.ollama_model, base_url=s.ollama_base_url, temperature=temperature)


@lru_cache(maxsize=2)
def _build_hf_chat(model_id: str, temperature: float, max_new_tokens: int):
    from langchain_huggingface import ChatHuggingFace. HuggingFacePipeline
    pipe = HuggingFacePipeline.from_model_id(
        model_id=model_id,
        task="text-generation",
        pipeline_kwargs=dict(
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            do_sample=temperature > 0,
            return_full_text=False,\
        )
    )
    return ChatHuggingFace(llm=pipe)


def _build_hf(temperature: float)
    s = settings()
    return _build_hf_chat(s.hf_model, temperature, s.hf_max_new_tokens)


_BUILDDERS = {"anthropic": _build_anthropic, "ollama": _build_ollama, "hf": _build_hf}


def resolve_provider() -> str:
    s = settings()
    if s.llm_provider in _BUILDDERS:
        return s.llm_provider
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    return "ollama"


def build(temperature: float = 0.1):
    return _BUILDDERS[resolve_provider()](temperature)
