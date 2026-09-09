"""Command-line interface for GitHub Issue Analysis Agent using Rich."""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Optional

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.table import Table
from rich.text import Text

from src.agent.pipeline import TriagePipeline
from src.config import settings
from src.llm import get_llm_provider
from src.models import PriorityLevel, IssueCategory

console = Console(legacy_windows=False)


def print_banner() -> None:
    """Display rich ASCII header."""
    banner_text = Text()
    banner_text.append("🛡️  GITHUB ISSUE ANALYSIS AGENT\n", style="bold cyan")
    banner_text.append("Autonomous Multi-Step AI Triage, Classification & Reporting Engine\n", style="italic white")
    banner_text.append("Powered by Deep Triage Reasoning & Native Function-Calling", style="dim")
    console.print(Panel(banner_text, border_style="cyan", padding=(1, 2)))


async def run_cli(
    repo: str,
    goal: str,
    limit: int = 30,
    apply: bool = False,
    mock: bool = False,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> int:
    """Execute the triage agent pipeline from the command line."""
    print_banner()

    effective_provider_name = "mock" if mock else (provider or settings.default_llm_provider)
    llm_provider = get_llm_provider(effective_provider_name, model=model)

    exec_mode = "[bold red]APPLY (WILL WRITE TO GITHUB)[/bold red]" if apply else "[bold green]DRY-RUN (Simulated Safely)[/bold green]"
    console.print(f"[bold]Target Repository:[/bold] [cyan]{repo}[/cyan]")
    console.print(f"[bold]Triage Goal:[/bold] {goal}")
    console.print(f"[bold]Execution Mode:[/bold] {exec_mode}")
    console.print(f"[bold]LLM Engine:[/bold] [magenta]{llm_provider.provider_name}[/magenta] ({llm_provider.model_name})")
    console.print(f"[bold]Issue Limit:[/bold] {limit}")
    console.print()

    progress_bar = Progress(
        SpinnerColumn("dots"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    )

    with progress_bar:
        task = progress_bar.add_task("[cyan]Starting pipeline...", total=100)

        def on_progress(p: dict) -> None:
            progress_bar.update(task, completed=p.get("percent", 0), description=f"[cyan]{p.get('message', '')}")

        pipeline = TriagePipeline(
            repo=repo,
            goal=goal,
            dry_run=not apply,
            apply_actions=apply,
            limit=limit,
            provider=llm_provider,
            progress_callback=on_progress,
        )

        try:
            report = await pipeline.execute()
        except Exception as exc:
            console.print(f"\n[bold red]Pipeline failed:[/bold red] {exc}")
            return 1

    console.print("\n[bold green]✓ Triage Run Completed Successfully![/bold green]\n")

    # Display KPI Summary Table
    kpi_table = Table(title="Triage Run Statistics", border_style="cyan", header_style="bold cyan")
    kpi_table.add_column("Analyzed", justify="center")
    kpi_table.add_column("Critical Blockers", justify="center", style="bold red")
    kpi_table.add_column("High Priority", justify="center", style="yellow")
    kpi_table.add_column("Duplicates", justify="center", style="magenta")
    kpi_table.add_column("Closes Recommended", justify="center", style="blue")
    kpi_table.add_column("Duration", justify="center")
    kpi_table.add_column("Tokens Used", justify="center")

    kpi_table.add_row(
        str(report.stats.total_issues_analyzed),
        str(report.stats.priorities_breakdown.get("critical", 0)),
        str(report.stats.priorities_breakdown.get("high", 0)),
        str(report.stats.duplicates_detected),
        str(report.stats.recommended_closes),
        f"{report.stats.execution_time_seconds:.1f}s",
        f"{report.stats.total_tokens_used:,}",
    )
    console.print(kpi_table)
    console.print()

    # Display Issues Table
    issues_table = Table(title="Triage Register", border_style="dim", header_style="bold white")
    issues_table.add_column("#", style="cyan", justify="right", width=6)
    issues_table.add_column("Title", style="white", max_width=35)
    issues_table.add_column("Category", justify="center", width=14)
    issues_table.add_column("Priority", justify="center", width=12)
    issues_table.add_column("Action", justify="left", max_width=25)
    issues_table.add_column("Labels to Apply", style="dim", max_width=20)

    category_colors = {
        "bug": "[red]BUG[/red]",
        "feature_request": "[green]FEATURE[/green]",
        "question": "[blue]QUESTION[/blue]",
        "documentation": "[cyan]DOCS[/cyan]",
        "duplicate": "[magenta]DUPLICATE[/magenta]",
        "spam": "[bright_black]SPAM[/bright_black]",
    }

    priority_colors = {
        "critical": "[bold red]CRITICAL[/bold red]",
        "high": "[yellow]HIGH[/yellow]",
        "medium": "[white]MEDIUM[/white]",
        "low": "[dim]LOW[/dim]",
    }

    for rec in report.issues:
        issue = rec.issue
        cls = rec.classification
        prio = rec.priority
        act = rec.action

        cat_badge = category_colors.get(cls.category.value, str(cls.category.value)) if cls else "N/A"
        prio_badge = priority_colors.get(prio.level.value, str(prio.level.value)) if prio else "N/A"
        act_str = act.headline if act else "N/A"
        labels_str = ", ".join(act.labels_to_add) if (act and act.labels_to_add) else "-"

        issues_table.add_row(
            f"#{issue.number}",
            issue.title,
            cat_badge,
            prio_badge,
            act_str,
            labels_str,
        )

    console.print(issues_table)
    console.print()

    # Output paths
    console.print(Panel(
        f"[bold]Generated Output Artifacts:[/bold]\n"
        f"• [bold green]Run Log (JSONL):[/bold green] [dim]{pipeline.run_logger.log_file}[/dim]\n"
        f"• [bold green]JSON Report:[/bold green] [dim]reports/{report.repository.replace('/', '_')}_{report.completed_at.strftime('%Y%m%d_%H%M%S')}.json[/dim]\n"
        f"• [bold green]Markdown Summary:[/bold green] [dim]reports/{report.repository.replace('/', '_')}_{report.completed_at.strftime('%Y%m%d_%H%M%S')}.md[/dim]",
        border_style="green",
        title="Artifacts Saved",
    ))

    return 0


def main() -> None:
    """CLI entry point with argument parsing."""
    parser = argparse.ArgumentParser(
        description="GitHub Issue Analysis Agent - Autonomous multi-step issue triage and reporting."
    )
    parser.add_argument(
        "--repo",
        "-r",
        type=str,
        default="mock/demo-repo",
        help="GitHub repository in 'owner/repo' format (default: 'mock/demo-repo')",
    )
    parser.add_argument(
        "--goal",
        "-g",
        type=str,
        default="Triage all open issues from the last 30 days and detect duplicates",
        help="Triage goal description",
    )
    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=30,
        help="Maximum issues to analyze (default: 30)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply actions to GitHub (labels, comments, closes). Default is dry-run mode.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Run in simulation mode without modifying GitHub (default: True)",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Force offline mock provider and demo repo fixtures (no API keys required)",
    )
    parser.add_argument(
        "--provider",
        "-p",
        choices=["mock", "gemini", "anthropic", "openai"],
        default=None,
        help="LLM provider to use",
    )
    parser.add_argument(
        "--model",
        "-m",
        type=str,
        default=None,
        help="Specific LLM model identifier",
    )

    args = parser.parse_args()
    apply_flag = args.apply

    exit_code = asyncio.run(
        run_cli(
            repo=args.repo,
            goal=args.goal,
            limit=args.limit,
            apply=apply_flag,
            mock=args.mock,
            provider=args.provider,
            model=args.model,
        )
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
