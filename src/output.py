"""Output formatting and file handling."""

from datetime import datetime
from pathlib import Path


def save_report(content: str, path: Path) -> None:
    """Save policy brief to markdown file."""
    header = f"""---
generated: {datetime.now().isoformat()}
tool: civic
---

"""
    path.write_text(header + content)
