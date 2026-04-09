"""Tool registry for executing tools by name."""

from typing import Any

from .models import Finding
from .implementations import (
    WebSearch, AcademicSearch, CongressSearch,
    FederalRegisterSearch, RegulationsSearch,
    CourtSearch, CensusSearch, StateLegislationSearch,
)


class ToolRegistry:
    """Registry for executing tools by name."""

    def __init__(self, scope: dict):
        self.scope = scope
        self._tools = {
            "web_search": WebSearch(),
            "academic_search": AcademicSearch(),
            "census_search": CensusSearch(),
            "congress_search": CongressSearch(),
            "federal_register_search": FederalRegisterSearch(),
            "regulations_search": RegulationsSearch(),
            "court_search": CourtSearch(),
            "state_legislation_search": StateLegislationSearch(scope.get("states", [])),
        }

    def execute(self, tool_name: str, args: dict[str, Any]) -> tuple[list[Finding], str]:
        """Execute tool, return (findings, formatted_text)."""
        tool = self._tools.get(tool_name)
        if not tool:
            return [], f"Unknown tool: {tool_name}"

        findings = tool.execute(**args)

        formatted = []
        for f in findings:
            date_str = f" ({f.date})" if f.date else ""
            cite_str = f" [{f.citations} citations]" if f.citations else ""
            formatted.append(f"**{f.title}**{date_str}{cite_str}\n{f.snippet}\nSource: {f.url}")

        return findings, "\n\n---\n\n".join(formatted)
