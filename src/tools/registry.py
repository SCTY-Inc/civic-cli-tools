"""Tool registry for executing tools by name."""

from typing import Any

from .implementations import (
    AcademicSearch,
    CensusSearch,
    CongressSearch,
    CourtSearch,
    FederalRegisterSearch,
    RegulationsSearch,
    StateLegislationSearch,
    WebSearch,
)
from .models import Finding


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
        tool = self._tools.get(tool_name)
        if not tool:
            return [], f"Unknown tool: {tool_name}"
        findings = tool.execute(**self._normalize_args(tool_name, args))
        return findings, self._format_findings(findings)

    def _normalize_args(self, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(args)
        if tool_name == "census_search" and not normalized.get("geography"):
            normalized["geography"] = self._default_census_geography()
        if (
            tool_name == "state_legislation_search"
            and len(self.scope.get("states", [])) == 1
            and not normalized.get("state")
        ):
            normalized["state"] = self.scope["states"][0]
        return normalized

    def _default_census_geography(self) -> str:
        if self.scope.get("type") == "state" and self.scope.get("states"):
            return f"state:{','.join(self.scope['states'])}"
        return "us"

    def _format_findings(self, findings: list[Finding]) -> str:
        if not findings:
            return "No results."
        parts = []
        for finding in findings:
            if finding.is_error:
                parts.append(f"ERROR [{finding.source_type or 'UNKNOWN'}] {finding.snippet}")
                continue
            date_str = f" ({finding.date})" if finding.date else ""
            cite_str = f" [{finding.citations} citations]" if finding.citations else ""
            parts.append(f"**{finding.title}**{date_str}{cite_str}\n{finding.snippet}\nSource: {finding.url}")
        return "\n\n---\n\n".join(parts)
