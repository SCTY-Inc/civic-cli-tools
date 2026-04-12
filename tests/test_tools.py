"""Tests for tool implementations with mocked HTTP."""

import json
import pytest
from unittest.mock import patch, MagicMock

import httpx

from tools.implementations import (
    AcademicSearch, CongressSearch, FederalRegisterSearch,
    RegulationsSearch, CourtSearch, CensusSearch, StateLegislationSearch,
)
from tools.registry import ToolRegistry


@pytest.fixture
def mock_fetch():
    """Patch BaseTool._fetch_json to return controlled data."""
    with patch("tools.implementations.BaseTool._fetch_json") as m:
        yield m


class TestAcademicSearch:
    def test_returns_findings(self, mock_fetch):
        mock_fetch.return_value = {
            "data": [{
                "title": "Paper Title",
                "abstract": "Abstract text",
                "year": 2025,
                "citationCount": 42,
                "url": "http://paper",
                "authors": [{"name": "Author A"}, {"name": "Author B"}],
            }]
        }
        tool = AcademicSearch()
        findings = tool.execute(query="test")
        assert len(findings) == 1
        assert findings[0].title == "Paper Title"
        assert findings[0].citations == 42
        assert findings[0].source_type == "ACADEMIC"

    def test_empty_query(self):
        tool = AcademicSearch()
        findings = tool.execute(query="")
        assert len(findings) == 1
        assert findings[0].title == "Error"

    def test_null_abstract_does_not_crash(self, mock_fetch):
        mock_fetch.return_value = {
            "data": [{
                "title": "Paper Title",
                "abstract": None,
                "year": 2025,
                "citationCount": 42,
                "url": "http://paper",
                "authors": [{"name": "Author A"}],
            }]
        }
        tool = AcademicSearch()
        findings = tool.execute(query="test")
        assert len(findings) == 1
        assert findings[0].is_error is False

    def test_api_error(self, mock_fetch):
        mock_fetch.side_effect = httpx.ConnectError("fail")
        tool = AcademicSearch()
        findings = tool.execute(query="test")
        assert len(findings) == 1
        assert "error" in findings[0].snippet.lower()


class TestCongressSearch:
    def test_returns_findings(self, mock_fetch, monkeypatch):
        monkeypatch.setenv("CONGRESS_GOV_API_KEY", "test-key")
        mock_fetch.return_value = {
            "bills": [{
                "type": "HR", "number": "1234",
                "title": "Test Act", "congress": 119,
                "latestAction": {"text": "Referred to committee"},
                "url": "http://bill", "introducedDate": "2025-01-15",
            }]
        }
        tool = CongressSearch()
        findings = tool.execute(query="test")
        assert len(findings) == 1
        assert "HR1234" in findings[0].title
        assert findings[0].source_type == "CONGRESS"

    def test_missing_api_key(self, monkeypatch):
        monkeypatch.delenv("CONGRESS_GOV_API_KEY", raising=False)
        tool = CongressSearch()
        findings = tool.execute(query="test")
        assert findings[0].title == "Error"


class TestFederalRegisterSearch:
    def test_returns_findings(self, mock_fetch):
        mock_fetch.return_value = {
            "results": [{
                "title": "Rule Title",
                "type": "Rule",
                "agencies": [{"name": "EPA"}],
                "abstract": "Abstract",
                "html_url": "http://rule",
                "publication_date": "2025-03-01",
            }]
        }
        tool = FederalRegisterSearch()
        findings = tool.execute(query="test")
        assert len(findings) == 1
        assert findings[0].source_type == "FED_REGISTER"


class TestRegulationsSearch:
    def test_returns_findings(self, mock_fetch, monkeypatch):
        monkeypatch.setenv("REGULATIONS_GOV_API_KEY", "test-key")
        mock_fetch.return_value = {
            "data": [{
                "id": "DOC-123",
                "attributes": {
                    "title": "Proposed Rule",
                    "documentType": "Proposed Rule",
                    "agencyId": "EPA",
                    "summary": "Summary text",
                    "postedDate": "2025-06-01T00:00:00Z",
                },
            }]
        }
        tool = RegulationsSearch()
        findings = tool.execute(query="test")
        assert len(findings) == 1
        assert findings[0].source_type == "REGULATIONS"
        assert "DOC-123" in findings[0].url

    def test_missing_api_key(self, monkeypatch):
        monkeypatch.delenv("REGULATIONS_GOV_API_KEY", raising=False)
        tool = RegulationsSearch()
        findings = tool.execute(query="test")
        assert findings[0].title == "Error"


class TestCourtSearch:
    def test_returns_findings(self, mock_fetch):
        mock_fetch.return_value = {
            "results": [{
                "caseName": "Doe v. Smith",
                "court": "Supreme Court",
                "snippet": "The <mark>court</mark> held",
                "absolute_url": "/opinion/123/",
                "dateFiled": "2024-11-15",
            }]
        }
        tool = CourtSearch()
        findings = tool.execute(query="test")
        assert len(findings) == 1
        assert findings[0].title == "Doe v. Smith"
        assert "<mark>" not in findings[0].snippet
        assert "**court**" in findings[0].snippet


class TestCensusSearch:
    def test_returns_findings(self, mock_fetch):
        mock_fetch.return_value = [
            ["NAME", "B01003_001E", "B19013_001E", "B17001_002E"],
            ["California", "39538223", "78672", "4633830"],
            ["Texas", "29145505", "63826", "3938700"],
        ]
        tool = CensusSearch()
        findings = tool.execute(topic="demographics")
        assert len(findings) == 2
        assert findings[0].title == "California"
        assert findings[0].source_type == "CENSUS"

    def test_specific_variable_match(self, mock_fetch):
        mock_fetch.return_value = [
            ["NAME", "B23025_005E"],
            ["United States", "6100000"],
        ]
        tool = CensusSearch()
        findings = tool.execute(topic="unemployment rates")
        assert len(findings) == 1

    def test_geography_state_fips(self):
        tool = CensusSearch()
        assert tool._parse_geography("state:CA,NY") == [{"for": "state:06"}, {"for": "state:36"}]

    def test_geography_county_fips(self):
        tool = CensusSearch()
        assert tool._parse_geography("county:06037") == [{"for": "county:037", "in": "state:06"}]

    def test_geography_us(self):
        tool = CensusSearch()
        assert tool._parse_geography("us") == [{"for": "us:1"}]
        assert tool._parse_geography("") == [{"for": "us:1"}]


class TestStateLegislationSearch:
    def test_returns_findings(self, mock_fetch, monkeypatch):
        monkeypatch.setenv("OPENSTATES_API_KEY", "test-key")
        mock_fetch.return_value = {
            "results": [{
                "identifier": "SB-123",
                "title": "Test Bill",
                "jurisdiction": {"name": "California"},
                "session": "2025-2026",
                "latest_action_description": "Passed assembly",
                "latest_action_date": "2025-04-01",
                "openstates_url": "http://bill",
            }]
        }
        tool = StateLegislationSearch(default_states=["CA"])
        findings = tool.execute(query="test")
        assert len(findings) == 1
        assert "SB-123" in findings[0].title
        assert findings[0].source_type == "STATE_LEG"

    def test_multi_state_scope_queries_each_state(self, monkeypatch):
        monkeypatch.setenv("OPENSTATES_API_KEY", "test-key")
        seen = []

        def fake_fetch(*args, **kwargs):
            jurisdiction = kwargs["params"].get("jurisdiction")
            seen.append(jurisdiction)
            return {
                "results": [{
                    "identifier": jurisdiction.upper(),
                    "title": f"Bill {jurisdiction}",
                    "jurisdiction": {"name": jurisdiction.upper()},
                    "session": "2025-2026",
                    "latest_action_description": "Introduced",
                    "latest_action_date": "2025-04-01",
                    "openstates_url": f"http://{jurisdiction}",
                }]
            }

        tool = StateLegislationSearch(default_states=["CA", "NY"])
        tool._fetch_json = fake_fetch
        findings = tool.execute(query="test")
        assert seen == ["ca", "ny"]
        assert len(findings) == 2

    def test_missing_api_key(self, monkeypatch):
        monkeypatch.delenv("OPENSTATES_API_KEY", raising=False)
        tool = StateLegislationSearch()
        findings = tool.execute(query="test")
        assert findings[0].title == "Error"


class TestToolRegistry:
    def test_defaults_census_geography_from_scope(self):
        registry = ToolRegistry({"type": "state", "states": ["CA", "NY"]})
        captured = {}

        def fake_execute(**kwargs):
            captured.update(kwargs)
            return []

        registry._tools["census_search"].execute = fake_execute
        registry.execute("census_search", {"topic": "population"})
        assert captured["geography"] == "state:CA,NY"
