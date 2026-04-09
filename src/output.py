"""Output formatting and file handling."""

import json
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


def format_json(topic: str, scope: str, results_dict: dict, brief: str = "") -> str:
    """Format research results as JSON for agent consumption."""
    output = {
        "topic": topic,
        "scope": scope,
        "timestamp": datetime.now().isoformat(),
        **results_dict,
    }
    if brief:
        output["brief"] = brief
    return json.dumps(output, indent=2)
