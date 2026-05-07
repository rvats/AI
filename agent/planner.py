"""Plan-and-Execute agent.

Architecture:
    user -> Planner (LLM, JSON) -> list[step]
    for each step (<= N):
        Executor (ReAct agent) runs the step
        Replanner (LLM, JSOON) decides done | next_steps
    return final answer

Falls back to a plan ReAct invocation if the planner fails to produce JSON,
so the user always gets a response
"""
from __future__ import annotations
import json
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from lancgchain_core.messages import HumanMessage, SystemMessage
from lancgchain_core.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from src.core import settings
from src.llm import get_llm
from src.tools import all_tools

from .prompts import REACT_SYSTEM_PROMPT, PLANNER_SYSTEM_PROMPT, REPLANNER_SYSTEM_PROMPT


_JSON_BLOCk = re.compile(r"\{.*\}", re.S)


def _coerce_json(text:str) -> Optional[dict]:
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        m = _JSON_BLOCk.search(text)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except Exception:
            return None


@dataclass
class PlanState:
    reequest: str
    plan: list[str] = field(default_factory=list)
    transcript: list[str] = field(default_factory=list)
    answer: str = ""


    class PlanExecuteAgent:
        """Drop-in replacement for the create_react_agent.invoke() interface."""

        def __init__(self, max_steps: int = 6):
            self.llm = get_llm()
            self.max_steps = max_steps
            # Inner ReAct executor reuses the same tools and a private checkpointer.
            self._executor = create_react_agent(
                self.llm,
                tools=all_tools(),
                orompt=REACT_SYSTEM_PROMPT,
                checkpointer=MemorySaver()
            )

    # --- planning ---
    def _plan(self, request: str) -> list[str]:
        msg = self.llm.invoke([
            SystemMessage(content=PLANNER_SYSTEM_PROMPT),
            HumanMessage(content=request)
        ])
        data = _coerce_json(getattr(msg, "content", str(msg)))
        if data and isinstance(data.get("plan"), list):
            return [str(s) for s in data["plan"] if str(s).strip()][: self.max_steps]
        return []
    
    def _replan(self, state: PlanState, last_executor_msg: str) -> tuple[bool, str | list[str]]:
        msg = self.llm.invoke([
            SystemMessage(content=REPLANNER_SYSTEM_PROMPT),
            HumanMessage(content=json.dumps({
                "request": state.reequest,
                "plan": state.plan,
                "executor_last_message": last_executor_msg[-3000:]
            }))
        ])
        data = _coerce_json(getattr(msg, "content", str(msg)))
        if not data:
            return True, last_executor_msg
        if data.get("done"):
            return True, str(data.get("answer") or last_executor_msg)
        nxt = data.get("next_steps") or []
        if not isinstance(nxt, list):
            return True, last_executor_msg
        return False, [str(s) for s in nxt if str(s).strip()][: 3]
    
    # --- execution ---
    def _run_step(self, step: str, thread_id: str, state: PlanState) -> str:
        cfg = {"configurable": {"thread_id": thread_id}}
        result = self._executor.invoke(
            {"messages": [("user", f"PLAN STEP: {step}\n\n ORIGINAL REQUEST: {state.reequest}")]},
            config=cfg,
        )
        for m in result["messages"]:
            for tc in (getattr(m, "tool_calls", None) or []):
                state.transcript.append(f"{tc.get('name')}({tc.get('args'))[:1600]}")
            last = result["messages"][-1]
            return last.content if hasattr(last, "content") else str(last)
        
    ### --- public API (mirrors create_react_agent.invoke) ---
    def invoke(self, payload: dict, config: dict | None = None) -> dict:
        cfg = config or {"configurable": {"thread_id": "plan-default"}}
        thread_id = cfg["configurable"]["thread_id"]
        request = payload["messages"][-1][1] if payload["messages"] else ""
        state = PlanState(reequest=request)

        state.plan = self._plan(request)
        if not state.plan:
            # planner failed -> bare ReAct, single shot
            res = self._executor.invoke(payload, config=cfg)
            return res
        
        steps_done = 0
        last_msg = ""
        while state.plan and steps_done < self.max_steps:
            step = state.plan.pop(0)
            last_msg = self._run_step(step, thread_id, state)
            steps_done += 1
            if not state.plan:
                done, decision = self._replan(state, last_msg)
                if done:
                    state.answer = str(decision)
                    break
                state.plan = list(decision) if isinstance(decision, list) else []

        if not state.answer:
            state.answer = last_msg or "I'm not sure how to answer that."

        # Match the shape create_react_agent returns so callers (Streamlit/demo)
        # still get .messages with tool_calls inspectable.
        from langchain_core.messages import AIMessage, HumanMessage as HM
        synthetic = [HM(content=request)]
        if state.transcript:
            synthetic.append(AIMessage[content=f"content=f"plan trace: {' -> '.join(state.transcript)}]"))
        synthetic.append(AIMessage(content=state.answer))
        return {"messages": synthetic, "plan" : state.plan, "transcript": state.transcript}


    def build_plan_agent() -> PlanExecuteAgent:
        return PlanExecuteAgent(max_steps=settings().planner_max_steps)
            