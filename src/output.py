"""Output formatting and file handling."""

from datetime import datetime
from pathlib import Path


def save_report(content: str, path: Path) -> None:
    """Save policy brief to markdown file."""
    # Add metadata header
    header = f"""---
generated: {datetime.now().isoformat()}
tool: civic
---

"""
    path.write_text(header + content)


def format_sources(sources: list[str]) -> str:
    """Format source URLs as numbered list."""
    if not sources:
        return ""
    lines = ["## Sources", ""]
    for i, url in enumerate(sources, 1):
        lines.append(f"{i}. {url}")
    return "\n".join(lines)
