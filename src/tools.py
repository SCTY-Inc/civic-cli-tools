"""Research tools for policy analysis."""

import os
from dataclasses import dataclass, field
from typing import Any

import httpx
from exa_py import Exa
from google.genai import types


@dataclass
class Finding:
    """Single research finding with metadata."""
    title: str
    snippet: str
    url: str
    date: str = ""
    source_type: str = ""
    citations: int = 0


@dataclass
class ResearchResults:
    """Aggregated results from all tools."""
    findings: list[Finding] = field(default_factory=list)
    tool_usage: dict[str, int] = field(default_factory=dict)

    def add(self, finding: Finding, tool_name: str):
        self.findings.append(finding)
        self.tool_usage[tool_name] = self.tool_usage.get(tool_name, 0) + 1

    def confidence_score(self) -> tuple[str, str]:
        """Calculate overall confidence based on source diversity and recency.

        Returns (level, explanation) where level is HIGH/MEDIUM/LOW
        """
        from datetime import datetime

        if not self.findings:
            return "LOW", "No findings"

        # Source diversity (0-1)
        source_types = set(f.source_type for f in self.findings)
        diversity = min(len(source_types) / 5, 1.0)  # 5+ sources = max

        # Recency score (0-1)
        current_year = datetime.now().year
        recency_scores = []
        for f in self.findings:
            if f.date:
                try:
                    year = int(f.date[:4])
                    age = current_year - year
                    recency_scores.append(max(0, 1 - (age * 0.2)))  # -20% per year
                except:
                    pass
        recency = sum(recency_scores) / len(recency_scores) if recency_scores else 0.5

        # Citation strength (0-1)
        cited = [f for f in self.findings if f.citations > 0]
        citation_score = min(len(cited) / 3, 1.0) if cited else 0.3

        # Combined score
        score = (diversity * 0.4) + (recency * 0.3) + (citation_score * 0.3)

        if score >= 0.7:
            level = "HIGH"
            dots = "●●●●●"
        elif score >= 0.4:
            level = "MEDIUM"
            dots = "●●●○○"
        else:
            level = "LOW"
            dots = "●○○○○"

        explanation = f"{dots} {level} — {len(source_types)} source types, {len(self.findings)} findings"
        return level, explanation

    def to_text(self) -> str:
        """Format findings for LLM consumption."""
        by_source = {}
        for f in self.findings:
            by_source.setdefault(f.source_type, []).append(f)

        parts = []
        for source, items in by_source.items():
            parts.append(f"\n## [{source}]\n")
            for f in items:
                date_str = f" ({f.date})" if f.date else ""
                cite_str = f" [{f.citations} citations]" if f.citations else ""
                parts.append(f"**{f.title}**{date_str}{cite_str}")
                parts.append(f"{f.snippet[:800]}")
                parts.append(f"Source: {f.url}\n")
        return "\n".join(parts)

    def to_appendix(self) -> str:
        """Format raw findings as appendix."""
        by_source = {}
        for f in self.findings:
            by_source.setdefault(f.source_type, []).append(f)

        # Add confidence header
        _, confidence_str = self.confidence_score()
        parts = [f"## Appendix: Source Data\n\n**Research Confidence:** {confidence_str}\n"]

        for source, items in sorted(by_source.items()):
            parts.append(f"### {source} ({len(items)} results)")
            for i, f in enumerate(items, 1):
                date_str = f"[{f.date}] " if f.date else ""
                cite_str = f" ({f.citations} citations)" if f.citations else ""
                parts.append(f"{i}. {date_str}**{f.title}**{cite_str}")
                parts.append(f"   {f.url}")
            parts.append("")
        return "\n".join(parts)


# =============================================================================
# Tool Declarations (Gemini function calling)
# =============================================================================

def get_tool_declarations(scope: dict) -> list[types.FunctionDeclaration]:
    """Return Gemini function declarations based on scope."""
    scope_type = scope["type"]

    # News-only mode: just web search
    if scope_type == "news":
        return [
            types.FunctionDeclaration(
                name="web_search",
                description="Search the web for current news, articles, and media coverage",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "query": types.Schema(type="STRING", description="Search query"),
                    },
                    required=["query"],
                ),
            ),
        ]

    # Policy-only mode: legislation and regulatory sources
    if scope_type == "policy":
        return [
            types.FunctionDeclaration(
                name="congress_search",
                description="Search federal legislation on Congress.gov - bills, resolutions, amendments",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "query": types.Schema(type="STRING", description="Legislation search terms"),
                    },
                    required=["query"],
                ),
            ),
            types.FunctionDeclaration(
                name="federal_register_search",
                description="Search Federal Register for rules, proposed rules, and agency notices",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "query": types.Schema(type="STRING", description="Regulation search terms"),
                    },
                    required=["query"],
                ),
            ),
            types.FunctionDeclaration(
                name="court_search",
                description="Search federal case law and court opinions on CourtListener",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "query": types.Schema(type="STRING", description="Legal search terms, case names, or topics"),
                    },
                    required=["query"],
                ),
            ),
            types.FunctionDeclaration(
                name="state_legislation_search",
                description="Search state legislation via OpenStates",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "query": types.Schema(type="STRING", description="Legislation search terms"),
                        "state": types.Schema(type="STRING", description="State code (e.g., CA, NY)"),
                    },
                    required=["query"],
                ),
            ),
        ]

    # Standard modes
    tools = [
        types.FunctionDeclaration(
            name="web_search",
            description="Search the web for current news, articles, and general policy information",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "query": types.Schema(type="STRING", description="Search query"),
                },
                required=["query"],
            ),
        ),
        types.FunctionDeclaration(
            name="academic_search",
            description="Search academic papers and research studies on Semantic Scholar (200M+ papers)",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "query": types.Schema(type="STRING", description="Research topic or keywords"),
                },
                required=["query"],
            ),
        ),
        types.FunctionDeclaration(
            name="census_search",
            description="Search US Census data for demographics, population, housing, and economic statistics",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "topic": types.Schema(type="STRING", description="Data topic (e.g., population, income, housing, education)"),
                    "geography": types.Schema(type="STRING", description="Geographic level: us, state:XX, or county:XXXXX"),
                },
                required=["topic"],
            ),
        ),
    ]

    if scope_type in ("federal", "all"):
        tools.extend([
            types.FunctionDeclaration(
                name="congress_search",
                description="Search federal legislation on Congress.gov - bills, resolutions, amendments",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "query": types.Schema(type="STRING", description="Legislation search terms"),
                    },
                    required=["query"],
                ),
            ),
            types.FunctionDeclaration(
                name="federal_register_search",
                description="Search Federal Register for rules, proposed rules, and agency notices",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "query": types.Schema(type="STRING", description="Regulation search terms"),
                    },
                    required=["query"],
                ),
            ),
            types.FunctionDeclaration(
                name="court_search",
                description="Search federal case law and court opinions on CourtListener",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "query": types.Schema(type="STRING", description="Legal search terms, case names, or topics"),
                    },
                    required=["query"],
                ),
            ),
        ])

    if scope_type in ("state", "all"):
        states_desc = "all states" if scope["type"] == "all" else ", ".join(scope["states"])
        tools.append(
            types.FunctionDeclaration(
                name="state_legislation_search",
                description=f"Search state legislation via OpenStates ({states_desc})",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "query": types.Schema(type="STRING", description="Legislation search terms"),
                        "state": types.Schema(type="STRING", description="State code (e.g., CA, NY) - optional if scope is single state"),
                    },
                    required=["query"],
                ),
            ),
        )

    return tools


# =============================================================================
# Tool Implementations
# =============================================================================

RESULTS_LIMIT = 10  # Increased from 5


class WebSearch:
    """Exa-powered web search."""

    def __init__(self):
        self._client = None

    @property
    def client(self) -> Exa:
        if self._client is None:
            api_key = os.getenv("EXA_API_KEY")
            if not api_key:
                raise ValueError("EXA_API_KEY not set")
            self._client = Exa(api_key=api_key)
        return self._client

    def execute(self, query: str) -> list[Finding]:
        try:
            results = self.client.search_and_contents(
                query,
                type="auto",
                use_autoprompt=True,
                num_results=RESULTS_LIMIT,
                text={"max_characters": 1500},
                summary=True,
            )
            findings = []
            for r in results.results:
                snippet = getattr(r, "summary", "") or getattr(r, "text", "")[:1000]
                date = getattr(r, "published_date", "") or ""
                if date:
                    date = date[:10]  # YYYY-MM-DD
                findings.append(Finding(
                    title=r.title or "Untitled",
                    snippet=snippet,
                    url=r.url,
                    date=date,
                    source_type="WEB",
                ))
            return findings
        except Exception as e:
            return [Finding(title="Error", snippet=str(e), url="", source_type="WEB")]


class AcademicSearch:
    """Semantic Scholar academic paper search."""

    BASE_URL = "https://api.semanticscholar.org/graph/v1"

    def execute(self, query: str) -> list[Finding]:
        try:
            with httpx.Client(timeout=30) as client:
                resp = client.get(
                    f"{self.BASE_URL}/paper/search",
                    params={
                        "query": query,
                        "limit": RESULTS_LIMIT,
                        "fields": "title,abstract,year,citationCount,url,authors"
                    }
                )
                resp.raise_for_status()
                data = resp.json()

            findings = []
            for paper in data.get("data", []):
                authors = ", ".join(a["name"] for a in paper.get("authors", [])[:3])
                if len(paper.get("authors", [])) > 3:
                    authors += " et al."
                snippet = f"Authors: {authors}\n{paper.get('abstract', '')[:600]}"
                findings.append(Finding(
                    title=paper.get("title", "Untitled"),
                    snippet=snippet,
                    url=paper.get("url", ""),
                    date=str(paper.get("year", "")),
                    source_type="ACADEMIC",
                    citations=paper.get("citationCount", 0),
                ))
            return findings
        except Exception as e:
            return [Finding(title="Error", snippet=str(e), url="", source_type="ACADEMIC")]


class CongressSearch:
    """Congress.gov legislation search."""

    BASE_URL = "https://api.congress.gov/v3"

    def execute(self, query: str) -> list[Finding]:
        api_key = os.getenv("CONGRESS_GOV_API_KEY")
        if not api_key:
            return [Finding(title="Error", snippet="CONGRESS_GOV_API_KEY not set", url="", source_type="CONGRESS")]

        try:
            with httpx.Client(timeout=30) as client:
                resp = client.get(
                    f"{self.BASE_URL}/bill",
                    params={"query": query, "limit": RESULTS_LIMIT, "api_key": api_key}
                )
                resp.raise_for_status()
                data = resp.json()

            findings = []
            for bill in data.get("bills", []):
                bill_id = f"{bill.get('type', '')}{bill.get('number', '')}"
                title = bill.get("title", "No title")
                status = bill.get("latestAction", {}).get("text", "N/A")
                snippet = f"Congress {bill.get('congress', 'N/A')} | Status: {status}"
                findings.append(Finding(
                    title=f"{bill_id}: {title}",
                    snippet=snippet,
                    url=bill.get("url", ""),
                    date=bill.get("introducedDate", ""),
                    source_type="CONGRESS",
                ))
            return findings
        except Exception as e:
            return [Finding(title="Error", snippet=str(e), url="", source_type="CONGRESS")]


class FederalRegisterSearch:
    """Federal Register rules and notices search."""

    BASE_URL = "https://www.federalregister.gov/api/v1"

    def execute(self, query: str) -> list[Finding]:
        try:
            with httpx.Client(timeout=30) as client:
                resp = client.get(
                    f"{self.BASE_URL}/documents.json",
                    params={"conditions[term]": query, "per_page": RESULTS_LIMIT, "order": "relevance"}
                )
                resp.raise_for_status()
                data = resp.json()

            findings = []
            for doc in data.get("results", []):
                agencies = ", ".join(a.get("name", "") for a in doc.get("agencies", [])[:2]) or "N/A"
                snippet = f"Type: {doc.get('type', 'N/A')} | Agency: {agencies}"
                if doc.get("abstract"):
                    snippet += f"\n{doc['abstract'][:500]}"
                findings.append(Finding(
                    title=doc.get("title", "Untitled"),
                    snippet=snippet,
                    url=doc.get("html_url", ""),
                    date=doc.get("publication_date", ""),
                    source_type="FED_REGISTER",
                ))
            return findings
        except Exception as e:
            return [Finding(title="Error", snippet=str(e), url="", source_type="FED_REGISTER")]


class CourtSearch:
    """CourtListener federal case law search."""

    BASE_URL = "https://www.courtlistener.com/api/rest/v4"

    def execute(self, query: str) -> list[Finding]:
        try:
            with httpx.Client(timeout=30) as client:
                resp = client.get(
                    f"{self.BASE_URL}/search/",
                    params={"q": query, "type": "o", "order_by": "score desc", "page_size": RESULTS_LIMIT}
                )
                resp.raise_for_status()
                data = resp.json()

            findings = []
            for case in data.get("results", []):
                snippet = f"Court: {case.get('court', 'N/A')}"
                if case.get("snippet"):
                    clean = case["snippet"].replace("<mark>", "**").replace("</mark>", "**")
                    snippet += f"\n{clean[:500]}"
                findings.append(Finding(
                    title=case.get("caseName", "Unknown Case"),
                    snippet=snippet,
                    url=f"https://www.courtlistener.com{case.get('absolute_url', '')}",
                    date=case.get("dateFiled", ""),
                    source_type="COURT",
                ))
            return findings
        except Exception as e:
            return [Finding(title="Error", snippet=str(e), url="", source_type="COURT")]


class CensusSearch:
    """US Census Bureau data search."""

    BASE_URL = "https://api.census.gov/data"
    VARIABLES = {
        "population": "B01003_001E",
        "income": "B19013_001E",
        "poverty": "B17001_002E",
        "housing": "B25001_001E",
        "education": "B15003_022E",
        "unemployment": "B23025_005E",
    }

    def execute(self, topic: str, geography: str = "us") -> list[Finding]:
        api_key = os.getenv("CENSUS_API_KEY")

        topic_lower = topic.lower()
        variable = next((v for k, v in self.VARIABLES.items() if k in topic_lower), "B01003_001E")
        geo_params = self._parse_geography(geography)

        try:
            params = {"get": f"NAME,{variable}", **geo_params}
            if api_key:
                params["key"] = api_key

            with httpx.Client(timeout=30) as client:
                resp = client.get(f"{self.BASE_URL}/2022/acs/acs5", params=params)
                resp.raise_for_status()
                data = resp.json()

            if len(data) < 2:
                return [Finding(title="No data", snippet=f"No census data for {topic}", url="", source_type="CENSUS")]

            findings = []
            headers = data[0]
            for row in data[1:6]:
                findings.append(Finding(
                    title=row[0],
                    snippet=f"{headers[1]}: {row[1]}",
                    url="https://data.census.gov",
                    date="2022",
                    source_type="CENSUS",
                ))
            return findings
        except Exception as e:
            return [Finding(title="Error", snippet=str(e), url="", source_type="CENSUS")]

    def _parse_geography(self, geography: str) -> dict:
        if geography == "us" or not geography:
            return {"for": "us:*"}
        elif geography.startswith("state:"):
            return {"for": "state:*"}
        elif geography.startswith("county:"):
            return {"for": "county:*", "in": "state:*"}
        return {"for": "state:*"}


class StateLegislationSearch:
    """OpenStates state legislation search."""

    BASE_URL = "https://v3.openstates.org"

    def __init__(self, default_states: list[str] = None):
        self.default_states = default_states or []

    def execute(self, query: str, state: str = None) -> list[Finding]:
        api_key = os.getenv("OPENSTATES_API_KEY")
        if not api_key:
            return [Finding(title="Error", snippet="OPENSTATES_API_KEY not set", url="", source_type="STATE_LEG")]

        jurisdiction = state.lower() if state else (self.default_states[0].lower() if len(self.default_states) == 1 else None)

        try:
            params = {"q": query, "per_page": RESULTS_LIMIT}
            if jurisdiction:
                params["jurisdiction"] = jurisdiction

            with httpx.Client(timeout=30) as client:
                resp = client.get(
                    f"{self.BASE_URL}/bills",
                    params=params,
                    headers={"X-API-KEY": api_key}
                )
                resp.raise_for_status()
                data = resp.json()

            findings = []
            for bill in data.get("results", []):
                state_name = bill.get("jurisdiction", {}).get("name", "N/A")
                latest = bill.get("latest_action_description", "N/A")[:100]
                snippet = f"State: {state_name} | Session: {bill.get('session', 'N/A')} | Latest: {latest}"
                findings.append(Finding(
                    title=f"{bill.get('identifier', 'N/A')}: {bill.get('title', 'No title')[:80]}",
                    snippet=snippet,
                    url=bill.get("openstates_url", ""),
                    date=bill.get("latest_action_date", ""),
                    source_type="STATE_LEG",
                ))
            return findings
        except Exception as e:
            return [Finding(title="Error", snippet=str(e), url="", source_type="STATE_LEG")]


# =============================================================================
# Tool Registry
# =============================================================================

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
            "court_search": CourtSearch(),
            "state_legislation_search": StateLegislationSearch(scope.get("states", [])),
        }

    def execute(self, tool_name: str, args: dict[str, Any]) -> tuple[list[Finding], str]:
        """Execute tool, return (findings, formatted_text)."""
        tool = self._tools.get(tool_name)
        if not tool:
            return [], f"Unknown tool: {tool_name}"

        if tool_name == "census_search":
            findings = tool.execute(args.get("topic", ""), args.get("geography", "us"))
        elif tool_name == "state_legislation_search":
            findings = tool.execute(args.get("query", ""), args.get("state"))
        else:
            findings = tool.execute(args.get("query", ""))

        # Format for LLM
        formatted = []
        for f in findings:
            date_str = f" ({f.date})" if f.date else ""
            cite_str = f" [{f.citations} citations]" if f.citations else ""
            formatted.append(f"**{f.title}**{date_str}{cite_str}\n{f.snippet}\nSource: {f.url}")
        return findings, "\n\n---\n\n".join(formatted)
