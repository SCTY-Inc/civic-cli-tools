"""Research tools for policy analysis."""

import os
from typing import Any

import httpx
from exa_py import Exa
from google.genai import types


# =============================================================================
# Tool Declarations (Gemini function calling)
# =============================================================================

def get_tool_declarations(scope: dict) -> list[types.FunctionDeclaration]:
    """Return Gemini function declarations based on scope."""
    tools = [
        # Always available
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
    ]

    if scope["type"] in ("federal", "all"):
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
        ])

    if scope["type"] in ("state", "all"):
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

    def execute(self, query: str) -> str:
        try:
            results = self.client.search_and_contents(
                query,
                type="auto",
                use_autoprompt=True,
                num_results=5,
                text={"max_characters": 1500},
                summary=True,
            )
            if not results.results:
                return f"No results for: {query}"

            formatted = []
            for r in results.results:
                entry = f"**{r.title}**\n"
                if hasattr(r, "summary") and r.summary:
                    entry += f"{r.summary}\n"
                elif hasattr(r, "text") and r.text:
                    entry += f"{r.text[:1000]}...\n"
                entry += f"Source: {r.url}"
                formatted.append(entry)
            return "\n\n---\n\n".join(formatted)
        except Exception as e:
            return f"Web search error: {e}"


class AcademicSearch:
    """Semantic Scholar academic paper search."""

    BASE_URL = "https://api.semanticscholar.org/graph/v1"

    def execute(self, query: str) -> str:
        try:
            with httpx.Client(timeout=30) as client:
                resp = client.get(
                    f"{self.BASE_URL}/paper/search",
                    params={
                        "query": query,
                        "limit": 5,
                        "fields": "title,abstract,year,citationCount,url,authors"
                    }
                )
                resp.raise_for_status()
                data = resp.json()

            if not data.get("data"):
                return f"No academic papers found for: {query}"

            formatted = []
            for paper in data["data"]:
                authors = ", ".join(a["name"] for a in paper.get("authors", [])[:3])
                if len(paper.get("authors", [])) > 3:
                    authors += " et al."

                entry = f"**{paper['title']}**\n"
                entry += f"Authors: {authors}\n"
                entry += f"Year: {paper.get('year', 'N/A')} | Citations: {paper.get('citationCount', 0)}\n"
                if paper.get("abstract"):
                    entry += f"{paper['abstract'][:500]}...\n"
                entry += f"URL: {paper.get('url', 'N/A')}"
                formatted.append(entry)

            return "\n\n---\n\n".join(formatted)
        except Exception as e:
            return f"Academic search error: {e}"


class CongressSearch:
    """Congress.gov legislation search."""

    BASE_URL = "https://api.congress.gov/v3"

    def execute(self, query: str) -> str:
        api_key = os.getenv("CONGRESS_GOV_API_KEY")
        if not api_key:
            return "CONGRESS_GOV_API_KEY not set"

        try:
            with httpx.Client(timeout=30) as client:
                resp = client.get(
                    f"{self.BASE_URL}/bill",
                    params={
                        "query": query,
                        "limit": 5,
                        "api_key": api_key
                    }
                )
                resp.raise_for_status()
                data = resp.json()

            bills = data.get("bills", [])
            if not bills:
                return f"No federal legislation found for: {query}"

            formatted = []
            for bill in bills:
                entry = f"**{bill.get('type', '')}{bill.get('number', '')}**: {bill.get('title', 'No title')}\n"
                entry += f"Congress: {bill.get('congress', 'N/A')} | "
                entry += f"Status: {bill.get('latestAction', {}).get('text', 'N/A')}\n"
                entry += f"Introduced: {bill.get('introducedDate', 'N/A')}\n"
                entry += f"URL: {bill.get('url', 'N/A')}"
                formatted.append(entry)

            return "\n\n---\n\n".join(formatted)
        except Exception as e:
            return f"Congress.gov search error: {e}"


class FederalRegisterSearch:
    """Federal Register rules and notices search."""

    BASE_URL = "https://www.federalregister.gov/api/v1"

    def execute(self, query: str) -> str:
        try:
            with httpx.Client(timeout=30) as client:
                resp = client.get(
                    f"{self.BASE_URL}/documents.json",
                    params={
                        "conditions[term]": query,
                        "per_page": 5,
                        "order": "relevance"
                    }
                )
                resp.raise_for_status()
                data = resp.json()

            results = data.get("results", [])
            if not results:
                return f"No Federal Register entries found for: {query}"

            formatted = []
            for doc in results:
                agencies = doc.get("agencies", [])
                agency_names = ", ".join(a.get("name", "") for a in agencies[:2]) or "N/A"

                entry = f"**{doc.get('title', 'No title')}**\n"
                entry += f"Type: {doc.get('type', 'N/A')} | Agency: {agency_names}\n"
                entry += f"Published: {doc.get('publication_date', 'N/A')}\n"
                entry += f"URL: {doc.get('html_url', 'N/A')}"
                formatted.append(entry)

            return "\n\n---\n\n".join(formatted)
        except Exception as e:
            return f"Federal Register search error: {e}"


class StateLegislationSearch:
    """OpenStates state legislation search."""

    BASE_URL = "https://v3.openstates.org"

    def __init__(self, default_states: list[str] = None):
        self.default_states = default_states or []

    def execute(self, query: str, state: str = None) -> str:
        api_key = os.getenv("OPENSTATES_API_KEY")
        if not api_key:
            return "OPENSTATES_API_KEY not set"

        # Use provided state, or default, or search all
        jurisdiction = state.lower() if state else (self.default_states[0].lower() if len(self.default_states) == 1 else None)

        try:
            with httpx.Client(timeout=30) as client:
                params = {
                    "q": query,
                    "per_page": 5,
                }
                if jurisdiction:
                    params["jurisdiction"] = jurisdiction

                resp = client.get(
                    f"{self.BASE_URL}/bills",
                    params=params,
                    headers={"X-API-KEY": api_key}
                )
                resp.raise_for_status()
                data = resp.json()

            bills = data.get("results", [])
            if not bills:
                return f"No state legislation found for: {query}"

            formatted = []
            for bill in bills:
                entry = f"**{bill.get('identifier', 'N/A')}** ({bill.get('jurisdiction', {}).get('name', 'N/A')})\n"
                entry += f"{bill.get('title', 'No title')}\n"
                entry += f"Session: {bill.get('session', 'N/A')} | "
                latest = bill.get("latest_action_description", "N/A")
                entry += f"Latest: {latest[:100]}...\n" if len(latest) > 100 else f"Latest: {latest}\n"
                entry += f"URL: {bill.get('openstates_url', 'N/A')}"
                formatted.append(entry)

            return "\n\n---\n\n".join(formatted)
        except Exception as e:
            return f"OpenStates search error: {e}"


# =============================================================================
# Tool Registry
# =============================================================================

class ToolRegistry:
    """Registry for executing tools by name."""

    def __init__(self, scope: dict):
        self.scope = scope
        self.web_search = WebSearch()
        self.academic_search = AcademicSearch()
        self.congress_search = CongressSearch()
        self.federal_register_search = FederalRegisterSearch()
        self.state_legislation_search = StateLegislationSearch(scope.get("states", []))

    def execute(self, tool_name: str, args: dict[str, Any]) -> str:
        """Execute a tool by name with given arguments."""
        if tool_name == "web_search":
            return self.web_search.execute(args.get("query", ""))
        elif tool_name == "academic_search":
            return self.academic_search.execute(args.get("query", ""))
        elif tool_name == "congress_search":
            return self.congress_search.execute(args.get("query", ""))
        elif tool_name == "federal_register_search":
            return self.federal_register_search.execute(args.get("query", ""))
        elif tool_name == "state_legislation_search":
            return self.state_legislation_search.execute(
                args.get("query", ""),
                args.get("state")
            )
        else:
            return f"Unknown tool: {tool_name}"
