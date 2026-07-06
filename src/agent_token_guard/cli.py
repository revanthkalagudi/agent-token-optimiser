"""AgentTokenGuard CLI — atg command entry point."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import print as rprint

from .memory import MemoryManager
from .indexer import RepoIndexer
from .compressor import OutputCompressor
from .metrics import MetricsEngine
from .doctor import Doctor
from .adapters import AgentsAdapter, ClaudeAdapter, CodexAdapter, CopilotAdapter, CursorAdapter

app = typer.Typer(
    name="atg",
    help="AgentTokenGuard — reduce LLM agent session token waste.",
    add_completion=False,
    no_args_is_help=True,
)

console = Console()

_AGENT_ADAPTERS = {
    "claude": ClaudeAdapter,
    "codex": CodexAdapter,
    "copilot": CopilotAdapter,
    "cursor": CursorAdapter,
    "agents": AgentsAdapter,
}
_VALID_AGENTS = set(_AGENT_ADAPTERS) | {"all"}


def _parse_agent_selection(raw: str) -> list[str]:
    requested = {a.strip().lower() for a in raw.split(",") if a.strip()}
    if not requested:
        return []
    unknown = requested - _VALID_AGENTS
    if unknown:
        valid = ", ".join(sorted(_VALID_AGENTS))
        console.print(f"[red]Unknown agents: {', '.join(sorted(unknown))}. Valid: {valid}.[/red]")
        raise typer.Exit(1)

    if "all" in requested:
        return sorted(_AGENT_ADAPTERS)
    return sorted(requested)


# ---------------------------------------------------------------------------
# atg init
# ---------------------------------------------------------------------------


@app.command()
def init(
    agents: Annotated[
        str,
        typer.Option(
            "--agents",
            "-a",
            help="Comma-separated adapters to enable: claude, codex, copilot, cursor, agents, all",
        ),
    ] = "all",
    root: Annotated[
        Optional[Path],
        typer.Option("--root", help="Repo root (defaults to current directory)"),
    ] = None,
) -> None:
    """Initialise AgentTokenGuard in a repo. Creates memory dirs, policies, and agent files."""
    root_path = root or Path.cwd()
    selected_agents = _parse_agent_selection(agents)
    if not selected_agents:
        console.print("[red]No adapters selected. Pass --agents with at least one platform.[/red]")
        raise typer.Exit(1)

    created: list[str] = []

    # Write policies
    compressor = OutputCompressor(root=root_path)
    compressor.write_policies()
    created += [
        ".agent-token-guard/rules/output-policy.md",
        ".agent-token-guard/rules/read-policy.md",
    ]

    # Ensure memory/index/metrics dirs exist
    for subdir in ("memory", "index", "metrics"):
        (root_path / ".agent-token-guard" / subdir).mkdir(parents=True, exist_ok=True)

    for name in selected_agents:
        adapter = _AGENT_ADAPTERS[name](root=root_path)
        created += adapter.generate()

    console.print(Panel.fit("[bold green]AgentTokenGuard initialised[/bold green]"))
    for path in created:
        console.print(f"  [green]✓[/green] {path}")

    console.print(
        "\n[dim]Next steps:[/dim]\n"
        "  1. Run [bold]atg index[/bold] to build the repo summary\n"
        "  2. Start your agent session\n"
        "  3. Run [bold]atg save[/bold] at the end of each session\n"
        "  4. Run [bold]atg resume[/bold] at the start of the next session"
    )


@app.command()
def uninstall(
    agents: Annotated[
        str,
        typer.Option(
            "--agents",
            "-a",
            help="Comma-separated adapters to remove: claude, codex, copilot, cursor, agents, all",
        ),
    ] = "all",
    purge_data: Annotated[
        bool,
        typer.Option("--purge-data", help="Also remove the .agent-token-guard data directory"),
    ] = False,
    root: Annotated[
        Optional[Path],
        typer.Option("--root", help="Repo root (defaults to current directory)"),
    ] = None,
) -> None:
    """Uninstall adapter files and optionally remove AgentTokenGuard data."""
    import shutil

    root_path = root or Path.cwd()
    selected_agents = _parse_agent_selection(agents)
    removed: list[str] = []

    for name in selected_agents:
        adapter = _AGENT_ADAPTERS[name](root=root_path)
        if hasattr(adapter, "uninstall"):
            removed += adapter.uninstall()

    if purge_data:
        guard_dir = root_path / ".agent-token-guard"
        if guard_dir.exists():
            shutil.rmtree(guard_dir)
            removed.append(".agent-token-guard/ (purged)")

    console.print(Panel.fit("[bold green]AgentTokenGuard uninstall complete[/bold green]"))
    if not removed:
        console.print("[dim]No files removed.[/dim]")
        return
    for path in removed:
        console.print(f"  [green]-[/green] {path}")


# ---------------------------------------------------------------------------
# atg save
# ---------------------------------------------------------------------------


@app.command()
def save(
    summary: Annotated[
        Optional[str],
        typer.Option("--summary", "-s", help="What was accomplished this session"),
    ] = None,
    decisions: Annotated[
        Optional[list[str]],
        typer.Option("--decisions", "-d", help="Key decisions made (repeat for multiple)"),
    ] = None,
    todos: Annotated[
        Optional[list[str]],
        typer.Option("--todos", "-t", help="Open tasks (repeat for multiple)"),
    ] = None,
    files: Annotated[
        Optional[list[str]],
        typer.Option("--files", "-f", help="Files touched this session"),
    ] = None,
    next_steps: Annotated[
        Optional[str],
        typer.Option("--next", "-n", help="What to do next session"),
    ] = None,
    root: Annotated[
        Optional[Path],
        typer.Option("--root", help="Repo root"),
    ] = None,
) -> None:
    """Save current session context to .agent-token-guard/memory/session.md."""
    root_path = root or Path.cwd()

    if not summary:
        console.print("[yellow]No --summary provided. Enter a brief summary (Ctrl+D to finish):[/yellow]")
        lines = []
        try:
            while True:
                line = input()
                lines.append(line)
        except EOFError:
            pass
        summary = "\n".join(lines).strip() or "Session saved without a summary."

    mm = MemoryManager(root=root_path)
    result = mm.save(
        summary=summary,
        decisions=decisions or [],
        todos=todos or [],
        touched_files=files or [],
        next_steps=next_steps or "",
    )

    # Use the changed-files auto-detection if no files provided
    if not files:
        indexer = RepoIndexer(root=root_path)
        changed = indexer.get_changed_files()
        if changed:
            mm.save(
                summary=summary,
                decisions=decisions or [],
                todos=todos or [],
                touched_files=changed,
                next_steps=next_steps or "",
            )
            result["auto_detected_files"] = changed

    metrics = MetricsEngine(root=root_path)
    metrics.record(
        "save",
        tokens_before=result["tokens_full"],
        tokens_after=result["tokens_compact"],
    )

    saved_pct = round(
        (1 - result["tokens_compact"] / max(result["tokens_full"], 1)) * 100, 1
    )

    console.print(Panel.fit("[bold green]Session saved[/bold green]"))
    console.print(f"  Full context:    [dim]{result['tokens_full']:,} tokens[/dim]")
    console.print(f"  Compact context: [bold]{result['tokens_compact']:,} tokens[/bold]")
    console.print(f"  Saved:           [green]{saved_pct}%[/green]")
    console.print(f"  File:            [dim].agent-token-guard/memory/session.md[/dim]")

    if result.get("auto_detected_files"):
        console.print(
            f"\n[dim]Auto-detected {len(result['auto_detected_files'])} changed files from git.[/dim]"
        )


# ---------------------------------------------------------------------------
# atg resume
# ---------------------------------------------------------------------------


@app.command()
def resume(
    root: Annotated[
        Optional[Path],
        typer.Option("--root", help="Repo root"),
    ] = None,
    raw: Annotated[
        bool,
        typer.Option("--raw", help="Output raw text without Rich formatting"),
    ] = False,
) -> None:
    """Print compact session context for pasting at agent session start."""
    root_path = root or Path.cwd()
    mm = MemoryManager(root=root_path)
    context = mm.resume()

    if raw:
        print(context)
        return

    tokens = max(1, len(context) // 4)
    console.print(Panel(context, title="[bold]Session Context[/bold]", expand=False))
    console.print(f"\n[dim]~{tokens} tokens — paste this at the start of your agent session.[/dim]")

    metrics = MetricsEngine(root=root_path)
    metrics.record("resume", tokens_after=tokens)


# ---------------------------------------------------------------------------
# atg index
# ---------------------------------------------------------------------------


@app.command()
def index(
    root: Annotated[
        Optional[Path],
        typer.Option("--root", help="Repo root"),
    ] = None,
) -> None:
    """Build repo summary, file-map, and dependency map."""
    root_path = root or Path.cwd()

    with console.status("[bold]Indexing repo...[/bold]"):
        indexer = RepoIndexer(root=root_path)
        stats = indexer.index()

    console.print(Panel.fit("[bold green]Index complete[/bold green]"))
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_row("Total files", str(stats["total_files"]))
    table.add_row("Code files", str(stats["code_files"]))
    table.add_row("Large files (>100 KB)", str(stats["large_files"]))
    if stats["entry_points"]:
        table.add_row("Entry points", ", ".join(f"`{e}`" for e in stats["entry_points"]))
    console.print(table)

    console.print(
        "\n[dim]Generated:[/dim]\n"
        "  .agent-token-guard/memory/repo-summary.md\n"
        "  .agent-token-guard/index/file-map.json\n"
        "  .agent-token-guard/index/dependency-map.json"
    )


# ---------------------------------------------------------------------------
# atg compress
# ---------------------------------------------------------------------------


@app.command()
def compress(
    file: Annotated[
        Optional[Path],
        typer.Option("--file", "-f", help="File to compress (default: read from stdin)"),
    ] = None,
    output: Annotated[
        Optional[Path],
        typer.Option("--output", "-o", help="Write compressed output to this file"),
    ] = None,
    root: Annotated[
        Optional[Path],
        typer.Option("--root", help="Repo root"),
    ] = None,
) -> None:
    """Compress verbose text: stack traces, CI logs, repeated output."""
    root_path = root or Path.cwd()
    compressor = OutputCompressor(root=root_path)

    if file:
        compressed, stats = compressor.compress_file(file)
    else:
        if sys.stdin.isatty():
            console.print("[yellow]Paste text to compress (Ctrl+D to finish):[/yellow]")
        raw = sys.stdin.read()
        if not raw.strip():
            console.print("[red]No input provided.[/red]")
            raise typer.Exit(1)
        compressed, stats = compressor.compress(raw)

    if output:
        Path(output).write_text(compressed)
        console.print(f"[green]Written to {output}[/green]")
    else:
        print(compressed)

    err_console = Console(stderr=True)
    err_console.print(
        f"\n[dim]Original: {stats['original_tokens']:,} tokens | "
        f"Compressed: {stats['compressed_tokens']:,} tokens | "
        f"Saved: {stats['savings_pct']}%[/dim]"
    )

    if stats["savings_pct"] > 0:
        metrics = MetricsEngine(root=root_path)
        metrics.record(
            "compress",
            tokens_before=stats["original_tokens"],
            tokens_after=stats["compressed_tokens"],
        )


# ---------------------------------------------------------------------------
# atg report
# ---------------------------------------------------------------------------


@app.command()
def report(
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output raw JSON"),
    ] = False,
    root: Annotated[
        Optional[Path],
        typer.Option("--root", help="Repo root"),
    ] = None,
) -> None:
    """Show estimated token savings and session usage."""
    root_path = root or Path.cwd()
    metrics = MetricsEngine(root=root_path)
    data = metrics.report()

    if json_output:
        import json
        print(json.dumps(data, indent=2))
        return

    if data["sessions"] == 0:
        console.print("[yellow]No sessions recorded yet. Run `atg save` after your first session.[/yellow]")
        return

    console.print(Panel.fit("[bold]Token Savings Report[/bold]"))

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_row("Sessions recorded", str(data["sessions"]))
    table.add_row("Total tokens saved", f"{data['total_tokens_saved']:,}")
    table.add_row("Files avoided", str(data["total_files_avoided"]))
    table.add_row(
        "Estimated cost saved",
        f"[green]~${data['estimated_cost_saved_usd']:.4f} USD[/green]",
    )
    console.print(table)

    events = data.get("events", [])
    if events:
        console.print(f"\n[dim]Last {min(5, len(events))} events:[/dim]")
        for ev in events[-5:]:
            saved = ev.get("tokens_saved", 0)
            console.print(
                f"  [dim]{ev['ts']}[/dim]  {ev['event']:<10}  "
                f"saved [green]{saved:,}[/green] tokens"
            )


@app.command()
def doctor(
    root: Annotated[
        Optional[Path],
        typer.Option("--root", help="Repo root"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output doctor report as JSON"),
    ] = False,
) -> None:
    """Run environment and dependency checks for release-readiness."""
    root_path = root or Path.cwd()
    report_data = Doctor(root=root_path).run()

    if json_output:
        import json

        print(json.dumps(report_data, indent=2))
        return

    style = "green" if report_data["ok"] else "yellow"
    console.print(Panel.fit(f"[bold {style}]ATG Doctor[/bold {style}]"))
    for check in report_data["checks"]:
        icon = "[green]PASS[/green]" if check["ok"] else "[red]FAIL[/red]"
        console.print(f"{icon}  {check['name']}: {check['detail']}")
        if check.get("fix"):
            console.print(f"      [dim]fix: {check['fix']}[/dim]")

    if report_data["ok"]:
        console.print("\n[green]Environment looks ready to ship.[/green]")
    else:
        console.print("\n[yellow]Resolve failing checks before publishing.[/yellow]")


# ---------------------------------------------------------------------------
# atg version
# ---------------------------------------------------------------------------


@app.command()
def version() -> None:
    """Print the installed version."""
    from . import __version__
    console.print(f"agent-token-guard {__version__}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    app()


if __name__ == "__main__":
    main()
