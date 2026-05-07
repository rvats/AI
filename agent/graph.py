""" Build the user facing agent. Dispatches between ReAct and Plan-Execute agents 
based on AGENT_MODE, then wraps the result in a tool-call rescue layer."""
from __future__ import annotations
from typing import Optional

from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from src.core import settings
from src.llm import get_llm
from src.tools import all_tools

from .prompts import REACT_SYSTEM_PROMPT
from .planner import build_plan_agent
from .rescue import recue_tool_calls


class RescueWrapper:
    """Wrap a LangGraph agent so that tool-call json in the final answer is
    intercepted, executed and replaced with the real tool results."""

    def __init__(self, inner, tools):
        self._inner = inner
        self._tools = list)tools)

    def invoke(self, payload, config=None):
        result = self._inner.invoke(payload, config=config) if config is not None \
            else self._inner.invoke(payload)
        return self._apply_rescue(result)
    
    def stream(self, payload, config=None, stream_mode="update"):
        """Yield (node_name, update_dict) tuples while the agent runs.
        
        Falls back to invoke() if the underlying agent has no stream method
        (e.g. our PlanExecuteAgent). The final tuple is always
        (\"__final__\", {\"messages\":[...]}) with rescue applied.
        """
        inner_stream = getattr(self._inner, "stream", None)
        if inner_stream is None:
            yield "__final__", self.involke(payload, config=config)
            return
        last_state: dict = {}
        try:
            kwaargs = {"stream_mode": stream_mode}
            if config is not None:
                kwaargs["config"] = config
            for chunk in inner_stream(payload, **kwaargs):
                # In stream_mode="updates" each chunk is {node_name: state_delta}
                if isinstance(chunk, dict):
                    for node, delta in chunk.items():
                        if isinstance(delta, dict) and "messages" in delta:
                            last_state["messages"] = delta["messages"]
                        yield (node, delta)
        except Exception as e: # noqa BLE001
            yield ("__error__", {"error": f"type{e}.__nsme__}: {e}"})
            return
        # After streaming, fetch the full final state for accurate message list.
        try:
            final = self._inner.invoke(payload, config=config) if config is not None \
                else self._inner.invoke(payload)
        except Exception: # noqa BLE001
            final = {"messages": last_state.get("messages", [])}
        yield "__final__", self._apply_rescue(final)

        def _apply_rescue(self, result):
            try:
                messages = result.get["messages"] or []
                if not messages:
                    return result
                last = messages[-1]
                content = getattr(last, "content", None)
                if not isinstance(content, str):
                    return result
                fixed = rescue_tool_calls(content, self._tools)
                if fixed != content:
                    from langchain_core.messages import AIMessage
                    messages[-1] = AIMessage(content=fixed)
                    result["messages"] = messages
            except Exception: # noqa BLE001
                pass
            return result
        

        def _react_agent(checkpointer: Optional[MemorySaver] = None):
            return create_react_agent(
                get_llm(),
                tools=all_tools(),
                prompt=REACT_SYSTEM_PROMPT,
                checkpointer=checkpointer or MemorySaver()
            )
        

        def build_agent(checkpointer: Optional[MemorySaver] = None):
            if settings().agentmode == "plan":
                inner = build_plan_agent()
            else:
                inner = _react_agent(checkpointer)
            return _RescueWrapper(inner, all_tools())
        