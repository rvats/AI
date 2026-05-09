"""MCP server: web browser automation via Playwright (async API).

Run standalone:
    python -m mcp_local.servers.browser_server

Each MCP tool call runs in a fresh subprocess, so this server exposes a 
single self-contained `browser` tool that performs an entire scripted 
session (open, navigate, click, fill, capture) in one call.

Browser preference (with automatic fallback):
    BROWSER_PREFERRED=chrome|msedge|chromium|firefox|webkit
If the requested channel isn't installed, fall back to bundled chromium.
Headless by default, set BROWSER_HEADLESS=false to see a window.
"""
from __future__ import annotations
import asyncio
import os
import time
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("agentic-browser")


def _workspace_root() -> Path:
    return Path(os.getenv("AGENT_WORKSPACE", ".")).resolve()


def _bool_env(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


async def _launch(pref: str, headless: bool):
    from playwright.async_api import async_playwright

    pw = await async_playwright().start()
    
    attempts: list[tuple[str, dict]] = []
    p = (pref or "").strip().lower()
    if p in ("chrome", "google-chrome"):
        attempts.append(("chromium", {"channel": "chrome"}))
    elif p in ("msedge", "edge"):
        attempts.append(("chromium", {"channel": "msedge"}))
    elif p == "firefox":
        attempts.append(("firefox", {}))
    elif p == "webkit":
        attempts.append(("webkit", {}))
    elif p and p != "chromium":
        attempts.append(("chromium", {"channel": p}))
    attempts.append(("chromium", {}))  # fallback to bundled chromium

    last_err: Exception | None = None
    for engine, kwargs in attempts:
        try:
            launcher = getattr(pw, engine)
            browser = await launcher.launch(headless=headless, **kwargs)
            return (
                pw,
                browser,
                engine,
                kwargs.get("channel") or engine,
                (engine, kwargs) != attempts[0]
            )
        except Exception as e: # noqa BLE001
            last_err = e
            continue

        await pw.stop()
    raise RuntimeError(
        f"Failed to launch any browser. Last error: {last_err}. "
        "Make sure you ran playwright install chromium"
    )


def _safe_path(rel: str) -> Path:
    root = _workspace_root()
    target = (root / rel).resolve()
    if root != target and root not in target.parents:
        raise ValueError(f"Path {target} is outside the workspace root {root}")
    return target


@mcp.tool()
async def browse(
    url: str,
    actions: list[dict] | None = None,
    browser: str = "",
    headless: bool = True,
    timeout_ms: int = 30000
) -> dict:
    """Open a browser, navigate to `url`, run a sequence of `actions`, retutn results.

    `browser` is one of "chrome", "msedge", "chromium", "firefox", "webkit". Falls back
    to bundled Chromium if the requested channel isn't installed.

    Each action is a dict with a "type", e.g.:
        {"type": "navigate",    "url": "..."}
        {"type": "click",       "selector": "a.signin"}
        {"type": "fill",        "selector": "#q", "value": "hello"}
        {"type": "press",       "selector": "#q", "key": "Enter"}
        {"type": "wait",        "ms": 10000}
        {"type": "wait_for",    "selector": ".result"}
        {"type": "get_text",    "selector": "h1", "max_chars": 2000}
        {"type": "get_title"}
        {"type": "eval",        "expression": "document.title"}
        {"type": "screenshot",  "path": "relative/path.png"}    # path optional
    """
    pref = browser or os.getenv("BROWSER_PREFERRED", "chromium")
    headless = headless if headless is not None else _bool_env("BROWSER_HEADLESS", True)
    actions = actions or []

    pw, browser_obj, engine, channel, fellback = await _launch(pref, headless)
    try:
        context = await browser_obj.new_context()
        page = await context.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)

        results = list[dict] = []
        for i, act in enumerate(actions):
            t = (act.get("type") or "").lower()
            try:
                if t == "navigate":
                    await page.goto(act["url"], wait_until="domcontentloaded", timeout=timeout_ms)
                    results.append({"step": i, "type": t, "ok": True, "url": page.url})
                elif t == "click":
                    await page.click(act["selector"], timeout=5000)
                    await asyncio.sleep(0.3)  # let page update after click
                    results.append({"step": i, "type": t, "ok": True, "url": page.url})
                elif t == "fill":
                    await page.fill(act["selector"], act["value"], timeout=5000)
                    results.append({"step": i, "type": t, "ok": True})
                elif t == "press":
                    await page.press(act["selector"], act["key"], timeout=5000)
                    await asyncio.sleep(0.3)
                    results.append({"step": i, "type": t, "ok": True})
                elif t == "wait":
                    await asyncio.sleep(int(act.get("ms", 5000)) / 1000)
                    results.append({"step": i, "type": t, "ok": True})
                elif t == "wait_for":
                    await page.wait_for_selector(
                        act["selector"], timeout=int(act.get("timeout_ms", 10000))
                    )
                    results.append({"step": i, "type": t, "ok": True})
                elif t == "get_text":
                    sel = act.get("selector", "body")
                    text = await page.inner_text(sel, timeout=5000)
                    limit = int(act.get("max_chars", 4000))
                    truncated = len(text) > limit
                    results.append({
                        "step": i, "type": t, "ok": True, "selector": sel,
                        "text": text[:limit] + ("\n...(truncated)" if truncated else ''),
                        "chars": len(text)
                    })
                elif t == "get_title":
                    results.append({
                        "step": i, "type": t, "ok": True, 
                        "title": await page.title(), "url": page.url
                    })
                elif t == "eval":
                    val = await page.evaluate(act["expression"])
                    results.append({"step": i, "type": t, "ok": True, "value": val})
                elif t == "screenshot":
                    rel = act.get("path") or f"demo_output-(int(time.time()-{i}.png"
                    target = _safe_path(rel)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    await page.screenshot(path=str(target), full_page=True)
                    results.append({
                        "step": i, "type": t, "ok": True, 
                        "path": str(target.relative_to(_workspace_root()))
                    })
                else:
                    results.append({"step": i, "type": t, "ok": False, 
                                    "error": f"Unknown action type: {t}"    })
            except Exception as e: # noqa BLE001
                results.append({"step": i, "type": t, "ok": False, "error": str(e)})
        
        return {
            "OK": True,
            "engine": engine,   
            "channel": channel,
            "fellback": fellback,
            "headless": headless,
            "final_url": page.url,
            "final_title": await page.title(),
            "actions": results
        }
    finally:
        try:
            await browser_obj.close()
        finally:
            await pw.stop()


    def main() -> None:
        mcp.run()


if __name__ == "__main__":
    main()
