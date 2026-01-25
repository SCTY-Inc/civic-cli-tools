"""CLI entry point for civic policy research."""

import argparse
import os
import signal
import sys
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console

from agents import research, write_brief, review, compare_research, write_comparison
from output import save_report

__version__ = "0.4.0"

console = Console()
err_console = Console(stderr=True)

STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC", "PR"
]


def parse_scope(scope_str: str) -> dict:
    """Parse scope string into structured dict."""
    if scope_str == "federal":
        return {"type": "federal", "states": []}
    elif scope_str == "all":
        return {"type": "all", "states": []}
    elif scope_str.startswith("state:"):
        states = [s.strip().upper() for s in scope_str[6:].split(",")]
        invalid = [s for s in states if s not in STATES]
        if invalid:
            raise ValueError(f"Invalid state codes: {', '.join(invalid)}")
        return {"type": "state", "states": states}
    else:
        raise ValueError(f"Invalid scope: {scope_str}. Use 'federal', 'all', or 'state:CA,NY'")


def parse_compare(compare_str: str) -> list[str]:
    """Parse compare targets."""
    targets = [t.strip() for t in compare_str.split(",")]
    valid_special = {"federal", "news", "policy"}

    for t in targets:
        if t not in valid_special and t.upper() not in STATES:
            raise ValueError(f"Invalid compare target: {t}. Use state codes (CA, NY) or 'federal', 'news', 'policy'")

    return targets


def check_env(scope: dict, compare: list[str] | None = None) -> list[str]:
    """Check required environment variables based on scope."""
    required = ["GOOGLE_API_KEY", "EXA_API_KEY"]

    # Check scope
    if scope["type"] in ("federal", "all"):
        required.append("CONGRESS_GOV_API_KEY")
    if scope["type"] in ("state", "all"):
        required.append("OPENSTATES_API_KEY")

    # Check compare targets
    if compare:
        if "federal" in compare or "policy" in compare:
            if "CONGRESS_GOV_API_KEY" not in required:
                required.append("CONGRESS_GOV_API_KEY")
        state_targets = [t for t in compare if t.upper() in STATES]
        if state_targets and "OPENSTATES_API_KEY" not in required:
            required.append("OPENSTATES_API_KEY")

    return [var for var in required if not os.getenv(var)]


def handle_interrupt(signum, frame):
    """Handle Ctrl+C gracefully."""
    err_console.print("\n[yellow]Interrupted[/]")
    sys.exit(130)


def main() -> int:
    """Main entry point. Returns exit code."""
    load_dotenv()
    signal.signal(signal.SIGINT, handle_interrupt)

    parser = argparse.ArgumentParser(
        prog="civic",
        description="Policy research CLI - generates evidence-based policy briefs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  civic "Solar energy policy"
  civic "Housing affordability" --scope federal
  civic "Rent control" --scope state:CA,NY
  civic "AI regulation" -q "What agencies are involved?" -v
  civic "Paid leave" --compare CA,NY
  civic "Healthcare" --compare federal,CA
  civic "Immigration" --compare policy,news
        """,
    )
    parser.add_argument("topic", nargs="?", help="Policy topic to research")
    parser.add_argument("-o", "--output", default="outputs/report.md", help="Output file (default: outputs/report.md)")
    parser.add_argument("-q", "--questions", nargs="+", metavar="Q", help="Specific research questions")
    parser.add_argument("-s", "--scope", default="all",
                        help="Research scope: federal, state:XX, state:CA,NY, or all (default: all)")
    parser.add_argument("-c", "--compare", metavar="A,B",
                        help="Compare targets: CA,NY or federal,CA or policy,news")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show tool calls")
    parser.add_argument("--sources", action="store_true", help="Show source usage summary")
    parser.add_argument("--no-appendix", action="store_true", help="Exclude source appendix from output")
    parser.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args()

    # Require topic
    if not args.topic:
        parser.print_help()
        return 0

    # Parse scope and compare
    try:
        scope = parse_scope(args.scope)
        compare_targets = parse_compare(args.compare) if args.compare else None
    except ValueError as e:
        err_console.print(f"[red]Error:[/] {e}")
        return 1

    # Check env vars
    missing = check_env(scope, compare_targets)
    if missing:
        err_console.print(f"[red]Missing environment variables:[/] {', '.join(missing)}")
        err_console.print("Add them to .env file or export them")
        return 1

    # Ensure output directory exists
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Run pipeline
    try:
        if compare_targets:
            # Comparison mode
            console.print(f"[bold]Civic[/] comparing: {args.topic}")
            console.print(f"[dim]Targets: {' vs '.join(compare_targets)}[/]\n")

            with console.status("[dim]Researching..."):
                outputs = compare_research(args.topic, compare_targets, args.questions, args.verbose)

            # Show sources for each target
            if args.sources:
                for output in outputs:
                    console.print(f"\n[bold]{output.scope_label}:[/]")
                    for tool, count in sorted(output.results.tool_usage.items()):
                        status = f"[green]{count}x[/]" if count > 0 else "[dim]0[/]"
                        console.print(f"  {tool}: {status}")

            console.print("[green]✓[/] Research")

            with console.status("[dim]Writing comparison..."):
                final = write_comparison(args.topic, outputs)
            console.print("[green]✓[/] Comparison")

        else:
            # Standard mode
            scope_label = args.scope if args.scope != "all" else "federal + state"
            console.print(f"[bold]Civic[/] researching: {args.topic}")
            console.print(f"[dim]Scope: {scope_label}[/]\n")

            with console.status("[dim]Researching..."):
                research_output = research(args.topic, args.questions, scope=scope, verbose=args.verbose)
            console.print("[green]✓[/] Research")

            if args.sources:
                level, explanation = research_output.results.confidence_score()
                color = {"HIGH": "green", "MEDIUM": "yellow", "LOW": "red"}.get(level, "white")
                console.print(f"\n[bold]Confidence:[/] [{color}]{explanation}[/]")

                console.print("\n[bold]Sources used:[/]")
                all_tools = ["web_search", "academic_search", "census_search", "congress_search",
                             "federal_register_search", "court_search", "state_legislation_search"]
                for tool in all_tools:
                    count = research_output.results.tool_usage.get(tool, 0)
                    status = f"[green]{count}x[/]" if count > 0 else "[dim]0[/]"
                    console.print(f"  {tool}: {status}")
                console.print()

            with console.status("[dim]Writing..."):
                draft = write_brief(args.topic, research_output, include_appendix=not args.no_appendix)
            console.print("[green]✓[/] Draft")

            with console.status("[dim]Reviewing..."):
                final = review(draft)
            console.print("[green]✓[/] Review")

        # Save output
        save_report(final, output_path)
        console.print(f"\n[green]Saved:[/] {output_path}")
        return 0

    except KeyboardInterrupt:
        err_console.print("\n[yellow]Interrupted[/]")
        return 130

    except Exception as e:
        err_console.print(f"[red]Error:[/] {e}")
        if args.verbose:
            err_console.print_exception()
        return 1


if __name__ == "__main__":
    sys.exit(main())
