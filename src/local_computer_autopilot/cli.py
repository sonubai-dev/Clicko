"""Command-line interface (CLI) for Clicko — Local Computer Autopilot."""

from __future__ import annotations

import json
import sys
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="clicko",
    help="Clicko — Enterprise Local Windows AI Computer Autopilot CLI",
    add_completion=False,
)
console = Console()


@app.command()
def version() -> None:
    """Display Clicko version and active phase roadmap milestones."""
    from local_computer_autopilot import __version__
    console.print(f"[bold cyan]Clicko / LocalComputerAutopilot[/bold cyan] v[green]{__version__}[/green]")
    console.print("  [green][OK] Phase 1[/green]: Safe Computer Control & Fail-Safe Core")
    console.print("  [green][OK] Phase 2[/green]: Visual Verification, SQLite Audit & Browser Automation")
    console.print("  [green][OK] Phase 3[/green]: Starlette Web Dashboard & Autonomous Planning")
    console.print("  [green][OK] Phase 4[/green]: Visual Grounding, Macros, Multi-Monitor & Desktop App Control")
    console.print("  [green][OK] Phase 5[/green]: Production Scheduling, Audit Exports & Enterprise Packaging")


@app.command()
def serve() -> None:
    """Start the Clicko MCP server over stdio transport (for Claude Desktop / MCP clients)."""
    from local_computer_autopilot.server import main
    main()


@app.command()
def web(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host address to bind to"),
    port: int = typer.Option(8000, "--port", "-p", help="Port number to bind to"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload for development"),
) -> None:
    """Launch the Clicko Starlette Web UI Dashboard."""
    from local_computer_autopilot.web.server import run_server
    console.print(f"[bold green]Starting Clicko Web Dashboard on http://{host}:{port}...[/bold green]")
    run_server(host=host, port=port, reload=reload)


@app.command()
def run(
    goal: str = typer.Argument(..., help="Natural language objective to accomplish"),
    mode: str = typer.Option("auto", "--mode", "-m", help="Planning mode: auto, local_llm, structured"),
) -> None:
    """Execute an autonomous workflow goal directly from the terminal."""
    from local_computer_autopilot.agent import AgentMode, AutonomousAgent, WorkflowPlanner
    from local_computer_autopilot.config import AppConfig

    cfg = AppConfig()
    planner = WorkflowPlanner()
    agent = AutonomousAgent(config=cfg)

    m = AgentMode(mode.lower()) if mode.lower() in [x.value for x in AgentMode] else AgentMode.AUTO
    console.print(f"[bold blue]Planning goal:[/bold blue] \"{goal}\"")
    plan = planner.plan(goal, mode=m)
    console.print(f"Plan generated with [bold]{len(plan.steps)}[/bold] steps ({plan.mode_used.value} mode).")

    for s in plan.steps:
        console.print(f"  [dim]Step {s.step_number}:[/dim] {s.action_name} - {s.description}")

    console.print("[yellow]Executing autonomous workflow...[/yellow]")
    res = agent.run_plan(plan)

    if res.success:
        console.print(f"[bold green][OK] Succeeded![/bold green] Completed {res.steps_completed}/{res.steps_total} steps in {res.duration_seconds}s")
    else:
        console.print(f"[bold red][FAIL] Failed:[/bold red] {res.error_message}")
        sys.exit(1)


@app.command()
def status() -> None:
    """Inspect local system diagnostics, monitor resolutions, and fail-safe state."""
    from local_computer_autopilot.agent.planner import WorkflowPlanner
    from local_computer_autopilot.computer.controller import ComputerController
    from local_computer_autopilot.config import AppConfig

    ctrl = ComputerController(AppConfig())
    planner = WorkflowPlanner()

    table = Table(title="Clicko Autopilot System Diagnostics")
    table.add_column("Property", style="cyan", no_wrap=True)
    table.add_column("Status / Value", style="green")

    screen = ctrl.get_screen_info()
    table.add_row("Primary Screen", f"{screen.width} x {screen.height}")

    monitors = ctrl.get_monitors()
    table.add_row("Displays Detected", str(len(monitors)))
    for m in monitors:
        primary = " [Primary]" if m.is_primary else ""
        table.add_row(f"  Display {m.index}", f"{m.width}x{m.height} at ({m.x}, {m.y}){primary}")

    status_rep = ctrl.get_status(["all"])
    table.add_row("PyAutoGUI Fail-Safe", "ACTIVE" if status_rep.failsafe_enabled else "DISABLED")
    table.add_row("Action Lock", "Held" if status_rep.action_lock_held else "Free")
    table.add_row("Local Ollama Reachable", "YES" if planner.is_local_llm_available() else "NO (Rule-based fallback active)")

    console.print(table)


@app.command()
def audit(
    format: str = typer.Option("json", "--format", "-f", help="Export format: json or csv"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="File path to write export into"),
) -> None:
    """Export task history and execution audit trails."""
    from local_computer_autopilot.audit import export_audit_csv, export_audit_json
    from local_computer_autopilot.task.storage import TaskStorage

    storage = TaskStorage()
    if format.lower() == "csv":
        data = export_audit_csv(storage, output_path=output)
    else:
        data = export_audit_json(storage, output_path=output)

    if output:
        console.print(f"[bold green]Audit exported successfully to:[/bold green] {output}")
    else:
        print(data)


def main() -> None:
    """Main CLI entrypoint."""
    app()


if __name__ == "__main__":
    main()
