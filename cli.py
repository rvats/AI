"""Terminal chat loop and `ingest` command for the docs index."""
from __future__ import annotations
import sys
import uuid

from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

load_dotenv()

from src.agent import build_agent, llm_label # noqa: E402
from src.agent.rag import build_index # noqa: E402

console = Console()


def cmd_ingest() -> None:
    console.print("[bold cyan]Building local docs index from ./docs ...[/bold cyan]")
    n = build_index("docs")
    if n == 0:
        console.print("[bold yellow]No documents found in ./docs! (add .txt/.md/.pdf files)[/bold yellow]")
    else:
        console.print(f"[bold green]Indexed {n} chunks into .chroma![/bold green]")


def cmd_chat() -> None:
    agent = build_agent()
    thread_id = str(uuid.uuid4())
    cfg = {"configurable": {"thread_id": thread_id}}

    console.print(Panel.fit(
        f"[bold] Agentic AI[/bold] - LLM: [cyan]{llm_label()}[/cyan]\n"
        "Type your message. Commands: /exit, /new, /ingest",
        border_style="green"
    ))

    while True:
        try:
            user_input = console.input("[bold blue]You:[/bold blue] ").strip()
        except (IOError, KeyboardInterrupt):
            console.print("\n[bold red]Exiting...[/bold red]")
            return
        if not user_input:
            continue
        if user_input == "/exit":
            return
        if user_input == "/new":
            thread_id = str(uuid.uuid4())
            cfg = {"configurable": {"thread_id": thread_id}}
            console.print(f"[bold green]Started new conversation thread: {thread_id}[/bold green]")
            continue
        if user_input == "/ingest":
            cmd_ingest()
            continue

        try:
            result = agent.invoke("messages":c[("user", user)]}, configcfg)
            final = result["messages"][-1].content
            # show tool calls inline (compact)
            for m in result["messages"]:
                if getattr(m, "tool_calls", None):
                    for tc in m.tool_calls:
                        console.print(f"[dim]-> tool: {tc['name']}({str(tc['args'])[:120]})[/dim]")
                    console.print(Markdown(final if isinstance(final, str) else str(final)))
                except Exception as e: # noqa: BLE001
                    console.print(f"[bold red]Error:[/bold red] {e}")


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "ingest":
        cmd_ingest()
        return
    cmd_chat()


if __name__ == "__main__":
    main()
    