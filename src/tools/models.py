"""Data models for research findings."""

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(slots=True)
class Finding:
    """Single research finding with metadata."""

    title: str
    snippet: str
    url: str
    date: str = ""
    source_type: str = ""
    citations: int = 0
    is_error: bool = False

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "snippet": self.snippet,
            "url": self.url,
            "date": self.date,
            "source_type": self.source_type,
            "citations": self.citations,
            "is_error": self.is_error,
        }


@dataclass
class ResearchResults:
    """Aggregated results from all tools."""

    findings: list[Finding] = field(default_factory=list)
    tool_usage: dict[str, int] = field(default_factory=dict)

    @property
    def evidence(self) -> list[Finding]:
        return [finding for finding in self.findings if not finding.is_error]

    @property
    def errors(self) -> list[Finding]:
        return [finding for finding in self.findings if finding.is_error]

    def add(self, finding: Finding) -> None:
        self.findings.append(finding)

    def extend(self, findings: list[Finding]) -> None:
        self.findings.extend(findings)

    def record_tool_call(self, tool_name: str) -> None:
        self.tool_usage[tool_name] = self.tool_usage.get(tool_name, 0) + 1

    def absorb(self, other: "ResearchResults") -> None:
        self.findings.extend(other.findings)
        for tool_name, count in other.tool_usage.items():
            self.tool_usage[tool_name] = self.tool_usage.get(tool_name, 0) + count

    def confidence_score(self) -> tuple[str, str]:
        """Calculate confidence from successful findings only."""
        evidence = self.evidence
        if not evidence:
            return "LOW", "No successful findings"

        source_types = {finding.source_type for finding in evidence}
        diversity = min(len(source_types) / 5, 1.0)

        current_year = datetime.now(timezone.utc).year
        recency_scores = []
        for finding in evidence:
            if not finding.date:
                continue
            try:
                age = current_year - int(finding.date[:4])
            except (TypeError, ValueError):
                continue
            recency_scores.append(max(0.0, 1 - (age * 0.2)))
        recency = sum(recency_scores) / len(recency_scores) if recency_scores else 0.0

        cited = [finding for finding in evidence if finding.citations > 0]
        citation_score = min(len(cited) / 3, 1.0)
        score = (diversity * 0.4) + (recency * 0.3) + (citation_score * 0.3)

        if score >= 0.7 and len(source_types) >= 5 and citation_score > 0:
            level, dots = "HIGH", "●●●●●"
        elif score >= 0.4 and len(source_types) >= 3:
            level, dots = "MEDIUM", "●●●○○"
        else:
            level, dots = "LOW", "●○○○○"

        return level, (
            f"{dots} {level} — {len(source_types)} source types, "
            f"{len(evidence)} findings, {len(cited)} cited item(s)"
        )

    def to_dict(self) -> dict:
        level, detail = self.confidence_score()
        output = {
            "confidence": {"level": level, "detail": detail},
            "findings": [finding.to_dict() for finding in self.evidence],
            "tool_usage": self.tool_usage,
        }
        if self.errors:
            output["errors"] = [finding.to_dict() for finding in self.errors]
        return output

    def _group_by_source(self, findings: list[Finding]) -> dict[str, list[Finding]]:
        by_source: dict[str, list[Finding]] = {}
        for finding in findings:
            by_source.setdefault(finding.source_type, []).append(finding)
        return by_source

    def to_text(self) -> str:
        """Format successful findings for LLM consumption."""
        evidence = self.evidence
        if not evidence:
            return "No successful findings."

        parts = []
        for source, items in sorted(self._group_by_source(evidence).items()):
            parts.append(f"## [{source}]")
            for finding in items:
                date_str = f" ({finding.date})" if finding.date else ""
                cite_str = f" [{finding.citations} citations]" if finding.citations else ""
                parts.append(f"**{finding.title}**{date_str}{cite_str}")
                parts.append(finding.snippet[:800])
                parts.append(f"Source: {finding.url}\n")
        return "\n".join(parts)

    def to_appendix(self) -> str:
        """Format successful findings as appendix with a separate tool-error section."""
        _, confidence = self.confidence_score()
        parts = [f"## Appendix: Source Data\n\n**Research Confidence:** {confidence}\n"]

        evidence = self.evidence
        if not evidence:
            parts.append("No successful findings were collected.\n")
        else:
            for source, items in sorted(self._group_by_source(evidence).items()):
                parts.append(f"### {source} ({len(items)} results)")
                for index, finding in enumerate(items, 1):
                    date_str = f"[{finding.date}] " if finding.date else ""
                    cite_str = f" ({finding.citations} citations)" if finding.citations else ""
                    parts.append(f"{index}. {date_str}**{finding.title}**{cite_str}")
                    parts.append(f"   {finding.url}")
                parts.append("")

        if self.errors:
            parts.append(f"### Tool errors ({len(self.errors)})")
            for finding in self.errors:
                parts.append(f"- [{finding.source_type or 'UNKNOWN'}] {finding.snippet}")
            parts.append("")

        return "\n".join(parts).strip() + "\n"
