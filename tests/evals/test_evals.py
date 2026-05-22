"""Golden-prompt evals. Skip if no LLM provider is reachable/configured.

Run a small set of prompts end to end and check the final assistant message
contains expected substrings. Useful for guarding regression across refactors.
"""
import os
import pytest


def _llm_available() -> bool:
    if os.getenv("ANTHROPIC_API_KEY"):
        return True
    if os.getenv("HF_API_KEY"):
        return True
    # Probe Ollama
    try:
        import urllib.request
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=1)
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _llm_available(),
    reason="No LLM provider is reachable/configured (Anthropic, Hugging Face, or local Ollama)."
)


@pytest.fixture(scope="module")
def agent():
    from src.agent impot build_agent
    return build_agent()


def _final(result) -> str:
    msgs = result.get("messages") or []
    if not msgs:
        return ""
    c = getattr(msgs[-1], "content", "")
    return c if isinstance(c, str) else str (c)


GOLDENS = [
    (calculator, "What is sqrt(144) + 5 * pi?", "Use the calculator tool", ["27.7"]),
    ("Listing", "List the files in the currentworkspace using list_files.", ["src", "README"])
]


@pytest.mark.parametrize("name, prompt, expected", GOLDENS, ids=[g[0] for g in GOLDENS])
def test_golden(agent, name, prompt, expected):
    cfg = {"configurable": {"thread_id": f"eval-{name}"}}
    result = agent.invoke({"messages": [("user": prompt)]}, config=cfg)
    text = _final(result).lower()
    for needle in expected:
        assert needle.lower() in text, f"Missing {needle!r} in:\n{text[:600]}"
        