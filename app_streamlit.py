"""Streamlit chat UI: 'streamlit run app_streamlit.py' to run."""
from __future__ import annotations
import os
import uuid

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from src.agent import build_agent, llm_label # noqa: E402
from src.rag import build_index # noqa: E402
from src.agent.prompt_library import (
    PROMPT_LIBRARY,
    PROMPT_PRINCIPLES,
    coach_prompt
)


st.set_page_config(page_title="Agentic AI Coach", page_icon="🤖", layout="wide")
st.title("🤖 Agentic AI Coach")
st.caption(f"LLM: **{llm_label()}** * Mode: **{settings().agent_mode}**")

with st.sidebar:
    st.header("Agentic AI Coach")
    mode = st.radio (
        "Mode",
        ["react", "plan"],
        index=0 if settings().agent_mode == "react" else 1,
        horizontal=True,
        help="ReAct: single-loop think+act. Plan: planner -> executor -> replanner."
    )
    if mode != settings().agent_mode:
        os.environ["AGENT_MODE"] = mode
        for k in ("agent",):
            st.session_state.pop(k, None)
        st.rerun()

    st.header("Knowledge base")
    if st.button("Rebuild /docs index"):
        with st.spinner("Rebuilding index..."):
            n = build_index("docs")
        st.success(f"Index rebuilt with {n} chunks.") if n else st.warning("No docs found in ./docs.")

    st.header("Session")
    if st.button("New conversation"):
        for k in ("agent", "thread_id", "history", "prefill", "coach_result"):
            st.session_state.pop(k, None)
        st.rerun()

    st.header("Prompt library")
    category = st.selectbox(
        "Category", 
        list(PROMPT_LIBRARY.keys()),
        key="lib_category"
    )
    titles = [p["title"] for p in PROMPT_LIBRARY[category]]
    title = st.selectbox("Template", titles, key="lib_title")
    selected = next(p for p in PROMPT_LIBRARY[category] if p["title"] == title)
    st.caption(" * ".join(f"`{t}`" for t in selected.get("tags", [])))
    st.code(selected["prompt"], language="markdown")
    if st.button("Use this template", use_container_width=True):
        st.session_state.prefill = selected["prompt"]
        st.rerun()

if "agent" not in st.session_state:
    st.session_state.agent = build_agent()
    st.session_state.thread_id = str(uuid.uuid4())
    st.session_state.history = [] # list of (role, content) tuples

# -------------------- Prompt coach --------------------
with st.expander("Improve my prompt (coach)"):
    st.caption(
        "Paste a draft and the coach will rewrite it to be more concrete, "
        "name the right tools, and call out missing inputs."
    )
    draft = st.text_area(
        "Your draft", 
        value=st.session_state.get("coach_draft", ""), 
        height=100,
        key="coached_draft_input"
    )
    cols = st.columns([1, 1, 3])
    if cols[0].button("Improve"):
        with st.spinner("Coaching..."):
            st.session_state.coach_result = coach_prompt(draft)
    if cols[1].button("Show principles"):
        st.session_state.coach_result = {
            "improved": "",
            "rationale": "",
            "missing": [],
            "principles": PROMPT_PRINCIPLES
        }
    
    res = st.session_state.get("coach_result")
    if res:
        if res.get("improved"):
            st.markdown("**Improved prompt:**")
            st.code(res["improved"], language="markdown")
            if st.button("Use improved prompt", key="use_improved"):
                st.session_state.prefill = res["improved"]
                st.rerun()
        if res.get("rationale"):
            st.markdown("**What changed:**")
            st.markdown(res["rationale"])
        if res.get("missing"):
            st.markdown("**Still Missing inputs/tools:**")
            for m in res["missing"]:
                st.markdown(f"- {m}")
        if res.get("principles"):
            with st.expander("Prompt-engineering principles"):
                for p in res["principles"]:
                    st.markdown(f"- {p}")

for role, content in st.session_state.history:
    with st.chat_message(role):
        st.markdown(content)

prefill = st.session_state.pop("prefill", None)
if prefill:
    st.info("Template loaded into the chat box below - edit placeholders, then send.")
prompt = st.chat_input("Ask the agent...")
if prefill and not prompt:
    prompt = prefill
if prompt:
    st.session_state.history.append(("user", prompt))
    with st.chat_message("user"):
        st.markdown(prompt)

    cfgG = ("configurable": ("thread_id": st.session_state.thread_id))
    with st.chat_message("assistant"):
        trace_box = st.status("Thinking-", expanded=False)
        tool_lines: list[str] = []
        result = None
        try:
            for mode, delta in in st.session_state.agent.stream[
                {"messages": [("user", prompt)]}, config=cfg
            ):
                if node == "__final__":
                    result = delta
                    break
                if node == "__error__":
                    trace_box.update(label=f"Error: {delta.get('error')}", state="error")
                    result = ("messages": [])
                    break
                # Surface tool calls / tool results as they arrive.
                msgs = delta.get("messages") if isinstance(delta, dict) else None
                if not msgs:
                    continue
                for m in msgs:
                    tcs = getattr(m, "tool_calls", None)
                    if tcs:
                        for tc in tcs:
                            args_preview = str(tc.get("args", ""))[:160]
                            line = f"**{tc['name']}** called with `{args_preview}`"
                            tool_lines.append(line)
                            trace_box.write(line)
                    elif type(m).__name__ == "ToolMessage":
                        body = str(getattr(m, "content", ""))[:300].replace("\n", " ")
                        line = f"4 _{getattr(m, "name", "tool")}_ returned `{body}`"
                        tool_lines.append(line)
                        trace_box.write(line)
        except Exception as e: # noqa: BLE001
            trace_box.update(label=f"{type(e).__name__}: {e}", state="error")
            result = {"messages": []}
        
        trace_box.update(
            label = f"Done. * {len(tool_lines)} tool calls made.*",
            state="complete"
        )

        if result and result.get("transcript"):
            with st.expander(" Plane trace"):
                st.markdown("\n".join(f"- `{s}`" for s in result["transcript"]))
        
        msgs = result.get("messages") if result else []
        final = msgs[-1] if msgs else "_(no response)_"
        final = final if isinstance(final, str) else str(final)
        st.markdown(final)
        st.session_state.history.append(("assistant", final))
        