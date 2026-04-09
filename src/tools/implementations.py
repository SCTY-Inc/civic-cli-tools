"""Tool implementations for policy research."""

import os

import httpx
from exa_py import Exa

from .base import BaseTool, RESULTS_LIMIT, get_env_key
from .models import Finding

STATE_FIPS = {
    "AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06",
    "CO": "08", "CT": "09", "DE": "10", "DC": "11", "FL": "12",
    "GA": "13", "HI": "15", "ID": "16", "IL": "17", "IN": "18",
    "IA": "19", "KS": "20", "KY": "21", "LA": "22", "ME": "23",
    "MD": "24", "MA": "25", "MI": "26", "MN": "27", "MS": "28",
    "MO": "29", "MT": "30", "NE": "31", "NV": "32", "NH": "33",
    "NJ": "34", "NM": "35", "NY": "36", "NC": "37", "ND": "38",
    "OH": "39", "OK": "40", "OR": "41", "PA": "42", "PR": "72",
    "RI": "44", "SC": "45", "SD": "46", "TN": "47", "TX": "48",
    "UT": "49", "VT": "50", "VA": "51", "WA": "53", "WV": "54",
    "WI": "55", "WY": "56",
}


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
        if not query:
            return self._error("No query provided")
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
        except ValueError:
            raise
        except Exception as e:
            return self._error(f"Web search failed: {e}")


class AcademicSearch(BaseTool):
    """Semantic Scholar academic paper search."""

    SOURCE_TYPE = "ACADEMIC"
    BASE_URL = "https://api.semanticscholar.org/graph/v1"

    def execute(self, query: str = "", **kwargs) -> list[Finding]:
        if not query:
            return self._error("No query provided")
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
        except (httpx.HTTPStatusError, httpx.TransportError) as e:
            return self._error(f"Semantic Scholar API error: {e}")
        except (KeyError, ValueError) as e:
            return self._error(f"Failed to parse academic results: {e}")


class CongressSearch(BaseTool):
    """Congress.gov legislation search."""

    SOURCE_TYPE = "CONGRESS"
    BASE_URL = "https://api.congress.gov/v3"

    def execute(self, query: str = "", **kwargs) -> list[Finding]:
        api_key = get_env_key("CONGRESS_GOV_API_KEY")
        if not api_key:
            return self._error("CONGRESS_GOV_API_KEY not set")
        if not query:
            return self._error("No query provided")
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
        except (httpx.HTTPStatusError, httpx.TransportError) as e:
            return self._error(f"Congress.gov API error: {e}")
        except (KeyError, ValueError) as e:
            return self._error(f"Failed to parse Congress results: {e}")


class FederalRegisterSearch(BaseTool):
    """Federal Register rules and notices search."""

    SOURCE_TYPE = "FED_REGISTER"
    BASE_URL = "https://www.federalregister.gov/api/v1"

    def execute(self, query: str = "", **kwargs) -> list[Finding]:
        if not query:
            return self._error("No query provided")
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
        except (httpx.HTTPStatusError, httpx.TransportError) as e:
            return self._error(f"Federal Register API error: {e}")
        except (KeyError, ValueError) as e:
            return self._error(f"Failed to parse Federal Register results: {e}")


class RegulationsSearch(BaseTool):
    """Regulations.gov dockets, comments, and rulemaking documents."""

    SOURCE_TYPE = "REGULATIONS"
    BASE_URL = "https://api.regulations.gov/v4"

    def execute(self, query: str = "", **kwargs) -> list[Finding]:
        api_key = get_env_key("REGULATIONS_GOV_API_KEY")
        if not api_key:
            return self._error("REGULATIONS_GOV_API_KEY not set")
        if not query:
            return self._error("No query provided")
        try:
            data = self._fetch_json(
                f"{self.BASE_URL}/documents",
                params={
                    "filter[searchTerm]": query,
                    "page[size]": RESULTS_LIMIT,
                    "api_key": api_key,
                },
            )
            findings = []
            for doc in data.get("data", []):
                attrs = doc.get("attributes", {})
                summary = attrs.get("summary", "") or ""
                snippet = f"Type: {attrs.get('documentType', 'N/A')} | Agency: {attrs.get('agencyId', 'N/A')}"
                if summary:
                    snippet += f"\n{summary[:500]}"
                findings.append(Finding(
                    title=attrs.get("title", "Untitled"),
                    snippet=snippet,
                    url=f"https://www.regulations.gov/document/{doc.get('id', '')}",
                    date=(attrs.get("postedDate", "") or "")[:10],
                    source_type=self.SOURCE_TYPE,
                ))
            return findings
        except (httpx.HTTPStatusError, httpx.TransportError) as e:
            return self._error(f"Regulations.gov API error: {e}")
        except (KeyError, ValueError) as e:
            return self._error(f"Failed to parse Regulations.gov results: {e}")


class CourtSearch(BaseTool):
    """CourtListener federal case law search."""

    SOURCE_TYPE = "COURT"
    BASE_URL = "https://www.courtlistener.com/api/rest/v4"

    def execute(self, query: str = "", **kwargs) -> list[Finding]:
        if not query:
            return self._error("No query provided")
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
        except (httpx.HTTPStatusError, httpx.TransportError) as e:
            return self._error(f"CourtListener API error: {e}")
        except (KeyError, ValueError) as e:
            return self._error(f"Failed to parse court results: {e}")


class CensusSearch(BaseTool):
    """US Census Bureau data search."""

    SOURCE_TYPE = "CENSUS"
    BASE_URL = "https://api.census.gov/data"

    VARIABLES = {
        # Demographics
        "population": "B01003_001E",
        "median_age": "B01002_001E",
        # Income & poverty
        "income": "B19013_001E",
        "poverty": "B17001_002E",
        "gini": "B19083_001E",
        # Housing
        "housing": "B25001_001E",
        "median_rent": "B25064_001E",
        "homeownership": "B25003_002E",
        "vacancy": "B25002_003E",
        # Education
        "education": "B15003_022E",
        "bachelors": "B15003_022E",
        "high_school": "B15003_017E",
        # Employment
        "unemployment": "B23025_005E",
        "labor_force": "B23025_002E",
        # Health insurance
        "uninsured": "B27010_017E",
        "insurance": "B27010_002E",
        # Disability
        "disability": "B18101_001E",
    }

    def execute(self, topic: str = "", geography: str = "us", **kwargs) -> list[Finding]:
        api_key = get_env_key("CENSUS_API_KEY")
        topic_lower = topic.lower()

        # Match relevant variables (multiple if applicable)
        matched = [(k, v) for k, v in self.VARIABLES.items() if k in topic_lower]
        if not matched:
            matched = [
                ("population", self.VARIABLES["population"]),
                ("income", self.VARIABLES["income"]),
                ("poverty", self.VARIABLES["poverty"]),
            ]

        variables = list(dict(matched[:5]).values())  # deduplicate
        var_labels = [k for k, _ in matched[:5]]
        geo_params = self._parse_geography(geography)

        try:
            var_str = ",".join(["NAME"] + variables)
            params = {"get": var_str, **geo_params}
            if api_key:
                params["key"] = api_key
            data = self._fetch_json(f"{self.BASE_URL}/2022/acs/acs5", params=params)

            if len(data) < 2:
                return self._error(f"No census data for {topic}")

            findings = []
            for row in data[1:6]:
                parts = []
                for i, label in enumerate(var_labels):
                    val = row[i + 1] if i + 1 < len(row) else "N/A"
                    parts.append(f"{label}: {val}")
                findings.append(Finding(
                    title=row[0],
                    snippet=" | ".join(parts),
                    url="https://data.census.gov",
                    date="2022",
                    source_type=self.SOURCE_TYPE,
                ))
            return findings
        except (httpx.HTTPStatusError, httpx.TransportError) as e:
            return self._error(f"Census API error: {e}")
        except (KeyError, ValueError, IndexError) as e:
            return self._error(f"Failed to parse Census data: {e}")

    def _parse_geography(self, geography: str) -> dict:
        if not geography or geography == "us":
            return {"for": "us:*"}
        if geography.startswith("state:"):
            code = geography[6:].strip().upper()
            fips = STATE_FIPS.get(code)
            if fips:
                return {"for": f"state:{fips}"}
            return {"for": "state:*"}
        if geography.startswith("county:"):
            parts = geography[7:].strip().split(",")
            if len(parts) == 2:
                state_fips = STATE_FIPS.get(parts[1].strip().upper())
                if state_fips:
                    return {"for": "county:*", "in": f"state:{state_fips}"}
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
        if not query:
            return self._error("No query provided")

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
        except (httpx.HTTPStatusError, httpx.TransportError) as e:
            return self._error(f"OpenStates API error: {e}")
        except (KeyError, ValueError) as e:
            return self._error(f"Failed to parse state legislation results: {e}")
