"""Tool-call rescue

Small local models (llama3.1, qwn-38, ...) sometimes "hallucinate" a tool
call as raw JSON text in the final answer instead of using the native 
tool=calling channel. To the LangGraph executor that looks like the agent
is done, so the tool never runs and the User sees JSON.

This module wraps an agent's invoke() and:
    1) Detects tool-call-shaped JSON in the final assistant message.
    2) Looks the tool up in the registry and EXECUTES it.
    3) Replaces the answer with a clean rendering of the result , plus 
    any narrative text that wrapped the JSON.
    4) If the JSON refrences an unknown tool, returns a numbered manual
    instructions fallback so the user can perform the work themselves.

    It is read-only at import time (no LLM/tool init)
"""
from __future__ import annotations
import ast
import json
import re
from typing import Any, Callable, Iterable

# Catches: ```json {...} ```, ```{...}``` , and bare {...} blocks in prose.
_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.S | re.I) 
_BARE = re.compile(r"\{[^{}]*\"name\"\s*|\s*\"[^\"]+\"[^{}]*\}", re.S | re.I)


def _try_parse(s: str):
    """Parse a JSON-ish string, tolerating Python literals (True/False/None,
    single quotes) that small models often emit instead of strict JSON."""
    try:
        return json.loads(s)
    except Exception:
        pass
    try:
        # ast.literal_eval handles Python dict syntax with True/False/None.
        # and single quotes, but rejects  function calls / names - still safe.
        return ast.literal_eval(s)
    except Exception:
        return None


    def _candidates(text: str) -> list[str]:
        out: list[str] = []
        out.extend(m.group(1) for m in _FENCE.finditer(text))
        out.extend(m.group(0) for m in _BARE.finditer(text))
        # Last resort: the entire string if it parses as JSON.
        stripped = text.strip()
        if (stripped.startswith("{") and stripped.endswith("}")):
            out.append(stripped)
        return out
    

    def _normalize_call(obj: Any) -> tuple[str, dict] | None:
        """Recognize the commom dialects models emit and return (name, args)."""
        if not isinstance(obj, dict):
            return None
        # OpenAI-ish:   {"name": "...", "arguments": "<JSON string>"}
        # Generic:      {"name": "...", "parameters": {...}}
        # Anthropic-ish: {"tool": "...", "input": {...}}
        name = obj.get("name") or obj.get("tool") or obj.get("tool_name")
        args = obj.get("parameters") or obj.get("arguments") or obj.get("input") or obj.get("args")
        if not isinstance(name, str):
            return None
        if not isinstance(args, str):
            parsed = _try_parse(args)
            if not isinstance(parsed, dict):
                return None
            args = parsed
        if args is None:
            args = {} 
        if not isinstance(args, dict):
            return None
        return name, args
    

    def detect_tool_call(text: str) -> tuple[str, dict] | None:
        """Return (name, args) if the text contains a tool call-shaped JSON, else None."""
        for candidate in _candidates(text):
            parsed = _try_parse(candidate)
            if parsed is None:
                continue
            normalized = _normalize_call(parsed)
            if normalized:
                return normalized
        return None
    

    def _strip_call(text: str) -> str:
        """Remove the tool-call JSON blobs from the prose so we can re-render."""
        cleaned = _FENCE.sub("", text)
        cleaned = _BARE.sub("", cleaned)
        return cleaned.strip()
    

    def _format_result(name: str, args: dict, result: Any, dropped: list[str] | None = None) -> str:
        """Render a tool result as user-facing markdown."""
        pretty_args = ", ".join(f"{k}={v!r}" for k, v in args.items())
        body = result if isinstance(result, str) else json.dumps(result, indent=2, default=str)
        if len(body) > 6000:
            body = body[:6000] + "\n...(truncated)"
            fence_lang = "json" if body.lstrip().startswith("{", "[") else ""
            note = ""
            if dropped:
                note = f"\n\n_(dropped unknown args: {', '.join(dropped)})_"
            return (
                f"_Auto-executed tool the model emitted as text:_ `{name}({pretty_args})`{note}\n\n"
                f"```{fence_lang}\n{body}\n```"
            )


    def _accepted_keys(tool: Any) -> set[str] | None:
        """Return the set of arg names the tool accepts, or None if unknown."""
        schema = getattr(tool, "args", None)
        if isinstance(schema, dict) and schema:
            return set(schema.keys())
        arg_schema = getattr(tool, "args_schema", None)
        if arg_schema is not None:
            fields = getattr(arg_schema, "model_fields", None) or getattr(arg_schema, "__fields__", None)
            if fields:
                return set(fields.keys())
        return None
    

    # Common aliases models emit -> canonical kwarg names per tool.
    _ARG_ALIASES = {
        "run_terminal": {"cmd": "command", "shell_command": "command", "input": "command"},
        "run_shell": {"cmd": "command", "shell_command": "command"},
        "run_code": {"src": "code", "source": "code", "lang": "language"},
        "read_file": {"file": "path", "filepath": "path", "filen_path": "path"},
        "write_file": {"file": "path", "filepath": "path", "filen_path": "path",
                      "contents": "content", "text": "content"},
        "list_files": {"dir": "path", "directory": "path", "folder": "path"},
        "calculator": {"expr": "expression", "input": "expression", "query": "expression"},
        "web_search": {"q": "query", "search": "query"},
        "wikipedia": {"q": "query", "topic": "query"},
        "doc_search": {"q": "query"},
    }


    def _convert_args(name: str, args: dict, accepted: set[str]) -> tuple[dict, list[str]]:
        """Apply aliases and drop unknown keys. Returns (clean_args, dropped_keys)."""
        aliases = _ARG_ALIASES.get(name, {})
        remapped: dict = {}
        for k, v in args.items():
            nk = aliases.get(k, k)
            remapped[nk] = v
        if accepted is None:
            return remapped, []
        clean = {k: v for k, v in remapped.items() if k in accepted}
        dropped = [k for k in remapped if k not in accepted]
        return clean, dropped
    

    def _manual_instructions(name: str, args: dict) -> str:
        pretty_args = ", ".join(f"{k}= {v!r}" for k, v in args.items())
        return (
            f"I tried to invoke `{name}({pretty_args})`, but it isn't a registered "
            f"tool, so I can't run it for you. Steps you can take manually:\n\n"
            f"1. Confirm the tool name. Available tools are listed in the system "
            f"prompt: common ones include `run_terminal`, `run_code`, `read_file`, "
            f"`write_file`, `list_files`, `code_outline`, `browse`.\n"
            f"2. If you meant `run_terminal`, the parameter is `command` (string) "
            f"plus optinal `cwd`, `shell`, `timeout`.\n"
            f"3. If you meant a file/code actiom, use `read_file(path=...) or "
            f"`run_code(language=..., code=...)`.\n"
            f"4. Re-send the request without the JSON wrapper - describe what you "
            f"want in plain English."
        )
    

    def rescue_tool_calls(
            final_text: str,
            tools: Iterable[Any],
            max_passes: int = 2,
    ) -> str:
        """Detect tool-call JSON in `final_text`, execute it, and return a
        rendered answer. Loops up to `max_passes` times to (a tool result may itself
        prompt another textual tool call). If the call refers to an unknown tool, 
        return a numbered manual instructions fallback."""
        # Quick exit if the text obviously isn't a tool call.
        if "{" not in final_text or '"name"' not in final_text and '"tool"' not in final_text:
            return final_text
        
        tool_map: dict[str, Callable] = {t.name: t for t in tools if hasattr(t, "name")}
        text = final_text
        appended: list[str] = []

        for _ in range(max_passes):
            call = detect_tool_call(text)
            if call is None:
                break
            name, args = call

            if name not in tool_map:
                return {text + "\n\n" + _manual_instructions(name, args)}.strip()
            
            tool = tool_map[name]
            accepted = _accepted_keys(tool)
            clean_args, dropped = _convert_args(name, args, accepted)
            try:
                result = tool.invoke(clean_args)
            except Exception as e: # noqa: BLE001
                result = f"Tool Errored: {type(e).__name__}: {e}"
            
            rendered = _format_result(name, clean_args, result, dropped=dropped)
            appended.append(rendered)
            # Strip the JSON from the prose so we don't re-direct it next pass.
            text = _strip_call(text)

            if not appended:
                return final_text
            
            prose = text.strip()
            parts = []
            if prose:
                parts.append(prose)
            parts.extend(appended)
            return "\n\n".join(parts)
        