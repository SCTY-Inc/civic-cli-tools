"""Tool implementations for policy research."""

import os

from exa_py import Exa

from .base import BaseTool, RESULTS_LIMIT, get_env_key
from .models import Finding


class WebSearch(BaseTool):
    """Exa-powered web search."""

    SOURCE_TYPE = "WEB"

    def __init__(self):
        self._client = None

    @property
    def client(self) -> Exa:
        if self._client is None:
            api_key = get_env_key("EXA_API_KEY")
            if not api_key:
                raise ValueError("EXA_API_KEY not set")
            self._client = Exa(api_key=api_key)
        return self._client

    def execute(self, query: str = "", **kwargs) -> list[Finding]:
        try:
            results = self.client.search_and_contents(
                query, type="auto", use_autoprompt=True,
                num_results=RESULTS_LIMIT, text={"max_characters": 1500}, summary=True,
            )
            findings = []
            for r in results.results:
                snippet = getattr(r, "summary", "") or getattr(r, "text", "")[:1000]
                date = (getattr(r, "published_date", "") or "")[:10]
                findings.append(Finding(
                    title=r.title or "Untitled", snippet=snippet, url=r.url,
                    date=date, source_type=self.SOURCE_TYPE,
                ))
            return findings
        except Exception as e:
            return self._error(str(e))


class AcademicSearch(BaseTool):
    """Semantic Scholar academic paper search."""

    SOURCE_TYPE = "ACADEMIC"
    BASE_URL = "https://api.semanticscholar.org/graph/v1"

    def execute(self, query: str = "", **kwargs) -> list[Finding]:
        try:
            data = self._fetch_json(
                f"{self.BASE_URL}/paper/search",
                params={"query": query, "limit": RESULTS_LIMIT,
                        "fields": "title,abstract,year,citationCount,url,authors"}
            )
            findings = []
            for paper in data.get("data", []):
                authors = ", ".join(a["name"] for a in paper.get("authors", [])[:3])
                if len(paper.get("authors", [])) > 3:
                    authors += " et al."
                findings.append(Finding(
                    title=paper.get("title", "Untitled"),
                    snippet=f"Authors: {authors}\n{paper.get('abstract', '')[:600]}",
                    url=paper.get("url", ""), date=str(paper.get("year", "")),
                    source_type=self.SOURCE_TYPE, citations=paper.get("citationCount", 0),
                ))
            return findings
        except Exception as e:
            return self._error(str(e))


class CongressSearch(BaseTool):
    """Congress.gov legislation search."""

    SOURCE_TYPE = "CONGRESS"
    BASE_URL = "https://api.congress.gov/v3"

    def execute(self, query: str = "", **kwargs) -> list[Finding]:
        api_key = get_env_key("CONGRESS_GOV_API_KEY")
        if not api_key:
            return self._error("CONGRESS_GOV_API_KEY not set")
        try:
            data = self._fetch_json(
                f"{self.BASE_URL}/bill",
                params={"query": query, "limit": RESULTS_LIMIT, "api_key": api_key}
            )
            findings = []
            for bill in data.get("bills", []):
                bill_id = f"{bill.get('type', '')}{bill.get('number', '')}"
                status = bill.get("latestAction", {}).get("text", "N/A")
                findings.append(Finding(
                    title=f"{bill_id}: {bill.get('title', 'No title')}",
                    snippet=f"Congress {bill.get('congress', 'N/A')} | Status: {status}",
                    url=bill.get("url", ""), date=bill.get("introducedDate", ""),
                    source_type=self.SOURCE_TYPE,
                ))
            return findings
        except Exception as e:
            return self._error(str(e))


class FederalRegisterSearch(BaseTool):
    """Federal Register rules and notices search."""

    SOURCE_TYPE = "FED_REGISTER"
    BASE_URL = "https://www.federalregister.gov/api/v1"

    def execute(self, query: str = "", **kwargs) -> list[Finding]:
        try:
            data = self._fetch_json(
                f"{self.BASE_URL}/documents.json",
                params={"conditions[term]": query, "per_page": RESULTS_LIMIT, "order": "relevance"}
            )
            findings = []
            for doc in data.get("results", []):
                agencies = ", ".join(a.get("name", "") for a in doc.get("agencies", [])[:2]) or "N/A"
                snippet = f"Type: {doc.get('type', 'N/A')} | Agency: {agencies}"
                if doc.get("abstract"):
                    snippet += f"\n{doc['abstract'][:500]}"
                findings.append(Finding(
                    title=doc.get("title", "Untitled"), snippet=snippet,
                    url=doc.get("html_url", ""), date=doc.get("publication_date", ""),
                    source_type=self.SOURCE_TYPE,
                ))
            return findings
        except Exception as e:
            return self._error(str(e))


class CourtSearch(BaseTool):
    """CourtListener federal case law search."""

    SOURCE_TYPE = "COURT"
    BASE_URL = "https://www.courtlistener.com/api/rest/v4"

    def execute(self, query: str = "", **kwargs) -> list[Finding]:
        try:
            data = self._fetch_json(
                f"{self.BASE_URL}/search/",
                params={"q": query, "type": "o", "order_by": "score desc", "page_size": RESULTS_LIMIT}
            )
            findings = []
            for case in data.get("results", []):
                snippet = f"Court: {case.get('court', 'N/A')}"
                if case.get("snippet"):
                    clean = case["snippet"].replace("<mark>", "**").replace("</mark>", "**")
                    snippet += f"\n{clean[:500]}"
                findings.append(Finding(
                    title=case.get("caseName", "Unknown Case"), snippet=snippet,
                    url=f"https://www.courtlistener.com{case.get('absolute_url', '')}",
                    date=case.get("dateFiled", ""), source_type=self.SOURCE_TYPE,
                ))
            return findings
        except Exception as e:
            return self._error(str(e))


class CensusSearch(BaseTool):
    """US Census Bureau data search."""

    SOURCE_TYPE = "CENSUS"
    BASE_URL = "https://api.census.gov/data"
    VARIABLES = {
        "population": "B01003_001E", "income": "B19013_001E",
        "poverty": "B17001_002E", "housing": "B25001_001E",
        "education": "B15003_022E", "unemployment": "B23025_005E",
    }

    def execute(self, topic: str = "", geography: str = "us", **kwargs) -> list[Finding]:
        api_key = get_env_key("CENSUS_API_KEY")
        topic_lower = topic.lower()
        variable = next((v for k, v in self.VARIABLES.items() if k in topic_lower), "B01003_001E")
        geo_params = self._parse_geography(geography)

        try:
            params = {"get": f"NAME,{variable}", **geo_params}
            if api_key:
                params["key"] = api_key
            data = self._fetch_json(f"{self.BASE_URL}/2022/acs/acs5", params=params)

            if len(data) < 2:
                return self._error(f"No census data for {topic}")

            findings = []
            headers = data[0]
            for row in data[1:6]:
                findings.append(Finding(
                    title=row[0], snippet=f"{headers[1]}: {row[1]}",
                    url="https://data.census.gov", date="2022", source_type=self.SOURCE_TYPE,
                ))
            return findings
        except Exception as e:
            return self._error(str(e))

    def _parse_geography(self, geography: str) -> dict:
        if geography == "us" or not geography:
            return {"for": "us:*"}
        elif geography.startswith("state:"):
            return {"for": "state:*"}
        elif geography.startswith("county:"):
            return {"for": "county:*", "in": "state:*"}
        return {"for": "state:*"}


class StateLegislationSearch(BaseTool):
    """OpenStates state legislation search."""

    SOURCE_TYPE = "STATE_LEG"
    BASE_URL = "https://v3.openstates.org"

    def __init__(self, default_states: list[str] = None):
        self.default_states = default_states or []

    def execute(self, query: str = "", state: str = None, **kwargs) -> list[Finding]:
        api_key = get_env_key("OPENSTATES_API_KEY")
        if not api_key:
            return self._error("OPENSTATES_API_KEY not set")

        jurisdiction = state.lower() if state else (
            self.default_states[0].lower() if len(self.default_states) == 1 else None
        )

        try:
            params = {"q": query, "per_page": RESULTS_LIMIT}
            if jurisdiction:
                params["jurisdiction"] = jurisdiction
            data = self._fetch_json(f"{self.BASE_URL}/bills", params=params,
                                    headers={"X-API-KEY": api_key})

            findings = []
            for bill in data.get("results", []):
                state_name = bill.get("jurisdiction", {}).get("name", "N/A")
                latest = bill.get("latest_action_description", "N/A")[:100]
                findings.append(Finding(
                    title=f"{bill.get('identifier', 'N/A')}: {bill.get('title', 'No title')[:80]}",
                    snippet=f"State: {state_name} | Session: {bill.get('session', 'N/A')} | Latest: {latest}",
                    url=bill.get("openstates_url", ""), date=bill.get("latest_action_date", ""),
                    source_type=self.SOURCE_TYPE,
                ))
            return findings
        except Exception as e:
            return self._error(str(e))
