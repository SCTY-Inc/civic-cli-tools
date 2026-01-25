"""CLI entry point for civic policy research."""

import argparse
import os
import signal
import sys
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console

from agents import research, write_brief, review
from output import save_report

__version__ = "0.3.0"

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


def check_env(scope: dict) -> list[str]:
    """Check required environment variables based on scope."""
    required = ["GOOGLE_API_KEY", "EXA_API_KEY"]

    if scope["type"] in ("federal", "all"):
        required.append("CONGRESS_GOV_API_KEY")
    if scope["type"] in ("state", "all"):
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
        """,
    )
    parser.add_argument("topic", nargs="?", help="Policy topic to research")
    parser.add_argument("-o", "--output", default="report.md", help="Output file (default: report.md)")
    parser.add_argument("-q", "--questions", nargs="+", metavar="Q", help="Specific research questions")
    parser.add_argument("-s", "--scope", default="all",
                        help="Research scope: federal, state:XX, state:CA,NY, or all (default: all)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show tool calls")
    parser.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args()

    # Require topic
    if not args.topic:
        parser.print_help()
        return 0

    # Parse scope
    try:
        scope = parse_scope(args.scope)
    except ValueError as e:
        err_console.print(f"[red]Error:[/] {e}")
        return 1

    # Check env vars
    missing = check_env(scope)
    if missing:
        err_console.print(f"[red]Missing environment variables:[/] {', '.join(missing)}")
        err_console.print("Add them to .env file or export them")
        return 1

    # Run pipeline
    try:
        scope_label = args.scope if args.scope != "all" else "federal + state"
        console.print(f"[bold]Civic[/] researching: {args.topic}")
        console.print(f"[dim]Scope: {scope_label}[/]\n")

        with console.status("[dim]Researching..."):
            findings = research(args.topic, args.questions, scope=scope, verbose=args.verbose)
        console.print("[green]✓[/] Research")

        with console.status("[dim]Writing..."):
            draft = write_brief(args.topic, findings)
        console.print("[green]✓[/] Draft")

        with console.status("[dim]Reviewing..."):
            final = review(draft)
        console.print("[green]✓[/] Review")

        output_path = Path(args.output)
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
