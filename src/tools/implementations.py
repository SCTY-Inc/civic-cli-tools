"""Tool implementations for policy research."""

import httpx
from exa_py import Exa

from . import base as _base
from .base import BaseTool, get_env_key
from .models import Finding

STATE_FIPS = dict(
    item.split(":")
    for item in """
    AL:01 AK:02 AZ:04 AR:05 CA:06 CO:08 CT:09 DE:10 DC:11 FL:12 GA:13 HI:15 ID:16 IL:17 IN:18 IA:19 KS:20
    KY:21 LA:22 ME:23 MD:24 MA:25 MI:26 MN:27 MS:28 MO:29 MT:30 NE:31 NV:32 NH:33 NJ:34 NM:35 NY:36 NC:37
    ND:38 OH:39 OK:40 OR:41 PA:42 PR:72 RI:44 SC:45 SD:46 TN:47 TX:48 UT:49 VT:50 VA:51 WA:53 WV:54 WI:55 WY:56
    """.split()
)


class WebSearch(BaseTool):
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
                query,
                type="auto",
                use_autoprompt=False,
                num_results=_base.RESULTS_LIMIT,
                text={"max_characters": 1500},
                summary=True,
            )
            findings = []
            for result in results.results:
                findings.append(Finding(
                    title=result.title or "Untitled",
                    snippet=getattr(result, "summary", "") or getattr(result, "text", "")[:1000],
                    url=result.url,
                    date=(getattr(result, "published_date", "") or "")[:10],
                    source_type=self.SOURCE_TYPE,
                ))
            return findings
        except ValueError:
            raise
        except Exception as exc:
            return self._error(f"Web search failed: {exc}")


class AcademicSearch(BaseTool):
    SOURCE_TYPE = "ACADEMIC"
    BASE_URL = "https://api.semanticscholar.org/graph/v1"

    def execute(self, query: str = "", **kwargs) -> list[Finding]:
        if not query:
            return self._error("No query provided")
        try:
            data = self._fetch_json(
                f"{self.BASE_URL}/paper/search",
                params={"query": query, "limit": _base.RESULTS_LIMIT, "fields": "title,abstract,year,citationCount,url,authors"},
            )
        except Exception as exc:
            return self._error(f"Semantic Scholar API error: {exc}")

        findings = []
        for paper in data.get("data", []):
            try:
                authors_data = paper.get("authors") or []
                authors = ", ".join((author.get("name") or "Unknown") for author in authors_data[:3]) or "Unknown"
                if len(authors_data) > 3:
                    authors += " et al."
                findings.append(Finding(
                    title=paper.get("title") or "Untitled",
                    snippet=f"Authors: {authors}\n{(paper.get('abstract') or '')[:600]}",
                    url=paper.get("url") or "",
                    date=str(paper.get("year") or ""),
                    source_type=self.SOURCE_TYPE,
                    citations=paper.get("citationCount") or 0,
                ))
            except Exception:
                continue
        return findings if findings or not data.get("data") else self._error("Semantic Scholar returned unreadable records")


class CongressSearch(BaseTool):
    SOURCE_TYPE = "CONGRESS"
    BASE_URL = "https://api.congress.gov/v3"

    def execute(self, query: str = "", **kwargs) -> list[Finding]:
        api_key = get_env_key("CONGRESS_GOV_API_KEY")
        if not api_key:
            return self._error("CONGRESS_GOV_API_KEY not set")
        if not query:
            return self._error("No query provided")
        try:
            data = self._fetch_json(f"{self.BASE_URL}/bill", params={"query": query, "limit": _base.RESULTS_LIMIT, "api_key": api_key})
            return [
                Finding(
                    title=f"{bill.get('type', '')}{bill.get('number', '')}: {bill.get('title', 'No title')}",
                    snippet=f"Congress {bill.get('congress', 'N/A')} | Status: {bill.get('latestAction', {}).get('text', 'N/A')}",
                    url=bill.get("url", ""),
                    date=bill.get("introducedDate", ""),
                    source_type=self.SOURCE_TYPE,
                )
                for bill in data.get("bills", [])
            ]
        except Exception as exc:
            return self._error(f"Congress.gov API error: {exc}")


class FederalRegisterSearch(BaseTool):
    SOURCE_TYPE = "FED_REGISTER"
    BASE_URL = "https://www.federalregister.gov/api/v1"

    def execute(self, query: str = "", **kwargs) -> list[Finding]:
        if not query:
            return self._error("No query provided")
        try:
            data = self._fetch_json(
                f"{self.BASE_URL}/documents.json",
                params={"conditions[term]": query, "per_page": _base.RESULTS_LIMIT, "order": "relevance"},
            )
            findings = []
            for doc in data.get("results", []):
                agencies = ", ".join(agency.get("name", "") for agency in doc.get("agencies", [])[:2]) or "N/A"
                snippet = f"Type: {doc.get('type', 'N/A')} | Agency: {agencies}"
                if doc.get("abstract"):
                    snippet += f"\n{doc['abstract'][:500]}"
                findings.append(Finding(
                    title=doc.get("title", "Untitled"),
                    snippet=snippet,
                    url=doc.get("html_url", ""),
                    date=doc.get("publication_date", ""),
                    source_type=self.SOURCE_TYPE,
                ))
            return findings
        except Exception as exc:
            return self._error(f"Federal Register API error: {exc}")


class RegulationsSearch(BaseTool):
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
                params={"filter[searchTerm]": query, "page[size]": _base.RESULTS_LIMIT, "api_key": api_key},
            )
            findings = []
            for doc in data.get("data", []):
                attrs = doc.get("attributes", {})
                snippet = f"Type: {attrs.get('documentType', 'N/A')} | Agency: {attrs.get('agencyId', 'N/A')}"
                if attrs.get("summary"):
                    snippet += f"\n{attrs['summary'][:500]}"
                findings.append(Finding(
                    title=attrs.get("title", "Untitled"),
                    snippet=snippet,
                    url=f"https://www.regulations.gov/document/{doc.get('id', '')}",
                    date=(attrs.get("postedDate", "") or "")[:10],
                    source_type=self.SOURCE_TYPE,
                ))
            return findings
        except Exception as exc:
            return self._error(f"Regulations.gov API error: {exc}")


class CourtSearch(BaseTool):
    SOURCE_TYPE = "COURT"
    BASE_URL = "https://www.courtlistener.com/api/rest/v4"

    def execute(self, query: str = "", **kwargs) -> list[Finding]:
        if not query:
            return self._error("No query provided")
        try:
            data = self._fetch_json(
                f"{self.BASE_URL}/search/",
                params={"q": query, "type": "o", "order_by": "score desc", "page_size": _base.RESULTS_LIMIT},
            )
            findings = []
            for case in data.get("results", []):
                snippet = f"Court: {case.get('court', 'N/A')}"
                if case.get("snippet"):
                    snippet += f"\n{case['snippet'].replace('<mark>', '**').replace('</mark>', '**')[:500]}"
                findings.append(Finding(
                    title=case.get("caseName", "Unknown Case"),
                    snippet=snippet,
                    url=f"https://www.courtlistener.com{case.get('absolute_url', '')}",
                    date=case.get("dateFiled", ""),
                    source_type=self.SOURCE_TYPE,
                ))
            return findings
        except Exception as exc:
            return self._error(f"CourtListener API error: {exc}")


class CensusSearch(BaseTool):
    SOURCE_TYPE = "CENSUS"
    BASE_URL = "https://api.census.gov/data"
    VARIABLES = {
        "population": "B01003_001E", "median_age": "B01002_001E", "income": "B19013_001E", "poverty": "B17001_002E",
        "gini": "B19083_001E", "housing": "B25001_001E", "median_rent": "B25064_001E", "homeownership": "B25003_002E",
        "vacancy": "B25002_003E", "education": "B15003_022E", "bachelors": "B15003_022E", "high_school": "B15003_017E",
        "unemployment": "B23025_005E", "labor_force": "B23025_002E", "uninsured": "B27010_017E", "insurance": "B27010_002E",
        "disability": "B18101_001E",
    }

    def execute(self, topic: str = "", geography: str = "us", **kwargs) -> list[Finding]:
        api_key = get_env_key("CENSUS_API_KEY")
        matched = [(name, code) for name, code in self.VARIABLES.items() if name in topic.lower()]
        if not matched:
            matched = [("population", self.VARIABLES["population"]), ("income", self.VARIABLES["income"]), ("poverty", self.VARIABLES["poverty"])]
        variables = list(dict(matched[:5]).values())
        labels = [name for name, _ in matched[:5]]

        try:
            findings = []
            for geo_params in self._parse_geography(geography):
                params = {"get": ",".join(["NAME", *variables]), **geo_params}
                if api_key:
                    params["key"] = api_key
                data = self._fetch_json(f"{self.BASE_URL}/2022/acs/acs5", params=params)
                if len(data) < 2:
                    continue
                for row in data[1:]:
                    snippet = " | ".join(
                        f"{label}: {row[index + 1] if index + 1 < len(row) else 'N/A'}"
                        for index, label in enumerate(labels)
                    )
                    findings.append(Finding(
                        title=row[0],
                        snippet=snippet,
                        url="https://data.census.gov",
                        date="2022",
                        source_type=self.SOURCE_TYPE,
                    ))
                    if len(findings) >= _base.RESULTS_LIMIT:
                        return findings
            return findings or self._error(f"No census data for {topic}")
        except Exception as exc:
            return self._error(f"Census API error: {exc}")

    def _parse_geography(self, geography: str) -> list[dict[str, str]]:
        if not geography or geography == "us":
            return [{"for": "us:1"}]
        if geography.startswith("state:"):
            states = [part.strip() for part in geography.split(":", 1)[1].split(",") if part.strip()]
            if not states:
                raise ValueError("State geography must include at least one state")
            return [{"for": f"state:{self._state_fips(state)}"} for state in states]
        if geography.startswith("county:"):
            counties = [part.strip() for part in geography.split(":", 1)[1].split(",") if part.strip()]
            if not counties:
                raise ValueError("County geography must include at least one county FIPS code")
            queries = []
            for county in counties:
                if not county.isdigit() or len(county) != 5:
                    raise ValueError("County geography must use 5-digit FIPS codes like county:06037")
                queries.append({"for": f"county:{county[2:]}", "in": f"state:{county[:2]}"})
            return queries
        raise ValueError(f"Unsupported geography: {geography}")

    def _state_fips(self, state: str) -> str:
        state = state.strip().upper()
        if state.isdigit() and len(state) == 2:
            return state
        if state in STATE_FIPS:
            return STATE_FIPS[state]
        raise ValueError(f"Unknown state code: {state}")


class StateLegislationSearch(BaseTool):
    SOURCE_TYPE = "STATE_LEG"
    BASE_URL = "https://v3.openstates.org"

    def __init__(self, default_states: list[str] | None = None):
        self.default_states = [state.upper() for state in (default_states or [])]

    def execute(self, query: str = "", state: str | None = None, **kwargs) -> list[Finding]:
        api_key = get_env_key("OPENSTATES_API_KEY")
        if not api_key:
            return self._error("OPENSTATES_API_KEY not set")
        if not query:
            return self._error("No query provided")

        states = self._states_to_search(state)
        per_page = _base.RESULTS_LIMIT if states == [None] else max(1, _base.RESULTS_LIMIT // len(states))
        try:
            findings = []
            for jurisdiction in states:
                params = {"q": query, "per_page": per_page}
                if jurisdiction:
                    params["jurisdiction"] = jurisdiction.lower()
                data = self._fetch_json(f"{self.BASE_URL}/bills", params=params, headers={"X-API-KEY": api_key})
                for bill in data.get("results", []):
                    latest = bill.get("latest_action_description", "N/A")[:100]
                    findings.append(Finding(
                        title=f"{bill.get('identifier', 'N/A')}: {bill.get('title', 'No title')[:80]}",
                        snippet=(
                            f"State: {bill.get('jurisdiction', {}).get('name', 'N/A')} | "
                            f"Session: {bill.get('session', 'N/A')} | Latest: {latest}"
                        ),
                        url=bill.get("openstates_url", ""),
                        date=bill.get("latest_action_date", ""),
                        source_type=self.SOURCE_TYPE,
                    ))
                    if len(findings) >= _base.RESULTS_LIMIT:
                        return findings
            return findings
        except Exception as exc:
            return self._error(f"OpenStates API error: {exc}")

    def _states_to_search(self, state: str | None) -> list[str | None]:
        raw_states = [state] if state else self.default_states
        if not raw_states:
            return [None]
        states = []
        for item in raw_states:
            states.extend(part.strip().upper() for part in str(item).split(",") if part.strip())
        return states or [None]
