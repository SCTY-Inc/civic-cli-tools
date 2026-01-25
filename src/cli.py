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

__version__ = "0.2.0"

console = Console()
err_console = Console(stderr=True)


def check_env() -> list[str]:
    """Check required environment variables. Returns list of missing vars."""
    required = ["GOOGLE_API_KEY", "EXA_API_KEY"]
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
  civic "Solar energy policy in Michigan"
  civic "Housing affordability" -q "Impact of rent control?"
  civic "AI regulation" -o ai-policy.md --verbose
        """,
    )
    parser.add_argument("topic", nargs="?", help="Policy topic to research")
    parser.add_argument("-o", "--output", default="report.md", help="Output file (default: report.md)")
    parser.add_argument("-q", "--questions", nargs="+", metavar="Q", help="Specific research questions")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show search queries")
    parser.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args()

    # Require topic
    if not args.topic:
        parser.print_help()
        return 0

    # Check env vars
    missing = check_env()
    if missing:
        err_console.print(f"[red]Missing environment variables:[/] {', '.join(missing)}")
        err_console.print("Add them to .env file or export them")
        return 1

    # Run pipeline
    try:
        console.print(f"[bold]Civic[/] researching: {args.topic}\n")

        with console.status("[dim]Researching..."):
            findings = research(args.topic, args.questions, verbose=args.verbose)
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
