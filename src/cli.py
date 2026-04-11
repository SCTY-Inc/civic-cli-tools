"""CLI entry point for civic policy research."""

import argparse
import json
import os
import signal
import sys
from datetime import datetime
from pathlib import Path

import httpx
import tomllib
from dotenv import load_dotenv
from rich.console import Console

from _agent_cli import DoctorCheck, doctor_runner
from agents import research, write_brief, review, compare_research, write_comparison
from output import save_report, format_json
from tools.base import get_cache_stats, clear_cache, set_results_limit

__version__ = "0.6.0"

_NO_COLOR = bool(os.environ.get("NO_COLOR")) or not sys.stdout.isatty()
_FORCE_TERM = sys.stdout.isatty() and not os.environ.get("NO_COLOR")

console = Console(no_color=_NO_COLOR, force_terminal=_FORCE_TERM)
err_console = Console(stderr=True, no_color=_NO_COLOR, force_terminal=_FORCE_TERM)

# API key signup URLs surfaced by `civic doctor`.
API_KEY_SIGNUP = {
    "GOOGLE_API_KEY": "https://aistudio.google.com/apikey",
    "EXA_API_KEY": "https://dashboard.exa.ai/api-keys",
    "CONGRESS_GOV_API_KEY": "https://api.congress.gov/sign-up",
    "OPENSTATES_API_KEY": "https://openstates.org/accounts/register/",
    "REGULATIONS_GOV_API_KEY": "https://open.gsa.gov/api/regulationsgov/",
    "CENSUS_API_KEY": "https://api.census.gov/data/key_signup.html",
}

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
    output_format: str = "markdown",
    limit: int | None = None,
) -> int:
    """Run the full research pipeline. Returns exit code."""
    if limit:
        set_results_limit(limit)

    # Read topic from stdin when '-' is passed
    if topic == "-":
        topic = sys.stdin.read().strip()
        if not topic:
            err_console.print("[red]Error:[/] empty topic on stdin")
            return 1

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

    is_json = output_format == "json"

    try:
        if compare_targets:
            if not is_json:
                console.print(f"[bold]Civic[/] comparing: {topic}")
                console.print(f"[dim]{' vs '.join(compare_targets)}[/]\n")

            with console.status("[dim]Researching...", disable=is_json):
                outputs = compare_research(topic, compare_targets, questions, verbose and not is_json)

            if is_json:
                all_results = {}
                for o in outputs:
                    all_results[o.scope_label] = o.results.to_dict()
                print(json.dumps({
                    "topic": topic,
                    "mode": "compare",
                    "targets": compare_targets,
                    "results": all_results,
                }, indent=2))
                return 0

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

            if not is_json:
                console.print(f"[bold]Civic[/] researching: {topic}")
                console.print(f"[dim]Scope: {scope_label}[/]\n")

            with console.status("[dim]Researching...", disable=is_json):
                research_output = research(topic, questions, scope=scope, verbose=verbose and not is_json)

            if is_json:
                results_dict = research_output.results.to_dict()
                print(format_json(topic, scope_label, results_dict))
                return 0

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

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
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

    if getattr(args, "format", None) != "json":
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
        output_format=getattr(args, "format", "markdown"),
        limit=getattr(args, "limit", None),
    )


def cmd_cache(args) -> int:
    """Manage response cache."""
    if args.cache_action == "clear":
        if clear_cache():
            console.print("[green]Cache cleared[/]")
        else:
            console.print("[dim]No cache to clear[/]")
        return 0

    if args.cache_action == "stats":
        stats = get_cache_stats()
        if not stats:
            console.print("[dim]No cache file[/]")
            return 0
        console.print("[bold]Cache stats[/]")
        console.print(f"  Entries: {stats['entries']}")
        console.print(f"  Size: {stats['size_kb']:.1f} KB")
        if stats["oldest"]:
            console.print(f"  Oldest: {datetime.fromtimestamp(stats['oldest']).isoformat()}")
            console.print(f"  Newest: {datetime.fromtimestamp(stats['newest']).isoformat()}")
        return 0

    return 0


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
        output_format=args.format,
        limit=getattr(args, "limit", None),
    )


def cmd_doctor(args) -> int:
    """Validate env vars. Required keys fail the run; optional keys warn only."""
    # Required vs optional split mirrors tools/implementations.py:
    # GOOGLE_API_KEY + EXA_API_KEY always required; the rest gate specific sources.
    required_keys = ["GOOGLE_API_KEY", "EXA_API_KEY"]
    optional_keys = [
        "CONGRESS_GOV_API_KEY",
        "OPENSTATES_API_KEY",
        "REGULATIONS_GOV_API_KEY",
        "CENSUS_API_KEY",
    ]

    def _env_check(name: str) -> bool:
        return bool(os.getenv(name))

    # Advisory scan of optional keys (never fails the run).
    for k in optional_keys:
        mark = "PASS" if _env_check(k) else "WARN"
        hint = "" if _env_check(k) else f"  — optional — sign up: {API_KEY_SIGNUP.get(k, '(no URL)')}"
        print(f"  [{mark}] env {k}{hint}", file=sys.stderr)

    # Required checks — any failure exits nonzero.
    required_checks = [
        DoctorCheck(
            name=f"env {k}",
            check=(lambda n=k: _env_check(n)),
            hint=f"required — sign up: {API_KEY_SIGNUP.get(k, '(no URL)')}",
        )
        for k in required_keys
    ]
    return doctor_runner(required_checks, exit_on_fail=False)


def cmd_get(args) -> int:
    """Fetch a URL's full content. Markdown by default, JSON envelope with -f json."""
    url = args.url
    is_json = getattr(args, "format", "markdown") == "json"
    try:
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            resp = client.get(url, headers={"User-Agent": f"civic/{__version__}"})
            resp.raise_for_status()
            body = resp.text
            status_code = resp.status_code
            content_type = resp.headers.get("content-type", "")
    except httpx.HTTPError as e:
        if is_json:
            print(json.dumps({
                "status": "error",
                "command": "get",
                "error": str(e),
            }, separators=(",", ":")))
        else:
            err_console.print(f"[red]Error:[/] {e}")
        return 1

    if is_json:
        print(json.dumps({
            "status": "ok",
            "command": "get",
            "data": {
                "url": url,
                "status_code": status_code,
                "content_type": content_type,
                "content": body,
            },
        }, separators=(",", ":")))
    else:
        print(body)
    return 0


def _add_common_flags(parser):
    """Add flags shared across subcommands."""
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("-f", "--format", choices=["markdown", "json"], default="markdown",
                        help="Output format: markdown (file) or json (stdout)")
    parser.add_argument("--sources", action="store_true")
    parser.add_argument("--no-appendix", action="store_true")
    parser.add_argument("--limit", type=int, default=None,
                        help="Per-tool results limit (default: 25)")


def _build_adhoc_parser() -> argparse.ArgumentParser:
    """Parser for ad-hoc topic research (no subcommands)."""
    parser = argparse.ArgumentParser(
        prog="civic",
        description="Policy research CLI — evidence-based briefs from 8 government sources",
    )
    parser.add_argument("topic", help="Policy topic to research (use '-' to read from stdin)")
    parser.add_argument("-s", "--scope", default="all",
                        help="federal | state:XX | all (default: all)")
    parser.add_argument("-c", "--compare", metavar="A,B",
                        help="Compare targets: CA,NY or federal,CA or policy,news")
    parser.add_argument("-o", "--output", default="outputs/report.md")
    parser.add_argument("-q", "--questions", nargs="+", metavar="Q")
    _add_common_flags(parser)
    return parser


def main() -> int:
    load_dotenv()
    signal.signal(signal.SIGINT, handle_interrupt)

    # Detect ad-hoc topic: first non-flag arg is not a known subcommand
    known_commands = {"run", "topics", "cache", "doctor", "get"}
    first_pos = next((a for a in sys.argv[1:] if not a.startswith("-")), None)

    if first_pos and first_pos not in known_commands:
        args = _build_adhoc_parser().parse_args()
        return cmd_research(args)

    parser = argparse.ArgumentParser(
        prog="civic",
        description="Policy research CLI — evidence-based briefs from 8 government sources",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  civic "AI regulation" -s federal
  civic "AI regulation" -s federal -f json
  civic "Caregiver policy" --compare CA,NY,MA
  civic run caregiver-federal
  civic topics
  civic cache stats
        """,
    )
    parser.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command")

    # --- civic run <name> ---
    run_parser = subparsers.add_parser("run", help="Run a named topic preset from topics.toml")
    run_parser.add_argument("name", help="Topic preset name (see: civic topics)")
    _add_common_flags(run_parser)
    run_parser.set_defaults(func=cmd_run)

    # --- civic topics ---
    topics_parser = subparsers.add_parser("topics", help="List available topic presets")
    topics_parser.set_defaults(func=cmd_topics)

    # --- civic cache ---
    cache_parser = subparsers.add_parser("cache", help="Manage response cache")
    cache_parser.add_argument("cache_action", choices=["stats", "clear"], help="stats | clear")
    cache_parser.set_defaults(func=cmd_cache)

    # --- civic doctor ---
    doctor_parser = subparsers.add_parser("doctor", help="Validate env vars + API keys")
    doctor_parser.set_defaults(func=cmd_doctor)

    # --- civic get <url> ---
    get_parser = subparsers.add_parser("get", help="Fetch a URL's full content")
    get_parser.add_argument("url", help="URL to fetch")
    get_parser.add_argument("-f", "--format", choices=["markdown", "json"], default="markdown",
                            help="Output format: markdown (raw body) or json envelope")
    get_parser.set_defaults(func=cmd_get)

    args = parser.parse_args()

    if hasattr(args, "func") and args.func:
        return args.func(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
