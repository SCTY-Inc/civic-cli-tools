"""CLI entry point for civic policy research."""

import argparse
import os
import signal
import sys
from pathlib import Path

import tomllib
from dotenv import load_dotenv
from rich.console import Console

from agents import research, write_brief, review, compare_research, write_comparison
from output import save_report

__version__ = "0.5.0"

console = Console()
err_console = Console(stderr=True)

STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC", "PR"
}

TOPICS_FILE = Path(__file__).parent.parent / "topics.toml"


# --- Topics ---

def load_topics() -> dict:
    """Load named topic presets from topics.toml."""
    if not TOPICS_FILE.exists():
        return {}
    with open(TOPICS_FILE, "rb") as f:
        data = tomllib.load(f)
    return data.get("topics", {})


def get_topic(name: str) -> dict | None:
    """Get a single topic preset by name."""
    return load_topics().get(name)


# --- Scope / compare parsing ---

def parse_scope(scope_str: str) -> dict:
    if scope_str == "federal":
        return {"type": "federal", "states": []}
    if scope_str == "all":
        return {"type": "all", "states": []}
    if scope_str.startswith("state:"):
        states = [s.strip().upper() for s in scope_str[6:].split(",")]
        invalid = [s for s in states if s not in STATES]
        if invalid:
            raise ValueError(f"Invalid state codes: {', '.join(invalid)}")
        return {"type": "state", "states": states}
    raise ValueError(f"Invalid scope: {scope_str}. Use 'federal', 'all', or 'state:CA,NY'")


def parse_compare(compare_str: str) -> list[str]:
    targets = [t.strip() for t in compare_str.split(",")]
    valid_special = {"federal", "news", "policy"}
    for t in targets:
        if t not in valid_special and t.upper() not in STATES:
            raise ValueError(f"Invalid compare target: {t}")
    return targets


def check_env(scope: dict, compare: list[str] | None = None) -> list[str]:
    required = ["GOOGLE_API_KEY", "EXA_API_KEY"]
    if scope["type"] in ("federal", "all"):
        required.append("CONGRESS_GOV_API_KEY")
    if scope["type"] in ("state", "all"):
        required.append("OPENSTATES_API_KEY")
    if compare:
        if any(t in ("federal", "policy") for t in compare):
            if "CONGRESS_GOV_API_KEY" not in required:
                required.append("CONGRESS_GOV_API_KEY")
        if any(t.upper() in STATES for t in compare):
            if "OPENSTATES_API_KEY" not in required:
                required.append("OPENSTATES_API_KEY")
    return [v for v in required if not os.getenv(v)]


# --- Pipeline runner ---

def run_pipeline(
    topic: str,
    scope_str: str = "all",
    compare_str: str | None = None,
    questions: list[str] | None = None,
    output_path: str = "outputs/report.md",
    verbose: bool = False,
    show_sources: bool = False,
    no_appendix: bool = False,
) -> int:
    """Run the full research → write → review pipeline. Returns exit code."""
    try:
        scope = parse_scope(scope_str)
        compare_targets = parse_compare(compare_str) if compare_str else None
    except ValueError as e:
        err_console.print(f"[red]Error:[/] {e}")
        return 1

    missing = check_env(scope, compare_targets)
    if missing:
        err_console.print(f"[red]Missing env vars:[/] {', '.join(missing)}")
        err_console.print("Add to .env or export. Get free keys: api.congress.gov/sign-up | openstates.org/accounts/register/")
        return 1

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    try:
        if compare_targets:
            console.print(f"[bold]Civic[/] comparing: {topic}")
            console.print(f"[dim]{' vs '.join(compare_targets)}[/]\n")

            with console.status("[dim]Researching..."):
                outputs = compare_research(topic, compare_targets, questions, verbose)

            if show_sources:
                for o in outputs:
                    console.print(f"\n[bold]{o.scope_label}:[/]")
                    for tool, count in sorted(o.results.tool_usage.items()):
                        console.print(f"  {tool}: {'[green]' + str(count) + 'x[/]' if count else '[dim]0[/]'}")

            console.print("[green]✓[/] Research")
            with console.status("[dim]Writing comparison..."):
                final = write_comparison(topic, outputs)
            console.print("[green]✓[/] Comparison")

        else:
            scope_label = scope_str if scope_str != "all" else "federal + state"
            console.print(f"[bold]Civic[/] researching: {topic}")
            console.print(f"[dim]Scope: {scope_label}[/]\n")

            with console.status("[dim]Researching..."):
                research_output = research(topic, questions, scope=scope, verbose=verbose)
            console.print("[green]✓[/] Research")

            if show_sources:
                level, explanation = research_output.results.confidence_score()
                color = {"HIGH": "green", "MEDIUM": "yellow", "LOW": "red"}.get(level, "white")
                console.print(f"\n[bold]Confidence:[/] [{color}]{explanation}[/]")
                console.print("\n[bold]Sources:[/]")
                for tool, count in sorted(research_output.results.tool_usage.items()):
                    console.print(f"  {tool}: {'[green]' + str(count) + 'x[/]' if count else '[dim]0[/]'}")
                console.print()

            with console.status("[dim]Writing..."):
                draft = write_brief(topic, research_output, include_appendix=not no_appendix)
            console.print("[green]✓[/] Draft")

            with console.status("[dim]Reviewing..."):
                final = review(draft)
            console.print("[green]✓[/] Review")

        save_report(final, out)
        console.print(f"\n[green]Saved:[/] {out}")
        return 0

    except KeyboardInterrupt:
        err_console.print("\n[yellow]Interrupted[/]")
        return 130
    except Exception as e:
        err_console.print(f"[red]Error:[/] {e}")
        if verbose:
            err_console.print_exception()
        return 1


# --- CLI ---

def handle_interrupt(signum, frame):
    err_console.print("\n[yellow]Interrupted[/]")
    sys.exit(130)


def cmd_run(args) -> int:
    """Run a named topic preset from topics.toml."""
    topic_config = get_topic(args.name)
    if not topic_config:
        topics = load_topics()
        err_console.print(f"[red]Topic '{args.name}' not found.[/]")
        if topics:
            err_console.print(f"Available: {', '.join(topics.keys())}")
        else:
            err_console.print(f"No topics.toml found at {TOPICS_FILE}")
        return 1

    console.print(f"[dim]Running preset:[/] {args.name}")
    return run_pipeline(
        topic=topic_config["topic"],
        scope_str=topic_config.get("scope", "all"),
        compare_str=topic_config.get("compare"),
        questions=topic_config.get("questions"),
        output_path=topic_config.get("output", f"outputs/{args.name}.md"),
        verbose=args.verbose,
        show_sources=args.sources,
        no_appendix=args.no_appendix,
    )


def cmd_topics(args) -> int:
    """List available topic presets."""
    topics = load_topics()
    if not topics:
        console.print(f"[dim]No topics found. Create {TOPICS_FILE}[/]")
        return 0
    console.print(f"[bold]Topics[/] ({len(topics)} presets)\n")
    for name, config in topics.items():
        scope = config.get("scope") or f"compare: {config.get('compare', 'all')}"
        console.print(f"  [bold]{name}[/]")
        console.print(f"    [dim]{config['topic']} — {scope}[/]")
    console.print(f"\n[dim]Run with: civic run <name>[/]")
    return 0


def cmd_research(args) -> int:
    """Run ad-hoc research on a topic."""
    return run_pipeline(
        topic=args.topic,
        scope_str=args.scope,
        compare_str=args.compare,
        questions=args.questions,
        output_path=args.output,
        verbose=args.verbose,
        show_sources=args.sources,
        no_appendix=args.no_appendix,
    )


def main() -> int:
    load_dotenv()
    signal.signal(signal.SIGINT, handle_interrupt)

    parser = argparse.ArgumentParser(
        prog="civic",
        description="Policy research CLI — evidence-based briefs from 7 government sources",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  civic "AI regulation" -s federal
  civic "Caregiver policy" --compare CA,NY,MA
  civic run caregiver-federal
  civic topics
        """,
    )
    parser.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command")

    # --- civic run <name> ---
    run_parser = subparsers.add_parser("run", help="Run a named topic preset from topics.toml")
    run_parser.add_argument("name", help="Topic preset name (see: civic topics)")
    run_parser.add_argument("-v", "--verbose", action="store_true")
    run_parser.add_argument("--sources", action="store_true")
    run_parser.add_argument("--no-appendix", action="store_true")
    run_parser.set_defaults(func=cmd_run)

    # --- civic topics ---
    topics_parser = subparsers.add_parser("topics", help="List available topic presets")
    topics_parser.set_defaults(func=cmd_topics)

    # --- civic <topic> (ad-hoc, default) ---
    parser.add_argument("topic", nargs="?", help="Policy topic to research")
    parser.add_argument("-s", "--scope", default="all",
                        help="federal | state:XX | all (default: all)")
    parser.add_argument("-c", "--compare", metavar="A,B",
                        help="Compare targets: CA,NY or federal,CA or policy,news")
    parser.add_argument("-o", "--output", default="outputs/report.md")
    parser.add_argument("-q", "--questions", nargs="+", metavar="Q")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--sources", action="store_true")
    parser.add_argument("--no-appendix", action="store_true")
    parser.set_defaults(func=None)

    args = parser.parse_args()

    # Subcommand
    if hasattr(args, "func") and args.func:
        return args.func(args)

    # Ad-hoc topic
    if args.topic:
        return cmd_research(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
