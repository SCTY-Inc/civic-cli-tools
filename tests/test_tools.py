"""Tests for tool implementations with mocked HTTP."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from tools.implementations import (
    AcademicSearch,
    CensusSearch,
    CongressSearch,
    CourtSearch,
    FederalRegisterSearch,
    RegulationsSearch,
    StateLegislationSearch,
    WebSearch,
)
from tools.registry import ToolRegistry
from tools.models import ToolResult


@pytest.fixture
def mock_fetch():
    """Patch BaseTool._fetch_json to return controlled data."""
    with patch("tools.implementations.BaseTool._fetch_json") as mock:
        yield mock


class TestWebSearch:
    def test_uses_current_search_api(self, monkeypatch):
        monkeypatch.setenv("EXA_API_KEY", "test-key")
        mock_client = MagicMock()
        mock_client.search.return_value = MagicMock(
            results=[
                MagicMock(
                    title="Policy Update",
                    summary="Summary text",
                    text="Full text",
                    url="http://example.com",
                    published_date="2025-01-15T00:00:00Z",
                )
            ]
        )

        tool = WebSearch()
        tool._client = mock_client

        result = tool.execute(query="caregiver policy")

        assert len(result.findings) == 1
        _, kwargs = mock_client.search.call_args
        assert kwargs["num_results"] == 25
        assert kwargs["contents"] == {"text": {"max_characters": 1500}}
        assert result.findings[0].title == "Policy Update"

    def test_missing_api_key(self, monkeypatch):
        monkeypatch.delenv("EXA_API_KEY", raising=False)
        result = WebSearch().execute(query="caregiver policy")
        assert result.findings == []
        assert result.errors == ["EXA_API_KEY not set"]

    def test_value_error_surfaces_as_provider_error(self, monkeypatch):
        monkeypatch.setenv("EXA_API_KEY", "test-key")
        mock_client = MagicMock()
        mock_client.search.side_effect = ValueError("status code 429")
        tool = WebSearch()
        tool._client = mock_client
        result = tool.execute(query="caregiver policy")
        assert result.findings == []
        assert result.errors == ["Exa API error: status code 429"]


class TestAcademicSearch:
    def test_returns_findings(self, mock_fetch):
        mock_fetch.return_value = {
            "data": [
                {
                    "title": "Paper Title",
                    "abstract": "Abstract text",
                    "year": 2025,
                    "citationCount": 42,
                    "url": "http://paper",
                    "authors": [{"name": "Author A"}, {"name": "Author B"}],
                }
            ]
        }
        result = AcademicSearch().execute(query="test")
        assert len(result.findings) == 1
        assert result.findings[0].title == "Paper Title"
        assert result.findings[0].citations == 42
        assert result.findings[0].source_type == "ACADEMIC"

    def test_empty_query(self):
        result = AcademicSearch().execute(query="")
        assert result.findings == []
        assert result.errors == ["No query provided"]

    def test_api_error(self, mock_fetch):
        mock_fetch.side_effect = httpx.ConnectError("fail")
        result = AcademicSearch().execute(query="test")
        assert result.findings == []
        assert "api error" in result.errors[0].lower()

    def test_handles_null_abstract(self, mock_fetch):
        mock_fetch.return_value = {
            "data": [
                {
                    "title": "Paper Title",
                    "abstract": None,
                    "year": 2025,
                    "citationCount": 1,
                    "url": "http://paper",
                    "authors": [{"name": "Author A"}],
                }
            ]
        }
        result = AcademicSearch().execute(query="test")
        assert len(result.findings) == 1
        assert result.findings[0].title == "Paper Title"
        assert "Authors:" in result.findings[0].snippet


class TestCongressSearch:
    def test_returns_findings(self, mock_fetch, monkeypatch):
        monkeypatch.setenv("CONGRESS_GOV_API_KEY", "test-key")
        mock_fetch.return_value = {
            "bills": [
                {
                    "type": "HR",
                    "number": "1234",
                    "title": "Test Act",
                    "congress": 119,
                    "latestAction": {"text": "Referred to committee"},
                    "url": "http://bill",
                    "introducedDate": "2025-01-15",
                }
            ]
        }
        result = CongressSearch().execute(query="test")
        assert len(result.findings) == 1
        assert "HR1234" in result.findings[0].title
        assert result.findings[0].source_type == "CONGRESS"

    def test_prefers_latest_action_date_when_available(self, mock_fetch, monkeypatch):
        monkeypatch.setenv("CONGRESS_GOV_API_KEY", "test-key")
        mock_fetch.return_value = {
            "bills": [
                {
                    "type": "HR",
                    "number": "1234",
                    "title": "Test Act",
                    "congress": 119,
                    "latestAction": {
                        "text": "Passed House",
                        "actionDate": "2025-02-01",
                    },
                    "url": "http://bill",
                    "introducedDate": "2025-01-15",
                }
            ]
        }
        result = CongressSearch().execute(query="test")
        assert len(result.findings) == 1
        assert result.findings[0].date == "2025-02-01"

    def test_missing_api_key(self, monkeypatch):
        monkeypatch.delenv("CONGRESS_GOV_API_KEY", raising=False)
        result = CongressSearch().execute(query="test")
        assert result.findings == []
        assert result.errors == ["CONGRESS_GOV_API_KEY not set"]

    def test_handles_missing_latest_action_object(self, mock_fetch, monkeypatch):
        monkeypatch.setenv("CONGRESS_GOV_API_KEY", "test-key")
        mock_fetch.return_value = {
            "bills": [
                {
                    "type": "HR",
                    "number": "1234",
                    "title": "Test Act",
                    "congress": 119,
                    "latestAction": None,
                    "url": "http://bill",
                    "introducedDate": "2025-01-15",
                }
            ]
        }
        result = CongressSearch().execute(query="test")
        assert len(result.findings) == 1
        assert "Status: N/A" in result.findings[0].snippet


class TestFederalRegisterSearch:
    def test_returns_findings(self, mock_fetch):
        mock_fetch.return_value = {
            "results": [
                {
                    "title": "Rule Title",
                    "type": "Rule",
                    "agencies": [{"name": "EPA"}],
                    "abstract": "Abstract",
                    "html_url": "http://rule",
                    "publication_date": "2025-03-01",
                }
            ]
        }
        result = FederalRegisterSearch().execute(query="test")
        assert len(result.findings) == 1
        assert result.findings[0].source_type == "FED_REGISTER"

    def test_respects_results_limit_even_if_api_ignores_page_size(self, mock_fetch, monkeypatch):
        monkeypatch.setattr("tools.implementations._base.RESULTS_LIMIT", 1)
        mock_fetch.return_value = {
            "results": [
                {
                    "title": "Rule A",
                    "type": "Rule",
                    "agencies": [{"name": "EPA"}],
                    "abstract": "Abstract",
                    "html_url": "http://rule-a",
                    "publication_date": "2025-03-01",
                },
                {
                    "title": "Rule B",
                    "type": "Rule",
                    "agencies": [{"name": "EPA"}],
                    "abstract": "Abstract",
                    "html_url": "http://rule-b",
                    "publication_date": "2025-03-02",
                },
            ]
        }
        result = FederalRegisterSearch().execute(query="test")
        assert len(result.findings) == 1
        assert result.findings[0].title == "Rule A"


class TestRegulationsSearch:
    def test_returns_findings(self, mock_fetch, monkeypatch):
        monkeypatch.setenv("REGULATIONS_GOV_API_KEY", "test-key")
        mock_fetch.return_value = {
            "data": [
                {
                    "id": "DOC-123",
                    "attributes": {
                        "title": "Proposed Rule",
                        "documentType": "Proposed Rule",
                        "agencyId": "EPA",
                        "summary": "Summary text",
                        "postedDate": "2025-06-01T00:00:00Z",
                    },
                }
            ]
        }
        result = RegulationsSearch().execute(query="test")
        assert len(result.findings) == 1
        assert result.findings[0].source_type == "REGULATIONS"
        assert "DOC-123" in result.findings[0].url

    def test_respects_minimum_page_size(self, mock_fetch, monkeypatch):
        monkeypatch.setenv("REGULATIONS_GOV_API_KEY", "test-key")
        monkeypatch.setattr("tools.implementations._base.RESULTS_LIMIT", 1)
        mock_fetch.return_value = {"data": []}
        RegulationsSearch().execute(query="test")
        assert mock_fetch.call_args.kwargs["params"]["page[size]"] == 5

    def test_missing_api_key(self, monkeypatch):
        monkeypatch.delenv("REGULATIONS_GOV_API_KEY", raising=False)
        result = RegulationsSearch().execute(query="test")
        assert result.findings == []
        assert result.errors == ["REGULATIONS_GOV_API_KEY not set"]


class TestCourtSearch:
    def test_returns_findings(self, mock_fetch):
        mock_fetch.return_value = {
            "results": [
                {
                    "caseName": "Doe v. Smith",
                    "court": "Supreme Court",
                    "snippet": "The <mark>court</mark> held",
                    "absolute_url": "/opinion/123/",
                    "dateFiled": "2024-11-15",
                }
            ]
        }
        result = CourtSearch().execute(query="test")
        assert len(result.findings) == 1
        assert result.findings[0].title == "Doe v. Smith"
        assert "<mark>" not in result.findings[0].snippet
        assert "**court**" in result.findings[0].snippet


class TestCensusSearch:
    def test_returns_findings(self, mock_fetch):
        mock_fetch.return_value = [
            ["NAME", "B01003_001E", "B19013_001E", "B17001_002E"],
            ["California", "39538223", "78672", "4633830"],
            ["Texas", "29145505", "63826", "3938700"],
        ]
        result = CensusSearch().execute(topic="demographics")
        assert len(result.findings) == 2
        assert result.findings[0].title == "California"
        assert result.findings[0].source_type == "CENSUS"

    def test_specific_variable_match(self, mock_fetch):
        mock_fetch.return_value = [
            ["NAME", "B23025_005E"],
            ["United States", "6100000"],
        ]
        result = CensusSearch().execute(topic="unemployment rates")
        assert len(result.findings) == 1

    def test_geography_state_fips(self):
        assert CensusSearch()._parse_geography("state:CA") == {"for": "state:06"}

    def test_geography_us(self):
        tool = CensusSearch()
        assert tool._parse_geography("us") == {"for": "us:*"}
        assert tool._parse_geography("") == {"for": "us:*"}

    def test_invalid_api_key_is_reported_clearly(self, mock_fetch):
        request = httpx.Request("GET", "https://api.census.gov/data/2022/acs/acs5")
        response = httpx.Response(
            302,
            request=request,
            headers={"location": "https://api.census.gov/data/invalid_key.html"},
        )
        mock_fetch.side_effect = httpx.HTTPStatusError("redirect", request=request, response=response)
        result = CensusSearch().execute(topic="income")
        assert result.findings == []
        assert result.errors == ["CENSUS_API_KEY invalid"]


class TestRegistry:
    def test_returns_error_text_without_fake_findings(self):
        registry = ToolRegistry({"type": "all", "states": []})
        registry._tools["web_search"] = MagicMock(
            execute=MagicMock(return_value=ToolResult(errors=["boom"]))
        )

        findings, formatted = registry.execute("web_search", {"query": "test"})

        assert findings == []
        assert formatted == "Tool error: boom"

    def test_policy_scope_rejects_undeclared_tool_calls(self, monkeypatch):
        monkeypatch.setenv("EXA_API_KEY", "test-key")
        registry = ToolRegistry({"type": "policy", "states": []})
        findings, formatted = registry.execute("web_search", {"query": "test"})
        assert findings == []
        assert formatted == "Unknown tool: web_search"

    def test_unexpected_tool_exception_is_not_hidden(self):
        registry = ToolRegistry({"type": "all", "states": []})
        registry._tools["web_search"] = MagicMock(execute=MagicMock(side_effect=RuntimeError("boom")))
        with pytest.raises(RuntimeError, match="boom"):
            registry.execute("web_search", {"query": "test"})


class TestStateLegislationSearch:
    def test_returns_findings(self, mock_fetch, monkeypatch):
        monkeypatch.setenv("OPENSTATES_API_KEY", "test-key")
        mock_fetch.return_value = {
            "results": [
                {
                    "identifier": "SB-123",
                    "title": "Test Bill",
                    "jurisdiction": {"name": "California"},
                    "session": "2025-2026",
                    "latest_action_description": "Passed assembly",
                    "latest_action_date": "2025-04-01",
                    "openstates_url": "http://bill",
                }
            ]
        }
        result = StateLegislationSearch(default_states=["CA"]).execute(query="test")
        assert len(result.findings) == 1
        assert "SB-123" in result.findings[0].title
        assert result.findings[0].source_type == "STATE_LEG"

    def test_uses_legiscan_when_openstates_is_unavailable(self, mock_fetch, monkeypatch):
        monkeypatch.delenv("OPENSTATES_API_KEY", raising=False)
        monkeypatch.setenv("LEGISCAN_API_KEY", "test-key")
        mock_fetch.return_value = {
            "status": "OK",
            "searchresult": {
                "summary": {"count": 1},
                "0": {
                    "state": "CA",
                    "bill_number": "AB2324",
                    "title": "Vocational education: youth caregivers.",
                    "last_action_date": "2026-04-21",
                    "last_action": "Re-referred to Com. on APPR.",
                    "url": "https://legiscan.com/CA/bill/AB2324/2025",
                },
            },
        }
        result = StateLegislationSearch(default_states=["CA"]).execute(query="caregiver")
        assert len(result.findings) == 1
        assert result.findings[0].title.startswith("AB2324:")
        assert result.findings[0].source_type == "LEGISCAN"

    def test_falls_back_to_legiscan_when_openstates_returns_no_results(self, mock_fetch, monkeypatch):
        monkeypatch.setenv("OPENSTATES_API_KEY", "openstates-key")
        monkeypatch.setenv("LEGISCAN_API_KEY", "legiscan-key")
        mock_fetch.side_effect = [
            {"results": []},
            {
                "status": "OK",
                "searchresult": {
                    "summary": {"count": 1},
                    "0": {
                        "state": "CA",
                        "bill_number": "AB2324",
                        "title": "Vocational education: youth caregivers.",
                        "last_action_date": "2026-04-21",
                        "last_action": "Re-referred to Com. on APPR.",
                        "url": "https://legiscan.com/CA/bill/AB2324/2025",
                    },
                },
            },
        ]
        result = StateLegislationSearch(default_states=["CA"]).execute(query="caregiver")
        assert len(result.findings) == 1
        assert result.findings[0].source_type == "LEGISCAN"
        assert mock_fetch.call_count == 2

    def test_missing_api_key(self, monkeypatch):
        monkeypatch.delenv("OPENSTATES_API_KEY", raising=False)
        monkeypatch.delenv("LEGISCAN_API_KEY", raising=False)
        result = StateLegislationSearch().execute(query="test")
        assert result.findings == []
        assert result.errors == ["OPENSTATES_API_KEY or LEGISCAN_API_KEY not set"]

    def test_handles_missing_jurisdiction_object(self, mock_fetch, monkeypatch):
        monkeypatch.setenv("OPENSTATES_API_KEY", "test-key")
        mock_fetch.return_value = {
            "results": [
                {
                    "identifier": "SB-123",
                    "title": "Test Bill",
                    "jurisdiction": None,
                    "session": "2025-2026",
                    "latest_action_description": "Passed assembly",
                    "latest_action_date": "2025-04-01",
                    "openstates_url": "http://bill",
                }
            ]
        }
        result = StateLegislationSearch(default_states=["CA"]).execute(query="test")
        assert len(result.findings) == 1
        assert "State: N/A" in result.findings[0].snippet
