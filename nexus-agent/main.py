"""
Nexus Agent — Local Agentic AI (Ollama or Anthropic)
Run: python main.py
"""
import os, sys, json, tempfile, subprocess, threading, asyncio, time
from pathlib import Path
from typing import Generator

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from duckduckgo_search import DDGS
    HAS_DDG = True
except ImportError:
    HAS_DDG = False

app = FastAPI(title="Nexus Agent")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

BASE_DIR = Path(os.getcwd())

# ─── Config ────────────────────────────────────────────────────────────────────

CONFIG = {
    "backend": "ollama",            # "ollama" | "anthropic"
    "ollama_url": "http://localhost:11434",
    "ollama_model": "qwen2.5:7b",   # any model with tool support
    "anthropic_key": os.getenv("ANTHROPIC_API_KEY", ""),
    "anthropic_model": "claude-sonnet-4-6",
}

# ─── Tool Definitions (Anthropic format — converted as needed) ─────────────────

TOOLS_ANTHROPIC = [
    {
        "name": "list_directory",
        "description": "List files and directories at a given path. Use '.' for current directory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path (relative to working dir)"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "read_file",
        "description": "Read the full contents of a file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to read (relative to working dir)"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "write_file",
        "description": "Write or overwrite a file with given content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path (relative to working dir)"},
                "content": {"type": "string", "description": "Content to write"}
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "execute_python",
        "description": "Execute Python code and return stdout/stderr. Great for calculations and data analysis.",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python code to run"}
            },
            "required": ["code"]
        }
    },
    {
        "name": "web_search",
        "description": "Search the internet for current information.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "max_results": {"type": "integer", "description": "Number of results (default 5)", "default": 5}
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_system_info",
        "description": "Get OS, Python version, installed packages, and working directory info.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
]

# OpenAI-compatible format (used for Ollama)
TOOLS_OPENAI = [
    {
        "type": "function",
        "function": {
            "name": t["name"],
            "description": t["description"],
            "parameters": t["input_schema"],
        }
    }
    for t in TOOLS_ANTHROPIC
]

# ─── Tool Execution ────────────────────────────────────────────────────────────

def execute_tool(name: str, args: dict) -> str:
    try:
        if name == "list_directory":
            p = BASE_DIR / args.get("path", ".")
            if not p.exists():
                return f"Error: '{args.get('path')}' does not exist"
            rows = []
            for item in sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name)):
                if item.is_dir():
                    rows.append(f"[DIR]  {item.name}/")
                else:
                    rows.append(f"[FILE] {item.name}  ({item.stat().st_size:,} bytes)")
            return "\n".join(rows) if rows else "(empty directory)"

        elif name == "read_file":
            p = BASE_DIR / args["path"]
            if not p.exists():
                return f"Error: '{args['path']}' does not exist"
            text = p.read_text(encoding="utf-8", errors="replace")
            if len(text) > 8000:
                return text[:8000] + "\n\n[...truncated]"
            return text

        elif name == "write_file":
            p = BASE_DIR / args["path"]
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(args["content"], encoding="utf-8")
            return f"Written {len(args['content']):,} chars to {p.relative_to(BASE_DIR)}"

        elif name == "execute_python":
            code = args["code"]
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
                f.write(code)
                tmp = f.name
            try:
                res = subprocess.run(
                    [sys.executable, tmp],
                    capture_output=True, text=True, timeout=30, cwd=str(BASE_DIR)
                )
                out = res.stdout or ""
                if res.stderr:
                    out += f"\n[stderr]\n{res.stderr}"
                if res.returncode != 0:
                    out += f"\n[exit {res.returncode}]"
                return out.strip() or "(no output)"
            except subprocess.TimeoutExpired:
                return "Error: timed out after 30s"
            finally:
                os.unlink(tmp)

        elif name == "web_search":
            if not HAS_DDG:
                return "duckduckgo-search not installed. Run: pip install duckduckgo-search"
            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(args["query"], max_results=args.get("max_results", 5)):
                    results.append(f"**{r['title']}**\n{r['href']}\n{r['body']}")
            return "\n\n---\n\n".join(results) if results else "No results found."

        elif name == "get_system_info":
            import platform
            info = {
                "OS": f"{platform.system()} {platform.release()} ({platform.machine()})",
                "Python": sys.version.split()[0],
                "Working Directory": str(BASE_DIR),
                "Backend": CONFIG["backend"],
                "Model": CONFIG["ollama_model"] if CONFIG["backend"] == "ollama" else CONFIG["anthropic_model"],
            }
            try:
                import pkg_resources
                pkgs = [f"{p.project_name}=={p.version}" for p in pkg_resources.working_set]
                info["Key Packages"] = [p for p in pkgs if any(
                    k in p.lower() for k in ["anthropic", "fastapi", "numpy", "pandas", "openai", "ollama"]
                )]
            except Exception:
                pass
            return json.dumps(info, indent=2)

        else:
            return f"Unknown tool: {name}"

    except Exception as e:
        return f"Tool error — {type(e).__name__}: {e}"

# ─── System Prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are Nexus, a capable local AI agent running on the user's laptop.
You have tools to explore the file system, run Python code, search the web, and inspect the system.

Guidelines:
- Think step by step and use tools when needed to complete tasks
- When writing code, execute it to show real results
- Use relative paths (the working directory is the project root)
- Format your responses clearly with markdown
- Be concise but thorough
"""

# ─── Anthropic Agent ───────────────────────────────────────────────────────────

def run_agent_anthropic(user_message: str) -> Generator[str, None, None]:
    import anthropic

    key = CONFIG["anthropic_key"]
    if not key:
        yield f"data: {json.dumps({'type':'error','message':'No Anthropic API key. Go to Settings and add your key.'})}\n\n"
        return

    client = anthropic.Anthropic(api_key=key)
    messages = [{"role": "user", "content": user_message}]

    def ev(d): return f"data: {json.dumps(d)}\n\n"

    for _ in range(10):
        with client.messages.stream(
            model=CONFIG["anthropic_model"],
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS_ANTHROPIC,
            messages=messages,
        ) as stream:
            tool_uses = []
            cur = -1

            for event in stream:
                t = event.type
                if t == "content_block_start":
                    blk = event.content_block
                    if blk.type == "tool_use":
                        tool_uses.append({"id": blk.id, "name": blk.name, "raw": "", "input": {}})
                        cur = len(tool_uses) - 1
                        yield ev({"type": "tool_start", "name": blk.name, "id": blk.id})
                    else:
                        cur = -1
                elif t == "content_block_delta":
                    d = event.delta
                    if d.type == "text_delta":
                        yield ev({"type": "text", "content": d.text})
                    elif d.type == "input_json_delta" and cur >= 0:
                        tool_uses[cur]["raw"] += d.partial_json
                elif t == "content_block_stop" and cur >= 0:
                    try:
                        tool_uses[cur]["input"] = json.loads(tool_uses[cur]["raw"] or "{}")
                    except Exception:
                        pass

            final = stream.get_final_message()
            messages.append({"role": "assistant", "content": final.content})

            if final.stop_reason != "tool_use" or not tool_uses:
                yield ev({"type": "done"})
                return

            results = []
            for tc in tool_uses:
                yield ev({"type": "tool_call", "name": tc["name"], "input": tc["input"], "id": tc["id"]})
                result = execute_tool(tc["name"], tc["input"])
                yield ev({"type": "tool_result", "name": tc["name"],
                          "result": result[:1500] + ("…" if len(result) > 1500 else ""), "id": tc["id"]})
                results.append({"type": "tool_result", "tool_use_id": tc["id"], "content": result})

            messages.append({"role": "user", "content": results})

    yield f"data: {json.dumps({'type':'done'})}\n\n"

# ─── Ollama Agent (OpenAI-compatible endpoint) ─────────────────────────────────

def run_agent_ollama(user_message: str) -> Generator[str, None, None]:
    from openai import OpenAI

    base_url = CONFIG["ollama_url"].rstrip("/") + "/v1"
    model = CONFIG["ollama_model"]

    try:
        client = OpenAI(base_url=base_url, api_key="ollama")
        # quick connectivity check
        client.models.list()
    except Exception as e:
        url = CONFIG["ollama_url"]
        msg = f"Cannot reach Ollama at {url}. Is Ollama running? ({e})"
        yield f"data: {json.dumps({'type':'error','message':msg})}\n\n"
        return

    def ev(d): return f"data: {json.dumps(d)}\n\n"

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    for _ in range(10):
        # Accumulate full response from stream
        full_text = ""
        tool_calls_acc: dict[int, dict] = {}
        finish_reason = None

        try:
            stream = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=TOOLS_OPENAI,
                tool_choice="auto",
                stream=True,
            )

            for chunk in stream:
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                finish_reason = choice.finish_reason or finish_reason
                delta = choice.delta

                if delta.content:
                    full_text += delta.content
                    yield ev({"type": "text", "content": delta.content})

                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in tool_calls_acc:
                            call_id = tc.id or f"call_{idx}_{int(time.time())}"
                            tool_calls_acc[idx] = {"id": call_id, "name": "", "arguments": "", "started": False}
                        if tc.function:
                            if tc.function.name:
                                tool_calls_acc[idx]["name"] += tc.function.name
                            if tc.function.arguments:
                                tool_calls_acc[idx]["arguments"] += tc.function.arguments
                            # emit tool_start once we have a name
                            if tool_calls_acc[idx]["name"] and not tool_calls_acc[idx]["started"]:
                                tool_calls_acc[idx]["started"] = True
                                yield ev({"type": "tool_start",
                                          "name": tool_calls_acc[idx]["name"],
                                          "id": tool_calls_acc[idx]["id"]})

        except Exception as e:
            yield ev({"type": "error", "message": f"Ollama error: {e}"})
            return

        # Build assistant message for history
        assistant_msg: dict = {"role": "assistant", "content": full_text or None}
        if tool_calls_acc:
            assistant_msg["tool_calls"] = [
                {
                    "id": v["id"],
                    "type": "function",
                    "function": {"name": v["name"], "arguments": v["arguments"]},
                }
                for v in tool_calls_acc.values()
            ]
        messages.append(assistant_msg)

        if not tool_calls_acc or finish_reason == "stop":
            yield ev({"type": "done"})
            return

        # Execute tools
        for v in tool_calls_acc.values():
            try:
                args = json.loads(v["arguments"]) if v["arguments"] else {}
            except Exception:
                args = {}

            yield ev({"type": "tool_call", "name": v["name"], "input": args, "id": v["id"]})
            result = execute_tool(v["name"], args)
            yield ev({"type": "tool_result", "name": v["name"],
                      "result": result[:1500] + ("…" if len(result) > 1500 else ""), "id": v["id"]})

            messages.append({"role": "tool", "tool_call_id": v["id"], "content": result})

    yield f"data: {json.dumps({'type':'done'})}\n\n"

# ─── Dispatch ──────────────────────────────────────────────────────────────────

def run_agent(user_message: str) -> Generator[str, None, None]:
    if CONFIG["backend"] == "anthropic":
        yield from run_agent_anthropic(user_message)
    else:
        yield from run_agent_ollama(user_message)

# ─── API Routes ────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root():
    html = (Path(__file__).parent / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(html)

@app.get("/api/config")
async def get_config():
    return {
        "backend": CONFIG["backend"],
        "ollama_url": CONFIG["ollama_url"],
        "ollama_model": CONFIG["ollama_model"],
        "anthropic_model": CONFIG["anthropic_model"],
        "has_anthropic_key": bool(CONFIG["anthropic_key"]),
    }

@app.post("/api/config")
async def set_config(request: Request):
    body = await request.json()
    if "backend" in body:
        CONFIG["backend"] = body["backend"]
    if "ollama_url" in body:
        CONFIG["ollama_url"] = body["ollama_url"].rstrip("/")
    if "ollama_model" in body:
        CONFIG["ollama_model"] = body["ollama_model"]
    if "anthropic_key" in body and body["anthropic_key"]:
        CONFIG["anthropic_key"] = body["anthropic_key"]
    if "anthropic_model" in body:
        CONFIG["anthropic_model"] = body["anthropic_model"]
    return {"status": "ok", "config": {k: v for k, v in CONFIG.items() if k != "anthropic_key"}}

@app.get("/api/ollama/models")
async def ollama_models():
    """List models available in the running Ollama instance."""
    try:
        from openai import OpenAI
        client = OpenAI(base_url=CONFIG["ollama_url"].rstrip("/") + "/v1", api_key="ollama")
        models = [m.id for m in client.models.list().data]
        return {"models": models, "running": True}
    except Exception as e:
        return {"models": [], "running": False, "error": str(e)}

@app.post("/api/chat")
async def chat(request: Request):
    body = await request.json()
    message = body.get("message", "").strip()
    if not message:
        return JSONResponse({"error": "Empty message"}, status_code=400)

    loop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def worker():
        try:
            for chunk in run_agent(message):
                asyncio.run_coroutine_threadsafe(queue.put(chunk), loop)
        except Exception as e:
            err = json.dumps({"type": "error", "message": str(e)})
            asyncio.run_coroutine_threadsafe(queue.put(f"data: {err}\n\n"), loop)
        finally:
            asyncio.run_coroutine_threadsafe(queue.put(None), loop)

    threading.Thread(target=worker, daemon=True).start()

    async def generate():
        while True:
            item = await queue.get()
            if item is None:
                break
            yield item

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"}
    )

# ─── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    print("\nNexus Agent running at http://localhost:8000")
    print(f"Backend: {CONFIG['backend']} | Model: {CONFIG['ollama_model'] if CONFIG['backend']=='ollama' else CONFIG['anthropic_model']}\n")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")
